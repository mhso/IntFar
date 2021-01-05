import flask
import api.util as api_util
from app.util import discord_request, make_template_context
from api.bets import get_dynamic_bet_desc

user_page = flask.Blueprint("users", __name__, template_folder="templates")

@user_page.route("/")
@user_page.route("/unknown")
def user_unknown():
    return flask.render_template("no_user.html")

def get_intfar_relations_data(disc_id, bot_conn, database):
    relations_data = []
    games_relations, intfars_relations = database.get_intfar_relations(disc_id)
    for discord_id, total_games in games_relations.items():
        intfars = intfars_relations.get(discord_id, 0)
        relations_data.append(
            (discord_id, total_games, intfars, int((intfars / total_games) * 100))
        )

    relations_data.sort(key=lambda x: x[2], reverse=True)

    avatars = discord_request(
        bot_conn, "func", "get_discord_avatar", [x[0] for x in relations_data]
    )
    avatars = [
        flask.url_for("static", filename=avatar.replace("app/static/", ""))
        for avatar in avatars
    ]
    nicknames = discord_request(
        bot_conn, "func", "get_discord_nick", [x[0] for x in relations_data]
    )
    full_data = [
        (x,) + y + (z,)
        for (x, y, z) in zip(nicknames, relations_data, avatars)
    ]

    return {"intfar_relations": full_data}

def get_intfar_data(disc_id, database):
    curr_month = api_util.current_month()
    games_played, intfar_reason_ids = database.get_intfar_stats(disc_id, False)
    games_all, intfars_all, intfar_counts, pct_all = api_util.organize_intfar_stats(games_played, intfar_reason_ids)

    criteria_stats = []
    for reason_id, reason in enumerate(api_util.INTFAR_REASONS):
        criteria_stats.append((reason, intfar_counts[reason_id]))

    longest_streak = database.get_longest_intfar_streak(disc_id)
    longest_non_streak = database.get_longest_no_intfar_streak(disc_id)

    games_played, intfar_reason_ids = database.get_intfar_stats(disc_id, True)
    games_month, intfars_month, _, pct_month = api_util.organize_intfar_stats(games_played, intfar_reason_ids)

    intfars_of_the_month = database.get_intfars_of_the_month()
    user_is_ifotm = intfars_of_the_month != [] and intfars_of_the_month[0][0] == disc_id

    max_intfar_id = database.get_max_intfar_details()[1]

    return {
        "curr_month": curr_month,
        "intfar_data": [
            ["Games:", games_all, games_month],
            ["Intfars:", intfars_all, intfars_month],
            ["Percent:", f"{pct_all}%", f"{pct_month}%"]
        ],
        "intfar_criteria_data": criteria_stats, "streak": longest_streak,
        "non_streak": longest_non_streak, "is_ifotm": user_is_ifotm,
        "most_intfars": max_intfar_id == disc_id
    }

def get_doinks_relations_data(disc_id, bot_conn, database):
    relations_data = []
    games_relations, doinks_relations = database.get_doinks_relations(disc_id)
    for discord_id, total_games in games_relations.items():
        doinks = doinks_relations.get(discord_id, 0)
        relations_data.append(
            (discord_id, total_games, doinks, int((doinks / total_games) * 100))
        )

    relations_data.sort(key=lambda x: x[2], reverse=True)

    avatars = discord_request(
        bot_conn, "func", "get_discord_avatar", [x[0] for x in relations_data]
    )
    avatars = [
        flask.url_for("static", filename=avatar.replace("app/static/", ""))
        for avatar in avatars
    ]
    nicknames = discord_request(
        bot_conn, "func", "get_discord_nick", [x[0] for x in relations_data]
    )
    full_data = [
        (x,) + y + (z,)
        for (x, y, z) in zip(nicknames, relations_data, avatars)
    ]

    return {"doinks_relations": full_data}

def get_doinks_data(disc_id, database):
    doinks_reason_ids = database.get_doinks_stats(disc_id)
    doinks_counts = api_util.organize_doinks_stats(doinks_reason_ids)
    criteria_stats = []
    for reason_id, reason in enumerate(api_util.DOINKS_REASONS):
        criteria_stats.append((reason, doinks_counts[reason_id]))

    max_doinks_id = database.get_max_doinks_details()[1]

    return {
        "doinks": len(doinks_reason_ids), "doinks_criteria_data": criteria_stats,
        "most_doinks": max_doinks_id == disc_id
    }

def get_bets(disc_id, database, bot_conn, only_active):
    bets = database.get_bets(only_active, disc_id)
    if bets is None:
        return []

    names = discord_request(bot_conn, "func", "get_discord_nick", None)
    names_dict = dict(zip((x[0] for x in database.summoners), names))
    presentable_data = []

    for bet_ids, amounts, events, targets, _, result_or_ticket, payout in bets:
        event_descs = [(i, get_dynamic_bet_desc(e, names_dict.get(t)), a) for (e, t, a, i) in zip(events, targets, amounts, bet_ids)]
        presentable_data.append(
            (event_descs, result_or_ticket, payout)
        )
    presentable_data.sort(key=lambda x: x[0][0], reverse=True)
    return presentable_data

def get_betting_data(disc_id, database, bot_conn):
    resolved_bets = get_bets(disc_id, database, bot_conn, False)
    active_bets = get_bets(disc_id, database, bot_conn, True)
    return {
        "resolved_bets": resolved_bets,
        "active_bets": active_bets
    }

def get_betting_tokens_data(disc_id, database):
    tokens = database.get_token_balance(disc_id)
    max_tokens_holder = database.get_max_tokens_details()[1]
    return {
        "betting_tokens": tokens,
        "is_goodest_boi": max_tokens_holder == disc_id
    }

@user_page.route("/<disc_id>")
def user(disc_id):
    if disc_id == "None":
        return flask.render_template("no_user.html")

    disc_id = int(disc_id)

    database = flask.current_app.config["DATABASE"]
    bot_conn = flask.current_app.config["BOT_CONN"]

    discord_data = discord_request(
        bot_conn, "func", ["get_discord_nick", "get_discord_avatar"], disc_id
    )
    nickname = discord_data[0]
    avatar = discord_data[1]
    if avatar is not None:
        avatar = flask.url_for("static", filename=avatar.replace("app/static/", ""))

    intfar_data = get_intfar_data(disc_id, database)
    intfar_relation_data = get_intfar_relations_data(disc_id, bot_conn, database)
    doinks_data = get_doinks_data(disc_id, database)
    doinks_relation_data = get_doinks_relations_data(disc_id, bot_conn, database)
    betting_data = get_betting_data(disc_id, database, bot_conn)
    tokens_data = get_betting_tokens_data(disc_id, database)
    most_reports_id = database.get_max_reports_details()[1]

    context = {
        "disc_id": disc_id, "nickname": nickname, "avatar": avatar,
        "most_reports": most_reports_id == disc_id
    }
    context.update(intfar_data)
    context.update(intfar_relation_data)
    context.update(doinks_data)
    context.update(doinks_relation_data)
    context.update(betting_data)
    context.update(tokens_data)

    return make_template_context("profile.html", **context)
