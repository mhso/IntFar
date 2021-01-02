from time import time
import json
import flask
from app.util import get_discord_data
from api.bets import get_dynamic_bet_desc, BETTING_IDS, MAX_BETTING_THRESHOLD
from app.user import get_user_details

betting_page = flask.Blueprint("betting", __name__, template_folder="templates")

def get_bets(bot_conn, database, only_active):
    all_bets = database.get_active_bets() if only_active else database.get_all_bets()
    names = get_discord_data(bot_conn, "func", "get_discord_nick", None)
    avatars = get_discord_data(bot_conn, "func", "get_discord_avatar", None)
    avatars = [
        flask.url_for("static", filename=avatar.replace("app/static/", ""))
        for avatar in avatars
    ]
    names_dict = dict(zip((x[0] for x in database.summoners), names))
    avatar_dict = dict(zip((x[0] for x in database.summoners), avatars))
    presentable_data = []
    for disc_id in all_bets:
        bets = all_bets[disc_id]
        reformatted = [x + (None,) for x in bets] if only_active else bets
        for bet_ids, amounts, events, targets, _, result_or_ticket, payout in reformatted:
            event_descs = [(i, get_dynamic_bet_desc(e, names_dict.get(t)), a) for (e, t, a, i) in zip(events, targets, amounts, bet_ids)]
            presentable_data.append(
                (disc_id, names_dict[disc_id], event_descs, result_or_ticket, payout, avatar_dict[disc_id])
            )
    presentable_data.sort(key=lambda x: x[2][0][0], reverse=True)
    return presentable_data

@betting_page.route('/')
def home():
    database = flask.current_app.config["DATABASE"]
    bot_conn = flask.current_app.config["BOT_CONN"]
    resolved_bets = get_bets(bot_conn, database, False)
    active_bets = get_bets(bot_conn, database, True)
    logged_in_user, logged_in_name, logged_in_avatar = get_user_details()

    all_events = [(bet_id, bet_id.replace("_", " ").capitalize()) for bet_id in BETTING_IDS]
    all_ids = [x[0] for x in database.summoners]
    all_names = get_discord_data(bot_conn, "func", "get_discord_nick", None)

    token_balance = "?"
    if logged_in_user is not None:
        token_balance = database.get_token_balance(logged_in_user)

    return flask.render_template(
        "betting.html", resolved_bets=resolved_bets,
        active_bets=active_bets, bet_events=all_events, targets=list(zip(all_ids, all_names)),
        token_balance=token_balance, logged_in_user=logged_in_user,
        logged_in_name=logged_in_name, logged_in_avatar=logged_in_avatar
    )

def get_response(text, code, data=None):
    json_response = {
        "response": text
    }
    if data is not None:
        json_response["data"] = data

    resp = flask.Response(response=json.dumps(json_response), status=code, mimetype="application/json")
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp

@betting_page.route("/payout", methods=["POST"])
def get_payout():
    data = flask.request.get_json()
    betting_handler = flask.current_app.config["BET_HANDLER"]
    bot_conn = flask.current_app.config["BOT_CONN"]
    events = data["events"]
    amounts = data["amounts"]
    targets = data["targets"]
    players = 1
    try:
        players = int(data["players"])
    except ValueError:
        pass

    game_start = get_discord_data(bot_conn, "func", "get_game_start", None)
    duration = 0 if game_start is None else time() - game_start
    if duration > 60 * MAX_BETTING_THRESHOLD:
        return get_response("Error: Game is too far progressed to create bet bet amount value.", 400)

    total_reward = 0
    for event, amount, target in zip(events, amounts, targets):
        target = None if target in ("invalid", "any") else target
        try:
            amount = int(amount)
        except ValueError:
            return get_response("Error: Invalid bet amount value.", 400)

        value = betting_handler.get_bet_value(int(amount), int(event), duration, target)[0]
        if target is not None:
            value *= players

        total_reward += value

    return_data = {
        "cost": sum(int(x) for x in amounts),
        "payout": int(total_reward * len(amounts))
    }
    return get_response("", 200, return_data)

@betting_page.route("/create", methods=["POST"])
def create_bet():
    data = flask.request.get_json()
    database = flask.current_app.config["DATABASE"]
    betting_handler = flask.current_app.config["BET_HANDLER"]
    bot_conn = flask.current_app.config["BOT_CONN"]
    events = [int(x) for x in data["events"]]
    event_strs = []
    for event in events:
        for x in BETTING_IDS:
            if BETTING_IDS[x] == event:
                event_strs.append(x)
                break

    amounts = data["amounts"]
    targets = [None if t in ("invalid", "any") else int(t) for t in data["targets"]]
    target_names = data["targetNames"]
    disc_id = data["disc_id"]

    if disc_id is None:
        return get_response("Error: You need to be logged in to place a bet.", 403)

    game_start = get_discord_data(bot_conn, "func", "get_game_start", None)

    success, response, placed_bet_data = betting_handler.place_bet(
        int(disc_id), amounts, game_start, event_strs, targets, target_names
    )

    if not success:
        return get_response(response, 400)

    bet_id, ticket = placed_bet_data
    new_balance = database.get_token_balance(disc_id)

    event_descs = [
        [get_dynamic_bet_desc(e, t), a] for (e, t, a) in zip(events, target_names, amounts)
    ]
    _, logged_in_name, logged_in_avatar = get_user_details()

    bet_data = {
        "name": logged_in_name, "events": event_descs,
        "bet_type": "single" if ticket is None else "multi",
        "bet_id": bet_id, "ticket": ticket,
        "avatar": logged_in_avatar, "betting_balance": new_balance
    }

    return get_response("Bet successfully placed!", 200, data=bet_data)

@betting_page.route("/delete", methods=["POST"])
def delete_bet():
    data = flask.request.form
    betting_handler = flask.current_app.config["BET_HANDLER"]
    bot_conn = flask.current_app.config["BOT_CONN"]

    disc_id = data["disc_id"]

    if disc_id is None:
        return get_response("Error: You need to be logged in to cancel a bet.", 403)

    ticket = None if data["betType"] == "single" else int(data["betId"])
    bet_id = None if data["betType"] == "multi" else int(data["betId"])

    game_start = get_discord_data(bot_conn, "func", "get_game_start", None)

    success, data = betting_handler.delete_bet(int(disc_id), bet_id, ticket, game_start)

    if not success:
        return get_response(data, 400)

    new_balance = data[0]

    return_data = {
        "betting_balance": new_balance
    }

    return get_response("Bet sucessfully cancelled.", 200, data=return_data)
