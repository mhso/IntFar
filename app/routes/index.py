from time import time
import flask
import api.util as api_util
from app.util import (
    discord_request, get_user_details, get_game_info, make_template_context, make_json_response
)
from api.bets import get_dynamic_bet_desc

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

def get_intfar_desc(game_data):
    _, _, disc_id, _, intfar_id, intfar_str = game_data
    response_list = None
    if disc_id == intfar_id:
        name = discord_request("func", "get_discord_nick", disc_id)
        response_list = [
            ("name", name), ("regular", "got"),
            ("feed-award", "Int-Far"), ("regular", "for")
        ]
        count = 0
        for i, c in enumerate(intfar_str):
            if c == "1":
                if count != 0:
                    response_list.append(("regular", "and"))
                response_list.append(("bold", api_util.INTFAR_REASONS[i]))
                count += 1
    return response_list

def get_doinks_desc(game_data):
    _, _, disc_id, doinks_str, _, _ = game_data
    response_list = None
    if doinks_str is not None:
        name = discord_request("func", "get_discord_nick", disc_id)
        response_list = [
            ("name", name), ("regular", "got"),
            ("feed-award", "Big Doinks"), ("regular", "for")
        ]
        count = 0
        for i, c in enumerate(doinks_str):
            if c == "1":
                if count != 0:
                    response_list.append(("regular", "and"))
                response_list.append(("bold", api_util.DOINKS_REASONS[i]))
                count += 1
    return response_list

def get_stat_desc(game_data, best_stats, worst_stats):
    game_id, _, disc_id, _, _, _ = game_data
    responses = []
    for i, stat_list in enumerate((best_stats, worst_stats)):
        for stat, person_id, stat_value, stat_game_id in stat_list:
            if stat_game_id == game_id and person_id == disc_id: # Best/worst stat was beaten.
                stat_index = api_util.STAT_COMMANDS.index(stat)
                readable_stat = api_util.STAT_QUANTITY_DESC[stat_index][i] + " " + stat
                name = discord_request("func", "get_discord_nick", disc_id)
                response_list = [
                    ("name", name), ("regular", "got the"), ("feed-award", readable_stat),
                    ("regular", "ever with"), ("bold", f"{stat_value} {stat}")
                ]
                responses.append(response_list)
    return responses

def get_game_desc(game_data, best_stats, worst_stats):
    duration = format_duration_approx(game_data[1])
    return (
        get_intfar_desc(game_data),
        get_doinks_desc(game_data),
        get_stat_desc(game_data, best_stats, worst_stats),
        duration
    )

def get_bet_desc(bet_data):
    disc_id, _, timestamp, amounts, events, targets, _, result, payout = bet_data
    name = discord_request("func", "get_discord_nick", disc_id)
    result_desc = "Won" if result == 1 else "Lost"
    tokens = (
        api_util.format_tokens_amount(payout) if result == 1
        else api_util.format_tokens_amount(sum(amounts))
    )
    response_list = [
        ("name", name), ("regular", result_desc), ("bold", f"{tokens} GBP"),
        ("regular", "by betting on")
    ]
    for i, (event, target) in enumerate(zip(events, targets)):
        target_name = (None if target is None
                       else discord_request("func", "get_discord_nick", target))
        dynamic_desc = get_dynamic_bet_desc(event, target_name)
        if i != 0:
            response_list.append(("regular", " and "))
        response_list.append(("bold", dynamic_desc))

    return response_list, format_duration_approx(timestamp)

def get_feed_data(database, feed_length=10):
    bets = database.get_bets(False)

    all_bets = []
    for disc_id in bets:
        for bet_data in bets[disc_id]:
            all_bets.append((disc_id,) + bet_data)

    all_bets.sort(key=lambda x: x[2])

    all_game_data = database.get_recent_intfars_and_doinks()
    best_stats_ever = []
    worst_stats_ever = []
    for best in (True, False):
        for stat in api_util.STAT_COMMANDS:
            maximize = not ((stat != "deaths") ^ best)
            stat_id, stat_value, game_id = database.get_most_extreme_stat(stat, best, maximize)
            if best:
                best_stats_ever.append((stat, stat_id, stat_value, game_id))
            else:
                worst_stats_ever.append((stat, stat_id, stat_value, game_id))

    feed_data = []
    bets_index = len(all_bets)-1
    games_index = len(all_game_data)-1

    while len(feed_data) < feed_length:
        game_data = all_game_data[games_index]
        bet_data = all_bets[bets_index]
        game_timestamp = game_data[1]
        bet_timestamp = bet_data[2]
        if game_timestamp > bet_timestamp:
            intfar_desc, doinks_desc, stat_descs, duration = get_game_desc(
                game_data, best_stats_ever, worst_stats_ever
            )
            if intfar_desc is not None:
                feed_data.append((intfar_desc, duration))
            if doinks_desc is not None:
                feed_data.append((doinks_desc, duration))
            for stat_desc in stat_descs:
                feed_data.append((stat_desc, duration))

            games_index -= 1
        else:
            bet_desc, duration = get_bet_desc(bet_data)
            if bet_desc is not None:
                feed_data.append((bet_desc, duration))
            bets_index -= 1

    return feed_data

@start_page.route('/')
@start_page.route('/index')
def index():
    database = flask.current_app.config["DATABASE"]
    curr_month = api_util.current_month()

    feed_descs = get_feed_data(database, feed_length=25)

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

    avatars = discord_request("func", "get_discord_avatar", None)
    if avatars is not None:
        avatars = [
            flask.url_for("static", filename=avatar.replace("app/static/", ""))
            for avatar in avatars
        ]
    nicknames = discord_request("func", "get_discord_nick", None)

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
        "index.html", curr_month=curr_month, feed_descs=feed_descs,
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

    saved_data = dict(data)
    del saved_data["secret"]
    saved_data["start"] = float(saved_data["start"])
    saved_data["map_id"] = int(saved_data["start"])

    flask.current_app.config["ACTIVE_GAME"] = saved_data
    print(f"SAVING ACTIVE GAME: {saved_data}", flush=True)
    return flask.make_response(("Success! Active game ID updated.", 200))

@start_page.route("/game_ended", methods=["POST"])
def active_game_ended():
    data = flask.request.form
    conf = flask.current_app.config["APP_CONFIG"]

    secret = data.get("secret")

    if secret != conf.discord_token:
        return flask.make_response(("Error: Unauthorized access.", 401))

    flask.current_app.config["ACTIVE_GAME"] = None
    print("REMOVING ACTIVE GAME", flush=True)
    return flask.make_response(("Success! Active game ID deleted.", 200))
