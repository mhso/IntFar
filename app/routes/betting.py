from time import time
import flask
import app.util as app_util
import api.util as api_util
from api.betting import MAX_BETTING_THRESHOLD

betting_page = flask.Blueprint("betting", __name__, template_folder="templates")

def get_bets(game, database, only_active):
    bet_handler = flask.current_app.config["BET_HANDLERS"][game]
    all_bets = database.get_bets(game, only_active)
    names = app_util.discord_request("func", "get_discord_nick", None)
    avatars = app_util.discord_request("func", "get_discord_avatar", None)
    avatars = [
        flask.url_for("static", filename=avatar.replace("app/static/", ""))
        for avatar in avatars
    ]
    names_dict = dict(zip((x[0] for x in database.summoners), names))
    avatar_dict = dict(zip((x[0] for x in database.summoners), avatars))

    presentable_data = []
    for disc_id in all_bets:
        bets = all_bets[disc_id]

        for bet_ids, guild_id, timestamp, amounts, events, targets, _, result_or_ticket, payout in bets:
            event_descs = [
                (i, bet_handler.get_dynamic_bet_desc(e, names_dict.get(t)), api_util.format_tokens_amount(a))
                for (e, t, a, i) in zip(events, targets, amounts, bet_ids)
            ]

            bet_date = app_util.format_bet_timestamp(timestamp)
            guild_short = api_util.get_guild_abbreviation(guild_id)

            presentable_data.append(
                (
                    disc_id, names_dict[disc_id], bet_date, guild_short, str(guild_id), event_descs,
                    result_or_ticket, api_util.format_tokens_amount(payout), avatar_dict[disc_id]
                )
            )

    presentable_data.sort(key=lambda x: x[5][0][0], reverse=True)

    return presentable_data

@betting_page.route("/")
def home():
    game = flask.current_app.config["CURRENT_GAME"]
    database = flask.current_app.config["DATABASE"]
    betting_handler = flask.current_app.config["BET_HANDLERS"][game]

    resolved_bets = get_bets(game, database, False)
    active_bets = get_bets(game, database, True)
    logged_in_user = app_util.get_user_details()[0]

    all_events = [(bet.event_id, bet.event_id.replace("_", " ").capitalize()) for bet in betting_handler.all_bets]
    all_ids = list(database.users)
    all_names = app_util.discord_request("func", "get_discord_nick", None)
    all_avatars = app_util.discord_request("func", "get_discord_avatar", None)
    guild_names = app_util.discord_request("func", "get_guild_name", None)

    user_token_balance = "?"
    all_balances = database.get_token_balance()
    all_token_balances = []
    for balance, disc_id in all_balances:
        index = all_ids.index(disc_id)
        name = all_names[index]
        avatar = flask.url_for("static", filename=all_avatars[index].replace("app/static/", ""))
        formatted_balance = api_util.format_tokens_amount(balance)
        all_token_balances.append((disc_id, name, formatted_balance, avatar))

        if logged_in_user is not None and disc_id == logged_in_user:
            user_token_balance = formatted_balance

    all_guild_data = []
    if logged_in_user is not None:
        guilds_for_user = app_util.discord_request("func", "get_guilds_for_user", logged_in_user)
        for guild_id, guild_name in zip(api_util.GUILD_IDS, guild_names):
            if guild_id in guilds_for_user:
                all_guild_data.append((guild_id, guild_name))

    main_guild_id = flask.request.cookies.get("main_guild_id")
    if main_guild_id is None:
        main_guild_id = api_util.MAIN_GUILD_ID

    return app_util.make_template_context(
        "betting.html",
        game=game,
        resolved_bets=resolved_bets,
        active_bets=active_bets,
        bet_events=all_events,
        targets=list(zip(all_ids, all_names)),
        token_balance=user_token_balance,
        all_token_balances=all_token_balances,
        all_guild_data=all_guild_data,
        main_guild_id=main_guild_id
    )

@betting_page.route("/payout", methods=["POST"])
def get_payout():
    game = flask.current_app.config["CURRENT_GAME"]
    data = flask.request.get_json()
    betting_handler = flask.current_app.config["BET_HANDLERS"][game]

    events = data["events"]
    amounts = data["amounts"]
    targets = data["targets"]
    guild_id = data["guildId"]
    players = 1

    try:
        players = int(data["players"])
    except ValueError:
        pass

    game_start = app_util.discord_request("func", "get_game_start", [game, guild_id])
    duration = 0 if game_start is None else time() - game_start
    if duration > 60 * MAX_BETTING_THRESHOLD:
        return app_util.make_json_response("Error: Game is too far progressed to create bet bet amount value.", 400)

    total_reward = 0
    amounts_values = []
    for event, amount, target in zip(events, amounts, targets):
        target = None if target in ("invalid", "any") else target
        try:
            amount = api_util.parse_amount_str(amount)
        except ValueError:
            return app_util.make_json_response("Error: Invalid bet amount value.", 400)

        amounts_values.append(amount)

        value = betting_handler.get_bet_value(int(amount), event, duration, target)[0]
        if target is not None:
            value *= players

        total_reward += value

    return_data = {
        "cost": api_util.format_tokens_amount(sum(int(x) for x in amounts_values)),
        "payout": api_util.format_tokens_amount(int(total_reward * len(amounts_values)))
    }

    return app_util.make_json_response(return_data, 200)

@betting_page.route("/create", methods=["POST"])
def create_bet():
    game = flask.current_app.config["CURRENT_GAME"]
    data = flask.request.get_json()
    database = flask.current_app.config["DATABASE"]
    betting_handler = flask.current_app.config["BET_HANDLERS"][game]
    events = [int(x) for x in data["events"]]

    event_strs = []
    for event in events:
        for bet in betting_handler.all_bets:
            if bet.event_id == event:
                event_strs.append(bet.event_id)
                break

    amounts = data["amounts"]
    targets = [None if t in ("invalid", "any") else int(t) for t in data["targets"]]
    target_names = data["targetNames"]
    disc_id = data["disc_id"]
    guild_id = data["guildId"]

    logged_in_user, logged_in_name, logged_in_avatar = app_util.get_user_details()

    if disc_id is None or logged_in_user is None:
        return app_util.make_json_response("Error: You need to be logged in to place a bet.", 403)

    game_start = app_util.discord_request("func", "get_game_start", [game, guild_id])

    success, response, placed_bet_data = betting_handler.place_bet(
        int(disc_id),
        guild_id,
        amounts,
        game_start,
        event_strs,
        targets,
        target_names
    )

    if not success:
        return app_util.make_json_response(response, 400)

    bet_id, ticket = placed_bet_data
    new_balance = database.get_token_balance(disc_id)

    amounts = [api_util.parse_amount_str(amount) for amount in amounts]

    event_descs = [
        [betting_handler.get_dynamic_bet_desc(e, t), a] for (e, t, a) in zip(events, target_names, amounts)
    ]

    channel_name = app_util.discord_request("func", "get_channel_name", guild_id)

    bet_data = {
        "response": "Bet successfully placed!",
        "name": logged_in_name,
        "events": event_descs,
        "bet_type": "single" if ticket is None else "multi",
        "bet_id": bet_id,
        "ticket": ticket,
        "guild_id": guild_id,
        "guild_name": api_util.get_guild_abbreviation(int(guild_id)),
        "channel_name": channel_name,
        "avatar": logged_in_avatar,
        "betting_balance": new_balance
    }

    disc_msg = f"Gnarly, {logged_in_name}, you created a bet using the **I N T E R W E B Z**!!!\n"
    if bet_data["bet_type"] == "single":
        response = response.replace("Bet succesfully placed:", "You bet on")
    else:
        response = response.replace("Multi-bet successfully placed! ", "")
    disc_msg += response

    app_util.discord_request("func", "send_message_unprompted", (disc_msg, guild_id))

    return app_util.make_json_response(bet_data, 200)

@betting_page.route("/delete", methods=["POST"])
def delete_bet():
    game = flask.current_app.config["CURRENT_GAME"]
    data = flask.request.form
    betting_handler = flask.current_app.config["BET_HANDLERS"][game]
    conf = flask.current_app.config["APP_CONFIG"]

    disc_id = data["disc_id"]
    guild_id = int(data["guildId"])

    logged_in_user, logged_in_name, _ = app_util.get_user_details()

    if disc_id is None or logged_in_user is None:
        return app_util.make_json_response("Error: You need to be logged in to cancel a bet.", 403)

    ticket = None if data["betType"] == "single" else int(data["betId"])
    bet_id = None if data["betType"] == "multi" else int(data["betId"])

    game_start = app_util.discord_request("func", "get_game_start", [game, guild_id])

    success, cancel_data = betting_handler.delete_bet(int(disc_id), bet_id, ticket, game_start)

    if not success:
        return app_util.make_json_response(cancel_data, 400)

    new_balance, amount_refunded = cancel_data

    return_data = {
        "response": "Bet sucessfully cancelled.",
        "betting_balance": new_balance
    }

    tokens_name = conf.betting_tokens

    logged_in_name = app_util.get_user_details()[1]

    disc_msg = f"Stealthy! {logged_in_name} just cancelled a bet using the website!\n"
    refunded_formatted = api_util.format_tokens_amount(amount_refunded)
    if data["betType"] == "single":
        disc_msg += (
            f"Bet with ID {bet_id} for {refunded_formatted} "
            f"{tokens_name} successfully cancelled.\n"
        )
    else:
        disc_msg += (
            f"Multi-bet with ticket ID {ticket} for {refunded_formatted} " +
            f"{tokens_name} successfully cancelled.\n"
        )

    disc_msg += f"Your {tokens_name} balance is now `{api_util.format_tokens_amount(new_balance)}`."

    app_util.discord_request("func", "send_message_unprompted", (disc_msg, guild_id))

    return app_util.make_json_response(return_data, 200)
