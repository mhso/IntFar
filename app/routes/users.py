import flask
import api.util as api_util
from app.util import discord_request, make_template_context, format_bet_timestamp
from api.bets import get_dynamic_bet_desc, BETTING_DESC

user_page = flask.Blueprint("users", __name__, template_folder="templates")

@user_page.route("/")
@user_page.route("/unknown")
def user_unknown():
    return flask.render_template("no_user.html")

def get_intfar_relations_data(disc_id, database):
    relations_data = []
    games_relations, intfars_relations = database.get_intfar_relations(disc_id)
    for discord_id, total_games in games_relations.items():
        intfars = intfars_relations.get(discord_id, 0)
        relations_data.append(
            (discord_id, total_games, intfars, int((intfars / total_games) * 100))
        )

    relations_data.sort(key=lambda x: x[2], reverse=True)

    avatars = discord_request(
        "func", "get_discord_avatar", [x[0] for x in relations_data]
    )
    avatars = [
        flask.url_for("static", filename=avatar.replace("app/static/", ""))
        for avatar in avatars
    ]
    nicknames = discord_request(
        "func", "get_discord_nick", [x[0] for x in relations_data]
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
            ["Percent:", f"{pct_all:.2f}%", f"{pct_month:.2f}%"]
        ],
        "intfar_criteria_data": criteria_stats, "streak": longest_streak,
        "non_streak": longest_non_streak, "is_ifotm": user_is_ifotm,
        "most_intfars": max_intfar_id == disc_id
    }

def get_doinks_relations_data(disc_id, database):
    relations_data = []
    games_relations, doinks_relations = database.get_doinks_relations(disc_id)
    for discord_id, total_games in games_relations.items():
        doinks = doinks_relations.get(discord_id, 0)
        relations_data.append(
            (discord_id, total_games, doinks, int((doinks / total_games) * 100))
        )

    relations_data.sort(key=lambda x: x[2], reverse=True)

    avatars = discord_request(
        "func", "get_discord_avatar", [x[0] for x in relations_data]
    )
    avatars = [
        flask.url_for("static", filename=avatar.replace("app/static/", ""))
        for avatar in avatars
    ]
    nicknames = discord_request(
        "func", "get_discord_nick", [x[0] for x in relations_data]
    )
    full_data = [
        (x,) + y + (z,)
        for (x, y, z) in zip(nicknames, relations_data, avatars)
    ]

    return {"doinks_relations": full_data}

def get_doinks_data(disc_id, database):
    doinks_reason_ids = database.get_doinks_stats(disc_id)
    total_doinks = database.get_doinks_count(disc_id)[1]
    doinks_counts = api_util.organize_doinks_stats(doinks_reason_ids)
    criteria_stats = []
    for reason_id, reason in enumerate(api_util.DOINKS_REASONS):
        criteria_stats.append((reason, doinks_counts[reason_id]))

    max_doinks_id = database.get_max_doinks_details()[1]

    return {
        "doinks": total_doinks, "doinks_criteria_data": criteria_stats,
        "most_doinks": max_doinks_id == disc_id
    }

def get_bets(disc_id, database, only_active):
    bets = database.get_bets(only_active, disc_id)
    if bets is None:
        return []

    names = discord_request("func", "get_discord_nick", None)
    names_dict = dict(zip((x[0] for x in database.summoners), names))
    presentable_data = []

    for bet_ids, _, timestamp, amounts, events, targets, _, result_or_ticket, payout in bets:
        event_descs = [
            (
                i, get_dynamic_bet_desc(e, names_dict.get(t)),
                api_util.format_tokens_amount(a)
            )
            for (e, t, a, i) in zip(events, targets, amounts, bet_ids)
        ]
        bet_date = format_bet_timestamp(timestamp)
        presentable_data.append(
            (bet_date, event_descs, result_or_ticket, api_util.format_tokens_amount(payout))
        )
    presentable_data.sort(key=lambda x: x[1][0], reverse=True)
    return presentable_data

def get_betting_data(disc_id, database):
    database = flask.current_app.config["DATABASE"]

    resolved_bets = get_bets(disc_id, database, False)
    active_bets = get_bets(disc_id, database, True)
    bets = database.get_bets(False, disc_id)

    betting_stats = []
    bet_event_hi_freq = None
    bet_won_hi_freq = None
    bet_person_hi_freq = None

    if bets is not None:
        bets_won = 0
        total_amount = 0
        total_payout = 0
        highest_amount = 0
        highest_payout = 0
        events_counts = {x: 0 for x in BETTING_DESC}
        events_won_counts = {x: 0 for x in BETTING_DESC}
        target_counts = {d_id: 0 for d_id, _, _ in database.summoners}
        total_bets = 0

        for _, _, _, amounts, events, targets, _, result, payout in bets:
            amount_bet = 0
            for amount, event, target in zip(amounts, events, targets):
                amount_bet += amount
                total_bets += 1

                events_counts[event] += 1
                if target is not None and target != disc_id:
                    target_counts[target] += 1
                if result == 1:
                    events_won_counts[event] += 1

            if amount_bet > highest_amount:
                highest_amount = amount_bet
            total_amount += amount_bet

            if payout is not None:
                if payout > highest_payout:
                    highest_payout = payout

                total_payout += payout

            if result == 1:
                bets_won += 1

        most_often_event, most_often_event_count = max(events_counts.items(), key=lambda x: x[1])
        most_often_event_name = BETTING_DESC[most_often_event]

        most_won_event, most_won_event_count = max(events_won_counts.items(), key=lambda x: x[1])
        if most_won_event_count > 0:
            most_won_event_name = BETTING_DESC[most_won_event]
            most_won_even_desc = f"{most_won_event_name} ({most_won_event_count} times)"
        else:
            most_won_even_desc = "No bets won yet"

        most_often_target, most_often_target_count = max(target_counts.items(), key=lambda x: x[1])
        if most_often_target_count > 0:
            most_often_target_name = discord_request(
                "func", "get_discord_nick", most_often_target
            )
            most_often_target_desc = f"{most_often_target_name} ({most_often_target_count} times)"
        else:
            most_often_target_desc = "No one"

        pct_won = int((bets_won / len(bets)) * 100)

        betting_stats = [
            ("Bets made", len(bets)), ("Bets won", f"{bets_won} ({pct_won}%)"),
            ("Total points spent", api_util.format_tokens_amount(total_amount)),
            ("Biggest bet amount", api_util.format_tokens_amount(highest_amount)),
            ("Biggest payout", api_util.format_tokens_amount(highest_payout))
        ]
        bet_event_hi_freq = f"{most_often_event_name} ({most_often_event_count} times)"
        bet_won_hi_freq = most_won_even_desc
        bet_person_hi_freq = most_often_target_desc

    return {
        "resolved_bets": resolved_bets, "active_bets": active_bets,
        "betting_stats": betting_stats, "bet_event_hi_freq": bet_event_hi_freq,
        "bet_won_hi_freq": bet_won_hi_freq, "bet_person_hi_freq": bet_person_hi_freq

    }

def get_betting_tokens_data(disc_id, database):
    tokens = api_util.format_tokens_amount(database.get_token_balance(disc_id))
    max_tokens_holder = database.get_max_tokens_details()[1]
    return {
        "betting_tokens": tokens,
        "is_goodest_boi": max_tokens_holder == disc_id
    }

def get_game_stats(disc_id, database):
    best_stats = []
    any_gold_best = False
    worst_stats = []
    any_gold_worst = False
    for best in (True, False):
        for stat in api_util.STAT_COMMANDS:
            maximize = not ((stat != "deaths") ^ best)
            (stat_count,
             min_or_max_value,
             _) = database.get_stat(stat, best, disc_id, maximize)

            best_or_worst_ever_id = database.get_most_extreme_stat(stat, best, maximize)[0]
            stat_is_gold = best_or_worst_ever_id == disc_id
            if stat_is_gold:
                if best:
                    any_gold_best = True
                else:
                    any_gold_worst = True

            pretty_stat = stat.replace("_", " ").capitalize() if len(stat) > 3 else stat.upper()
            stat_index = api_util.STAT_COMMANDS.index(stat)
            quantity_type = 0 if best else 1
            pretty_quantity = api_util.STAT_QUANTITY_DESC[stat_index][quantity_type]
            if pretty_quantity is not None:
                pretty_desc = f"{pretty_quantity.capitalize()} {pretty_stat}"
            else:
                min_or_max_value = stat_count
                pretty_desc = pretty_stat

            if min_or_max_value is None:
                min_or_max_value = "NA"
            else:
                min_or_max_value = api_util.round_digits(min_or_max_value)

            if best:
                best_stats.append(
                    (
                        [pretty_desc, stat_count, min_or_max_value],
                        stat_is_gold
                    )
                )
            else:
                worst_stats.append(
                    (
                        [pretty_desc, stat_count, min_or_max_value],
                        stat_is_gold
                    )
                )

    return {
        "game_stats": [(best_stats, any_gold_best), (worst_stats, any_gold_worst)]
    }

@user_page.route("/<disc_id>")
def user(disc_id):
    if disc_id == "None":
        return flask.render_template("no_user.html")

    disc_id = int(disc_id)
    database = flask.current_app.config["DATABASE"]

    if not database.user_exists(disc_id):
        flask.abort(404)

    discord_data = discord_request(
        ["func", "func"], ["get_discord_nick", "get_discord_avatar"], [disc_id, (disc_id, 128)]
    )
    nickname = discord_data[0]
    avatar = discord_data[1]
    if avatar is not None:
        avatar = flask.url_for("static", filename=avatar.replace("app/static/", ""))

    database.start_persistent_connection()
    intfar_data = get_intfar_data(disc_id, database)
    intfar_relation_data = get_intfar_relations_data(disc_id, database)
    doinks_data = get_doinks_data(disc_id, database)
    doinks_relation_data = get_doinks_relations_data(disc_id, database)
    betting_data = get_betting_data(disc_id, database)
    tokens_data = get_betting_tokens_data(disc_id, database)
    game_stat_data = get_game_stats(disc_id, database)
    most_reports_id = database.get_max_reports_details()[1]
    database.close_persistent_connection()

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
    context.update(game_stat_data)

    return make_template_context("profile.html", **context)
