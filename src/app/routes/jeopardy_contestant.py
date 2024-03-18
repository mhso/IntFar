import flask
from flask_socketio import emit

import app.util as app_util

from app.routes.jeopardy_presenter import PLAYER_NAMES, PLAYER_BACKGROUNDS, LOBBY_CODE, Contestant

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
        return flask.redirect(flask.url_for(".game_view"))

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

    player_data = [
        {"id": str(disc_id), "name": PLAYER_NAMES[disc_id]}
        for disc_id in PLAYER_NAMES
        if not disc_id in active_contestants
    ]

    if error:
        return app_util.make_template_context(
            "jeopardy/contestant_lobby.html",
            player_data=player_data,
            error=error
        )

    color = flask.request.form.get("color")
    avatar = app_util.discord_request("func", "get_discord_avatar", disc_id)

    if avatar:
        avatar = flask.url_for("static", filename=avatar.replace("app/static/", ""))

    turn_id = list(PLAYER_NAMES.keys()).index(disc_id)
    contestant = Contestant(disc_id, turn_id, PLAYER_NAMES[disc_id], avatar, color)

    response = flask.redirect(flask.url_for(".game_view"))
    response.set_cookie("user_data", contestant.to_json())

    return response

@jeopardy_contestant_page.route("/game")
def game_view():
    contestant = Contestant.from_json(flask.request.cookies.get("user_data"))
    state = flask.current_app.config["JEOPARDY_DATA"]["state"]

    if state is not None:
        state_dict = state.__dict__
        for data in state.player_data:
            if data["id"] == str(contestant.disc_id):
                contestant.score = data["score"]
                break
    else:
        state_dict = {"jeopardy_round": 0}

    return app_util.make_template_context(
        "jeopardy/contestant_game.html",
        active_player=str(contestant.disc_id),
        turn_id=contestant.index,
        nickname=contestant.name,
        avatar=contestant.avatar,
        color=contestant.color,
        score=contestant.score,
        ping=contestant.ping,
        player_bg_img=PLAYER_BACKGROUNDS[contestant.disc_id],
        **state_dict
    )

@app_util.socket_io.event
def calculate_ping(disc_id: str, timestamp: float):
    contestant: Contestant = flask.current_app.config["JEOPARDY_DATA"]["contestants"].get(int(disc_id))

    if contestant is not None:
        contestant.calculate_ping(timestamp)

        emit("ping_calculated", f"{max(contestant.ping, 0.1):.1f}")

@app_util.socket_io.event
def make_daily_wager(disc_id: str, amount: str):
    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    contestant: Contestant = jeopardy_data["contestants"][int(disc_id)]
    state = jeopardy_data["state"]

    max_wager = max(contestant.score, 500 * state.jeopardy_round)

    try:
        amount = int(amount)
    except ValueError:
        emit("invalid_wager", max_wager)
        return

    if 100 <= amount <= max_wager:
        emit("daily_wager_made", amount)
        emit("daily_wager_made", amount, to="presenter")
    else:
        emit("invalid_wager", max_wager)

@app_util.socket_io.event
def make_finale_wager(disc_id: str, amount: str):
    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    contestant: Contestant = jeopardy_data["contestants"][int(disc_id)]

    max_wager = max(contestant.score, 1000)

    try:
        amount = int(amount)
    except ValueError:
        emit("invalid_wager", max_wager)
        return

    if 100 <= amount <= max_wager:
        contestant.finale_wager = amount
        emit("finale_wager_made")
    else:
        emit("invalid_wager", max_wager)

@app_util.socket_io.event
def give_finale_answer(disc_id: str, answer: str):
    contestant: Contestant = flask.current_app.config["JEOPARDY_DATA"]["contestants"][int(disc_id)]
    contestant.finale_answer = answer
    
    emit("finale_answer_given")
