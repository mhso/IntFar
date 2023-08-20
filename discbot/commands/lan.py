from datetime import datetime
from time import time

import api.lan as lan_api
import api.util as api_util
from api.awards import get_intfar_reasons, get_doinks_reasons, organize_intfar_stats, organize_doinks_stats

_GAME = "lol"

async def send_lan_not_started_msg(client, message):
    now_dt = datetime.now()
    lan_start = lan_api.LAN_PARTIES[lan_api.LATEST_LAN_PARTY].start_time
    lan_dt = datetime.fromtimestamp(lan_start)
    duration = api_util.format_duration(now_dt, lan_dt)
    response = f"LAN is starting in `{duration}`! Check back then for cool stats " + "{emote_nazi}"
    await message.channel.send(client.insert_emotes(response))

async def handle_lan_msg(client, message):
    lan_party = lan_api.LAN_PARTIES[lan_api.LATEST_LAN_PARTY]
    if time() < lan_party.start_time:
        await send_lan_not_started_msg(client, message)
        return

    # General info about how the current LAN is going.
    games_stats = client.database.get_games_count(
        _GAME, time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
    )

    if games_stats is None:
        response = "No games have been played yet!"
    else:
        games_played, first_game_timestamp, games_won, _ = games_stats
        pct_won = (games_won / games_played) * 100

        dt_start = datetime.fromtimestamp(first_game_timestamp)
        dt_now = datetime.now()
        if dt_now.timestamp() > lan_party.end_time:
            dt_now = datetime.fromtimestamp(lan_party.end_time)

        duration = api_util.format_duration(dt_start, dt_now)

        champs_played = client.database.get_league_champs_played(
            time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
        )

        intfars = client.database.get_intfar_count(
            _GAME, time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
        )
        doinks = client.database.get_doinks_count(
            _GAME, time_after=lan_party.start_time, time_before=lan_party.end_timeE, guild_id=lan_party.guild_id
        )[1]

        longest_game_duration, longest_game_time = client.database.get_longest_game(
            _GAME, time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
        )
        longest_game_start = datetime.fromtimestamp(longest_game_time)
        longest_game_end = datetime.fromtimestamp(longest_game_time + longest_game_duration)
        longest_game = api_util.format_duration(longest_game_start, longest_game_end)

        response = (
            "At this LAN:\n" +
            f"- We have been clapping cheeks for **{duration}**\n" +
            f"- **{games_played}** games have been played (**{pct_won:.2f}%** was won)\n" +
            f"- **{intfars}** Int-Far awards have been given\n"
            f"- **{doinks}** Doinks have been awarded\n"
            f"- **{champs_played}** unique champs have been played\n"
            f"- **{longest_game}** was the duration of the longest game"
        )

    await message.channel.send(response)

async def handle_lan_performance_msg(client, message, target_id):
    lan_party = lan_api.LAN_PARTIES[lan_api.LATEST_LAN_PARTY]
    if time() < lan_party.start_time:
        await send_lan_not_started_msg(client, message)
        return

    # Info about various stats for a person at the current LAN.
    all_avg_stats, all_ranks = lan_api.get_average_stats(client.database)

    if all_avg_stats is None:
        response = "No games have yet been played at this LAN."
        await message.channel.send(response)
        return

    name = client.get_discord_nick(target_id, message.guild.id)

    response = f"At this LAN, {name} has the following average stats:"

    for stat_name in all_avg_stats:
        stats = all_avg_stats[stat_name]

        user_value = None
        user_rank = 0
        for index, (disc_id, stat_value) in enumerate(stats):
            if disc_id == target_id:
                if stat_name in ("Damage to champs", "Gold earned"):
                    stat_value = int(stat_value)
                user_value = api_util.round_digits(stat_value)
                user_rank = index + 1

        response += f"\n{stat_name}: **{user_value}** (rank **{user_rank}**/**5**)"

    user_total_rank = 0
    for index, rank_data in enumerate(all_ranks):
        if rank_data[0] == target_id:
            user_total_rank = index + 1
            break

    response += "\n---------------------------------------------"
    response += f"\nTotal rank: **{user_total_rank}**/**5**"

    await message.channel.send(response)

async def send_tally_messages(client, message, messages, event_name, for_all):
    response = f"{event_name} awarded at this LAN:" if for_all else "At this LAN, "
    for data in messages:
        if for_all:
            response += "\n- "
        response += f"{data[0]}"

    await message.channel.send(client.insert_emotes(response))

def format_intfar(client, message, disc_id, expanded):
    lan_party = lan_api.LAN_PARTIES[lan_api.LATEST_LAN_PARTY]
    person_to_check = client.get_discord_nick(disc_id, message.guild.id)

    games_played, intfar_reason_ids = client.database.get_intfar_stats(
        _GAME, disc_id, time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
    )
    games_played, intfars, intfar_counts, pct_intfar = organize_intfar_stats(_GAME, games_played, intfar_reason_ids)

    if expanded:
        msg = f"{person_to_check} has been "
    else:
        msg = f"{person_to_check}: "

    msg += f"Int-Far **{intfars}** time"
    if intfars != 1:
        msg += "s"
    msg += f" **({pct_intfar:.2f}%** of {games_played} games) "

    intfar_reasons = get_intfar_reasons(_GAME)

    if expanded and intfars > 0:
        msg += "\nInt-Fars awarded so far:"
        for reason_id, reason in enumerate(intfar_reasons.values()):
            msg += f"\n- {reason}: **{intfar_counts[reason_id]}**"

    return msg, intfars, pct_intfar

async def handle_lan_intfar_msg(client, message, target_id=None):
    lan_party = lan_api.LAN_PARTIES[lan_api.LATEST_LAN_PARTY]
    if time() < lan_party.start_time:
        await send_lan_not_started_msg(client, message)
        return

    targets = lan_party.participants if target_id is None else [target_id]
    messages = []
    for target in targets:
        resp_str, intfars, pct = format_intfar(client, message, target, target_id is not None)
        messages.append((resp_str, intfars, pct))
    
    messages.sort(key=lambda x: (x[1], x[2]), reverse=True)

    await send_tally_messages(client, message, messages, "Int-Fars", target_id is None)

def format_doinks(client, message, disc_id, expanded):
    lan_party = lan_api.LAN_PARTIES[lan_api.LATEST_LAN_PARTY]
    person_to_check = client.get_discord_nick(disc_id, message.guild.id)

    doinks_reason_ids = client.database.get_doinks_stats(
        _GAME, disc_id, time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
    )
    total_doinks = client.database.get_doinks_count(
        _GAME, disc_id, time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
    )[1]
    doinks_counts = organize_doinks_stats(_GAME, doinks_reason_ids)

    if expanded:
        msg = f"{person_to_check} has earned "
    else:
        msg = f"{person_to_check}: "

    msg += f"{total_doinks} " + "{emote_Doinks}"

    doinks_reasons = get_doinks_reasons(_GAME)

    if expanded and total_doinks > 0:
        msg += "\nBig doinks awarded so far:"
        for reason_id, reason in enumerate(doinks_reasons):
            msg += f"\n - {reason}: **{doinks_counts[reason_id]}**"
    return msg, total_doinks

async def handle_lan_doinks_msg(client, message, target_id=None):
    lan_party = lan_api.LAN_PARTIES[lan_api.LATEST_LAN_PARTY]
    if time() < lan_party.start_time:
        await send_lan_not_started_msg(client, message)
        return

    targets = lan_party.participants if target_id is None else [target_id]
    messages = []
    for target in targets:
        resp_str, doinks = format_doinks(client, message, target, target_id is not None)
        messages.append((resp_str, doinks))

    messages.sort(key=lambda x: x[1], reverse=True)

    await send_tally_messages(client, message, messages, "Doinks", target_id is None)
