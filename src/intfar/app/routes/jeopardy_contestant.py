import flask
from flask_socketio import emit

from mhooge_flask.routing import socket_io

from intfar.app import util as app_util
from intfar.app.routes.jeopardy_presenter import BUZZ_IN_SOUNDS, PLAYER_NAMES, PLAYER_INDEXES, PLAYER_BACKGROUNDS, Contestant

jeopardy_contestant_page = flask.Blueprint("jeopardy_contestant", __name__, template_folder="templates")

@jeopardy_contestant_page.route("/")
def home():
    if "jeopardy_user_id" in flask.request.cookies:
        return flask.redirect(flask.url_for(".game_view", _external=True))

    return flask.abort(404)

@jeopardy_contestant_page.route("/join", methods=["POST"])
def join_lobby():
    name = flask.request.form.get("name")
    disc_id = int(flask.request.form.get("user_id"))
    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    state = jeopardy_data["state"]
    config = flask.current_app.config["APP_CONFIG"]

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
        avatar = flask.url_for("static", _external=True, filename=app_util.get_relative_static_folder(avatar, config))
    else:
        avatar = flask.url_for("static", _external=True, filename="img/questionmark.png")

    turn_id = PLAYER_INDEXES.index(disc_id)
    with flask.current_app.config["JEOPARDY_JOIN_LOCK"]:
        active_contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]
        active_contestants[disc_id] = Contestant(disc_id, turn_id, name, avatar, color)

    response = flask.redirect(flask.url_for(".game_view", _external=True))
    max_age = 60 * 60 * 6 # 6 hours
    response.set_cookie("jeopardy_user_id", str(disc_id), max_age=max_age)

    return response

@jeopardy_contestant_page.route("/game")
def game_view():
    if "jeopardy_user_id" not in flask.request.cookies:
        return flask.redirect(flask.url_for(".lobby", _external=True, client_secret="None"))

    state = flask.current_app.config["JEOPARDY_DATA"]["state"]

    if state is None:
        return app_util.make_template_context("jeopardy/contestant_nogame.html")

    active_contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]
    disc_id = int(flask.request.cookies["jeopardy_user_id"])
    contestant: Contestant = active_contestants[disc_id]

    state_dict = state.__dict__

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
        power_ups=[power_up.__dict__ for power_up in contestant.power_ups],
        finale_wager=contestant.finale_wager,
        player_bg_img=PLAYER_BACKGROUNDS[contestant.disc_id],
        **state_dict
    )

@jeopardy_contestant_page.route("/<client_secret>")
def lobby(client_secret):
    config = flask.current_app.config["APP_CONFIG"]
    database = flask.current_app.config["DATABASE"]

    if client_secret is None or client_secret == "None":
        return flask.abort(404)

    disc_id = database.get_user_from_secret(client_secret)

    if disc_id is None or int(disc_id) not in PLAYER_NAMES:
        return flask.abort(404)

    base_url = "https://mhooge.com:5006" if config.env == "production" else "http://localhost:5006"
    join_url = f"{base_url}/jeoparty/join"

    join_code = "lan_jeopardy_v6"
    password = "lan_jeoparty_wohooo"

    avatar = app_util.discord_request("func", "get_discord_avatar", disc_id)
    if avatar:
        avatar = flask.url_for("static", _external=True, filename=app_util.get_relative_static_folder(avatar, config))

    bg_image = PLAYER_BACKGROUNDS[disc_id]
    buzz_sound = BUZZ_IN_SOUNDS[disc_id]

    return app_util.make_template_context(
        "jeopardy/contestant_lobby.html",
        join_url=join_url,
        join_code=join_code,
        password=password,
        user_id=str(disc_id),
        player_name=PLAYER_NAMES[disc_id],
        avatar=avatar,
        bg_image=bg_image,
        buzz_sound=buzz_sound,
    )

@socket_io.event
def ping_request(disc_id: str, timestamp: float):
    emit("ping_response", (disc_id, timestamp))

@socket_io.event
def calculate_ping(disc_id: str, timestamp_sent: float, timestamp_received: float):
    contestant: Contestant = flask.current_app.config["JEOPARDY_DATA"]["contestants"].get(int(disc_id))

    if contestant is not None:
        contestant.calculate_ping(timestamp_sent, timestamp_received)

        emit("ping_calculated", f"{min(999.0, max(contestant.ping, 1.0)):.1f}")

@socket_io.event
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

@socket_io.event
def make_finale_wager(disc_id: str, amount: str):
    disc_id = int(disc_id)
    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    contestant: Contestant = jeopardy_data["contestants"][int(disc_id)]

    max_wager = max(contestant.score, 1000)

    try:
        amount = int(amount)
    except ValueError:
        emit("invalid_wager", max_wager)
        return

    if 0 <= amount <= max_wager:
        print(f"Made finale wager for {disc_id} (#{contestant.index}) for {amount} points")
        contestant.finale_wager = amount
        emit("finale_wager_made")
        emit("contestant_ready", contestant.index, to="presenter")
    else:
        emit("invalid_wager", max_wager)

@socket_io.event
def give_finale_answer(disc_id: str, answer: str):
    contestant: Contestant = flask.current_app.config["JEOPARDY_DATA"]["contestants"][int(disc_id)]
    contestant.finale_answer = answer

    emit("finale_answer_given")
    emit("contestant_ready", contestant.index, to="presenter")
