import json
import flask
from api.util import current_month
from app.util import (
    discord_request, get_user_details, get_game_info, make_template_context, make_json_response
)

start_page = flask.Blueprint("index", __name__, template_folder="templates")

@start_page.route('/')
@start_page.route('/index')
def index():
    database = flask.current_app.config["DATABASE"]
    bot_conn = flask.current_app.config["BOT_CONN"]
    curr_month = current_month()

    intfar_all_data = []
    intfar_month_data = []
    for disc_id, _, _ in database.summoners:
        games_played, intfar_reason_ids = database.get_intfar_stats(disc_id)
        games_played_monthly, intfar_reason_ids_monthly = database.get_intfar_stats(disc_id, True)
        pct_intfar = (0 if games_played == 0
                      else int(len(intfar_reason_ids) / games_played * 100))
        pct_intfar_monthly = (0 if games_played_monthly == 0
                              else int(len(intfar_reason_ids_monthly) / games_played_monthly * 100))

        intfar_all_data.append(
            (disc_id, games_played, len(intfar_reason_ids), pct_intfar)
        )
        intfar_month_data.append(
            (disc_id, games_played_monthly, len(intfar_reason_ids_monthly), pct_intfar_monthly)
        )

    avatars = discord_request(bot_conn, "func", "get_discord_avatar", None)
    if avatars is not None:
        avatars = [
            flask.url_for("static", filename=avatar.replace("app/static/", ""))
            for avatar in avatars
        ]
    nicknames = discord_request(bot_conn, "func", "get_discord_nick", None)

    intfar_all_data = [
        (x,) + y + (z,)
        for (x, y, z) in zip(nicknames, intfar_all_data, avatars)
    ]
    intfar_month_data = [
        (x,) + y + (z,)
        for (x, y, z) in zip(nicknames, intfar_month_data, avatars)
    ]

    intfar_all_data.sort(key=lambda x: (x[3], x[4]), reverse=True)
    intfar_month_data.sort(key=lambda x: (x[3], x[4]), reverse=True)

    return make_template_context(
        "index.html", curr_month=curr_month,
        intfar_all=intfar_all_data, intfar_month=intfar_month_data
    )

@start_page.route("/active_game", methods=["GET"])
def get_active_game_info():
    logged_in_user = get_user_details()[0]

    if logged_in_user is None:
        return make_json_response("Error: You need to be verified to access this data.", 401)

    json_response = get_game_info()
    if json_response is None:
        return make_json_response("No active game", 404)

    return make_json_response(json_response, 200)

@start_page.route("/game_started", methods=["POST"])
def active_game_started():
    data = flask.request.form
    conf = flask.current_app.config["APP_CONFIG"]

    secret = data.get("secret")

    if secret != conf.discord_token:
        return flask.make_response(("Error: Unauthorized access.", 401))

    flask.current_app.config["ACTIVE_GAME"] = data.get("game_id")

@start_page.route("/game_ended", methods=["POST"])
def active_game_ended():
    data = flask.request.form
    conf = flask.current_app.config["APP_CONFIG"]

    secret = data.get("secret")

    if secret != conf.discord_token:
        return flask.make_response(("Error: Unauthorized access.", 401))

    flask.current_app.config["ACTIVE_GAME"] = None
    flask.current_app.config["GAME_START"] = None
