import json
from time import sleep, time
from os import remove
from os.path import exists

from mhooge_flask.logging import logger
import flask

import api.util as api_util
import app.util as app_util
from api.awards import get_intfar_reasons, get_doinks_reasons
from api.game_data import get_stat_quantity_descriptions
from discbot.commands.util import ADMIN_DISC_ID

start_page = flask.Blueprint("index", __name__, template_folder="templates")

def format_duration_approx(timestamp):
    time_now = time()
    duration = time_now - timestamp
    if duration < 60:
        metric = "sec"
    elif duration < 60 * 60:
        metric = "min"
        duration = duration / 60
    elif duration < 60 * 60 * 24:
        metric = "hour"
        duration = duration / (60 * 60)
    elif duration < 60 * 60 * 24 * 30:
        metric = "day"
        duration = duration / (60 * 60 * 24)
    else:
        metric = "month"
        duration = duration / (60 * 60 * 24 * 30)

    duration = int(duration)
    if duration > 1:
        metric = metric + "s"

    return f"{duration} {metric} ago"

def get_intfar_desc(game, game_data):
    _, _, disc_id, _, intfar_id, intfar_str = game_data
    intfar_reasons = get_intfar_reasons(game).values()
    response_list = None

    if disc_id == intfar_id:
        name = app_util.discord_request("func", "get_discord_nick", disc_id)
        response_list = [
            ("name", name), ("regular", "got"),
            ("feed-award", "Int-Far"), ("regular", "for")
        ]
        count = 0
        for reason, char in zip(intfar_reasons, intfar_str):
            if char == "1":
                if count != 0:
                    response_list.append(("regular", "and"))
                response_list.append(("bold", reason))
                count += 1

    return response_list

def get_doinks_desc(game, game_data):
    _, _, disc_id, doinks_str, _, _ = game_data
    doinks_reasons = get_doinks_reasons(game).values()
    response_list = None

    if doinks_str is not None:
        name = app_util.discord_request("func", "get_discord_nick", disc_id)
        response_list = [
            ("name", name), ("regular", "got"),
            ("feed-award", "Big Doinks"), ("regular", "for")
        ]
        count = 0
        for reason, char in zip(doinks_reasons, doinks_str):
            if char == "1":
                if count != 0:
                    response_list.append(("regular", "and"))
                response_list.append(("bold", reason))
                count += 1

    return response_list

def get_stat_desc(game, game_data, best_stats, worst_stats):
    game_id, _, disc_id, _, _, _ = game_data
    responses = []
    stats = get_stat_quantity_descriptions(game)
    for i, stat_list in enumerate((best_stats, worst_stats)):
        for stat, person_id, stat_value, stat_game_id in stat_list:
            if stat_game_id == game_id and person_id == disc_id: # Best/worst stat was beaten.
                stat_fmt = api_util.round_digits(stat_value)
                stat_name_fmt = stat.replace("_", " ")
                readable_stat = stats[stat][i] + " " + stat_name_fmt
                name = app_util.discord_request("func", "get_discord_nick", disc_id)
                response_list = [
                    ("name", name), ("regular", "got the"), ("feed-award", readable_stat),
                    ("regular", "ever with"), ("bold", f"{stat_fmt} {stat_name_fmt}")
                ]
                responses.append(response_list)
    return responses

def get_game_desc(game, game_data, best_stats, worst_stats):
    duration = format_duration_approx(game_data[1])
    return (
        get_intfar_desc(game, game_data),
        get_doinks_desc(game, game_data),
        get_stat_desc(game, game_data, best_stats, worst_stats),
        duration
    )

def get_bet_desc(game, bet_data):
    betting_handler = flask.current_app.config["BET_HANDLERS"][game]
    disc_id, _, guild_id, timestamp, amounts, events, targets, _, result, payout = bet_data
    disc_data = app_util.discord_request("func", ["get_discord_nick", "get_guild_name"], [disc_id, guild_id])
    name = disc_data[0]
    guild = disc_data[1]
    result_desc = "Won" if result == 1 else "Lost"
    tokens = (
        api_util.format_tokens_amount(payout) if result == 1
        else api_util.format_tokens_amount(sum(amounts))
    )
    response_list = [
        ("name", name), ("regular", result_desc), ("bold", f"{tokens} GBP"),
        ("regular", "in"), ("bold", guild), ("regular", "by betting on")
    ]
    for i, (event, target) in enumerate(zip(events, targets)):
        target_name = (
            None if target is None
            else app_util.discord_request("func", "get_discord_nick", target)
        )
        dynamic_desc = betting_handler.get_dynamic_bet_desc(event, target_name)
        if i != 0:
            response_list.append(("regular", " and "))
        response_list.append(("bold", dynamic_desc))

    return response_list, format_duration_approx(timestamp)

def get_feed_data(game, database, feed_length=10):
    bets = database.get_bets(game, False)

    all_bets = []
    for disc_id in bets:
        for bet_data in bets[disc_id]:
            all_bets.append((disc_id,) + bet_data)

    all_bets.sort(key=lambda x: x[3])

    all_game_data = database.get_recent_intfars_and_doinks(game)
    best_stats_ever = []
    worst_stats_ever = []

    stats = get_stat_quantity_descriptions(game)

    for best in (True, False):
        for stat in stats:
            maximize = not ((stat != "deaths") ^ best)
            stat_id, stat_value, game_id = database.get_most_extreme_stat(game, stat, maximize)
            if best:
                best_stats_ever.append((stat, stat_id, stat_value, game_id))
            else:
                worst_stats_ever.append((stat, stat_id, stat_value, game_id))

    feed_data = []
    bets_index = len(all_bets) - 1
    games_index = len(all_game_data) - 1

    while len(feed_data) < feed_length:
        game_data = all_game_data[games_index]
        bet_data = all_bets[bets_index]
        game_timestamp = game_data[1]
        bet_timestamp = bet_data[3]
        if game_timestamp > bet_timestamp:
            intfar_desc, doinks_desc, stat_descs, duration = get_game_desc(
                game, game_data, best_stats_ever, worst_stats_ever
            )
            if intfar_desc is not None:
                feed_data.append((intfar_desc, duration))
            if doinks_desc is not None:
                feed_data.append((doinks_desc, duration))
            for stat_desc in stat_descs:
                feed_data.append((stat_desc, duration))

            games_index -= 1
        else:
            bet_desc, duration = get_bet_desc(game, bet_data)
            if bet_desc is not None:
                feed_data.append((bet_desc, duration))
            bets_index -= 1

    return feed_data

@start_page.route("/")
@start_page.route("/index")
def index():
    game = flask.current_app.config["CURRENT_GAME"]

    if game == "csgo":
        return app_util.make_template_context("under_construction.html", 200)

    database = flask.current_app.config["DATABASE"]
    curr_month = api_util.current_month()

    feed_descs = get_feed_data(game, database, feed_length=25)

    intfar_all_data = {}
    intfar_month_data = {}
    for disc_id in database.users_by_game[game]:
        games_played, intfar_reason_ids = database.get_intfar_stats(game, disc_id)
        games_played_monthly, intfar_reason_ids_monthly = database.get_intfar_stats(game, disc_id, True)
        pct_intfar = (
            0 if games_played == 0
            else len(intfar_reason_ids) / games_played * 100
        )
        pct_intfar_monthly = (
            0 if games_played_monthly == 0
            else len(intfar_reason_ids_monthly) / games_played_monthly * 100
        )

        intfar_all_data[disc_id] = (
            games_played, len(intfar_reason_ids), f"{pct_intfar:.2f}"
        )
        intfar_month_data[disc_id] = (
            games_played_monthly, len(intfar_reason_ids_monthly), f"{pct_intfar_monthly:.2f}"
        )

    avatars = app_util.discord_request("func", "get_discord_avatar", None)
    if not avatars:
        sleep(1)
        avatars = app_util.discord_request("func", "get_discord_avatar", None)

    if avatars:
        avatars = {
            disc_id: flask.url_for("static", filename=avatars[disc_id].replace("app/static/", ""))
            for disc_id in avatars
        }
    nicknames = app_util.discord_request("func", "get_discord_nick", None)

    intfar_all_data = [
        (nicknames[disc_id], disc_id) + intfar_all_data[disc_id] + (avatars[disc_id],)
        for disc_id in intfar_all_data
    ]
    intfar_month_data = [
        (nicknames[disc_id], disc_id) + intfar_month_data[disc_id] + (avatars[disc_id],)
        for disc_id in intfar_month_data
    ]

    intfar_all_data.sort(key=lambda x: (x[3], x[4]), reverse=True)
    intfar_month_data.sort(key=lambda x: (x[3], x[4]), reverse=True)

    return app_util.make_template_context(
        "index.html",
        curr_month=curr_month,
        feed_descs=feed_descs,
        intfar_all=intfar_all_data,
        intfar_month=intfar_month_data
    )

@start_page.route("active_game", methods=["GET"])
def get_active_game_info():
    game = flask.current_app.config["CURRENT_GAME"]
    logged_in_user = app_util.get_user_details()[0]

    if logged_in_user is None:
        return app_util.make_json_response("Error: You need to be verified to access this data.", 401)

    json_response = app_util.get_game_info(game)

    shown_games = app_util.filter_hidden_games(json_response, logged_in_user)

    if shown_games == []:
        return app_util.make_json_response("No active game", 404)

    return app_util.make_json_response(shown_games, 200)

@start_page.route("game_started", methods=["POST"])
def active_game_started():
    game = flask.current_app.config["CURRENT_GAME"]
    data = flask.request.form
    conf = flask.current_app.config["APP_CONFIG"]

    secret = data.get("secret")

    # Verify that the request contains the Discord App Token (that is only known by us).
    if secret != conf.discord_token:
        return flask.make_response(("Error: Unauthorized access.", 401))

    saved_data = dict(data)
    del saved_data["secret"]
    saved_data["start"] = float(saved_data["start"])
    saved_data["map_id"] = int(saved_data["map_id"])
    saved_data["guild_id"] = int(saved_data["guild_id"])

    flask.current_app.config["ACTIVE_GAME"][saved_data["guild_id"]][game] = saved_data
    return flask.make_response(("Success! Active game ID updated.", 200))

@start_page.route("game_ended", methods=["POST"])
def active_game_ended():
    game = flask.current_app.config["CURRENT_GAME"]
    data = flask.request.form
    conf = flask.current_app.config["APP_CONFIG"]

    secret = data.get("secret")

    # Verify that the request contains the Discord App Token (that is only known by us).
    if secret != conf.discord_token:
        return flask.make_response(("Error: Unauthorized access.", 401))

    flask.current_app.config["ACTIVE_GAME"][int(data["guild_id"])][game] = None

    if flask.current_app.config["GAME_PREDICTION"].get(int(data["game_id"])) is not None:
        remove("resources/predictions_temp.json")

    flask.current_app.config["GAME_PREDICTION"][int(data["game_id"])] = None

    return flask.make_response(("Success! Active game ID deleted.", 200))

@start_page.route("/heartbeat")
def heartbeat():
    if flask.current_app.config["EXIT_CODE"] != 0:
        return app_util.make_text_response("Restarting", 503)

    return app_util.make_text_response("Alive and kicking!", 200)

@start_page.route("/restart", methods=["POST"])
def restart():
    logged_in_user = app_util.get_user_details()[0]

    if logged_in_user is None or logged_in_user != ADMIN_DISC_ID:
        return app_util.make_text_response("Unathorized Access.", 401)

    flask.current_app.config["EXIT_CODE"] = 2

    exit(2)

def save_prediction_to_file(prediction, game_duration):
    filename = "resources/predictions_temp.json"
    if exists(filename):
        snapshot_json = json.load(open(filename, "r", encoding="utf-8"))
    else:
        snapshot_json = {"predictions": []}

    snapshot_json["predictions"].append({
        "timestamp": game_duration,
        "prediction": prediction
    })

    json.dump(snapshot_json, open(filename, "w", encoding="utf-8"), indent=4)

@start_page.route("/update_prediction", methods=["POST"])
def set_prediction():
    data = flask.request.form
    conf = flask.current_app.config["APP_CONFIG"]

    secret = data.get("secret")

    # Verify that the request contains the Discord App Token (that is only known by us).
    if secret != conf.discord_token:
        return flask.make_response(("Error: Unauthorized access.", 401))

    game_id = int(data["game_id"])

    logger.info(f"Updated game prediction: {data['pct_win']}% chance of winning.")

    save_prediction_to_file(data["pct_win"], int(data["game_duration"]))

    flask.current_app.config["GAME_PREDICTION"][game_id] = data["pct_win"]

    return flask.make_response(("Success! Game prediction updated.", 200))

@start_page.route("/prediction", methods=["GET"])
def get_prediction():
    data = flask.request.args
    game_id = data.get("game_id")

    if game_id is None:
        return app_util.make_json_response("Error: Missing parameter 'game_id'.", 400)

    pct_win = flask.current_app.config["GAME_PREDICTION"].get(int(game_id))

    if pct_win is None:
        return app_util.make_json_response("Error: No prediction exists.", 404)

    return app_util.make_json_response(pct_win, 200)
