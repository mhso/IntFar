import flask
from flask_socketio import emit

import app.util as app_util

from app.routes.jeopardy_presenter import PLAYER_NAMES, PLAYER_INDEXES, PLAYER_BACKGROUNDS, Contestant

jeopardy_contestant_page = flask.Blueprint("jeopardy_contestant", __name__, template_folder="templates")

@jeopardy_contestant_page.route("/")
def home():
    if "user_data" in flask.request.cookies:
        return flask.redirect(flask.url_for(".game_view"))

    return flask.abort(404)

@jeopardy_contestant_page.route("/<client_secret>")
def lobby(client_secret):
    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    database = flask.current_app.config["DATABASE"]

    if client_secret is None or client_secret == "None":
        return flask.abort(404)

    state = jeopardy_data["state"]
    disc_id = database.get_user_from_secret(client_secret)

    if disc_id is None or int(disc_id) not in PLAYER_NAMES:
        return flask.abort(404)

    avatar = app_util.discord_request("func", "get_discord_avatar", disc_id)
    if avatar:
        avatar = flask.url_for("static", filename=avatar.replace("app/static/", ""))

    if state is None:
        return app_util.make_template_context("jeopardy/contestant_nogame.html")

    if "user_data" in flask.request.cookies:
        return flask.redirect(flask.url_for(".game_view"))

    return app_util.make_template_context(
        "jeopardy/contestant_lobby.html",
        user_id=str(disc_id),
        player_name=PLAYER_NAMES[disc_id],
        avatar=avatar,
    )

@jeopardy_contestant_page.route("/join", methods=["POST"])
def join_lobby():
    name = flask.request.form.get("name")
    disc_id = int(flask.request.form.get("user_id"))
    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    state = jeopardy_data["state"]

    if state is None:
        return app_util.make_template_context("jeopardy/contestant_nogame.html")

    error = None
    if name is None or name == "":
        error = "Du skal give et navn"
    elif len(name) > 10:
        error = "Dit navn er for langt (max 10 bogstaver)"

    if error:
        return app_util.make_template_context(
            "jeopardy/contestant_lobby.html",
            user_id=str(disc_id),
            player_name=name,
            error=error
        )

    color = flask.request.form.get("color")
    avatar = app_util.discord_request("func", "get_discord_avatar", disc_id)

    if avatar:
        avatar = flask.url_for("static", filename=avatar.replace("app/static/", ""))
    else:
        avatar = flask.url_for("static", filename="img/questionmark.png")

    turn_id = PLAYER_INDEXES.index(disc_id)
    contestant = Contestant(disc_id, turn_id, name, avatar, color)

    response = flask.redirect(flask.url_for(".game_view"))
    max_age = 60 * 60 * 6 # 6 hours
    response.set_cookie("user_data", contestant.to_json(), max_age=max_age)

    return response

@jeopardy_contestant_page.route("/game")
def game_view():
    if "user_data" not in flask.request.cookies:
        return flask.redirect(flask.url_for(".lobby", client_secret=None))

    contestant = Contestant.from_json(flask.request.cookies["user_data"])
    state = flask.current_app.config["JEOPARDY_DATA"]["state"]

    if state is None:
        return app_util.make_template_context("jeopardy/contestant_nogame.html")

    state_dict = state.__dict__
    for data in state.player_data:
        if data["disc_id"] == str(contestant.disc_id):
            contestant.score = data["score"]
            contestant.buzzes = data["buzzes"]
            contestant.hits = data["hits"]
            contestant.misses = data["misses"]
            break

    return app_util.make_template_context(
        "jeopardy/contestant_game.html",
        active_player=str(contestant.disc_id),
        turn_id=contestant.index,
        nickname=contestant.name,
        avatar=contestant.avatar,
        color=contestant.color,
        score=contestant.score,
        buzzes=contestant.buzzes,
        hits=contestant.hits,
        misses=contestant.misses,
        ping=contestant.ping,
        player_bg_img=PLAYER_BACKGROUNDS[contestant.disc_id],
        **state_dict
    )

@app_util.socket_io.event
def ping_request(disc_id: str, timestamp: float):
    emit("ping_response", (disc_id, timestamp))

@app_util.socket_io.event
def calculate_ping(disc_id: str, timestamp_sent: float, timestamp_received: float):
    contestant: Contestant = flask.current_app.config["JEOPARDY_DATA"]["contestants"].get(int(disc_id))

    if contestant is not None:
        contestant.calculate_ping(timestamp_sent, timestamp_received)

        emit("ping_calculated", f"{min(999.0, max(contestant.ping, 1.0)):.1f}")

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
