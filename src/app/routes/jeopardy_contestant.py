import json
import flask
from time import time
from flask_socketio import emit, send

import app.util as app_util

from app.routes.jeopardy_presenter import PLAYER_NAMES, LOBBY_CODE, Contestant

jeopardy_contestant_page = flask.Blueprint("jeopardy_contestant", __name__, template_folder="templates")

@jeopardy_contestant_page.route("/")
def home():
    active_contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]
    player_data = [
        {"id": str(disc_id), "name": PLAYER_NAMES[disc_id]}
        for disc_id in PLAYER_NAMES
        if not disc_id in active_contestants
    ]

    if "user_data" in flask.request.cookies:
        contestant = Contestant.from_json(flask.request.cookies["user_data"])
        if contestant.disc_id not in active_contestants:
            active_contestants[contestant.disc_id] = contestant

        return flask.redirect(flask.url_for(".question_view", jeopardy_round=0, category="mechanics", tier=1))

    return app_util.make_template_context("jeopardy/contestant_lobby.html", player_data=player_data)

@jeopardy_contestant_page.route("/join", methods=["POST"])
def join_lobby():
    lobby_code = flask.request.form.get("code")
    disc_id = int(flask.request.form.get("contestant"))
    active_contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]

    error = None
    if disc_id is None:
        error = "Du mangler at vælge hvem du er"
    elif disc_id not in PLAYER_NAMES:
        error = "Du har valgt en ugyldig spiller"
    elif disc_id in active_contestants:
        error = "Denne spiller er allerede med i lobbyen"
    elif lobby_code != LOBBY_CODE:
        error = "Forkert lobby kode"

    if error:
        return app_util.make_template_context(
            "jeopardy/contestant_lobby.html",
            error=error
        )

    color = flask.request.form.get("color")
    avatar = app_util.discord_request("func", "get_discord_avatar", disc_id)

    if avatar:
        avatar = flask.url_for("static", filename=avatar.replace("app/static/", ""))

    turn_id = list(PLAYER_NAMES.keys()).index(disc_id)
    contestant = Contestant(disc_id, turn_id, PLAYER_NAMES[disc_id], avatar, color)

    response = flask.redirect(flask.url_for(".question_view"))
    response.set_cookie("user_data", contestant.to_json())

    return response

@jeopardy_contestant_page.route("/game")
def question_view():
    contestant = Contestant.from_json(flask.request.cookies.get("user_data"))
    state = flask.current_app.config["JEOPARDY_DATA"]["state"]

    if state is not None:
        state_dict = state.__dict__
        contestant.score = state.player_data[contestant.index]["score"]
    else:
        state_dict = {"round": 0}

    return app_util.make_template_context(
        "jeopardy/contestant_game.html",
        active_player=str(contestant.disc_id),
        turn_id=contestant.index,
        nickname=contestant.name,
        avatar=contestant.avatar,
        color=contestant.color,
        score=contestant.score,
        ping=contestant.ping,
        **state_dict
    )

@app_util.socket_io.event
def calculate_ping(disc_id, timestamp):
    contestant: Contestant = flask.current_app.config["JEOPARDY_DATA"]["contestants"].get(int(disc_id))

    if contestant is not None:
        contestant.calculate_ping(timestamp)

        emit("ping_calculated", f"{contestant.ping:.1f}")
