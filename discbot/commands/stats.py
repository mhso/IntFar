from datetime import datetime
from time import time
import api.util as api_util
from api.awards import get_intfar_reasons, get_doinks_reasons
from api.game_data import (
    get_stat_quantity_descriptions,
    stats_from_database,
    get_formatted_stat_names,
    get_formatted_stat_value
)
from api.game_data.cs2 import RANKS
from discbot.commands.misc import get_winrate

async def handle_stats_msg(client, message, game):
    game_name = api_util.SUPPORTED_GAMES[game]
    valid_stats = ", ".join(f"'{cmd}'" for cmd in get_stat_quantity_descriptions(game))
    response = f"**--- Valid stats for {game_name} ---**\n```"
    response += valid_stats
    response += "\n```"
    response += "You can use these stats with the following commands: "
    response += "`!average [stat]`, `!best [stat]`, or `!worst [stat]`"

    await message.channel.send(response)

async def handle_average_msg(client, message, stat, game, playable_id=None, disc_id=None):
    quantity_descs = get_stat_quantity_descriptions(game)
    if stat not in quantity_descs: # Check if the requested stat is a valid stat.
        emote = "{emote_carole_fucking_baskin}"
        response = f"Not a valid stat: '{stat}' {emote}. See `!stats` for a list of valid stats."
        await message.channel.send(client.insert_emotes(response))
        return

    playable_name = None
    if playable_id is not None:
        playable_name = client.api_clients[game].get_playable_name(playable_id)

    minimum_games = 10 if playable_id is None else 5
    values = client.game_databases[game].get_average_stat(stat, disc_id, playable_id, minimum_games)()

    for_all = disc_id is None
    readable_stat = stat.replace("_", " ")

    response = ""

    for index, (disc_id, avg_value, games) in enumerate(values):
        if for_all:
            response += "- "

        target_name = client.get_discord_nick(disc_id, message.guild.id)

        if avg_value is None:
            # No games or no games on the given champ/map.
            response += f"{target_name} has not yet played at least {minimum_games} games "

            if playable_id is not None:
                response += f"on {playable_name} "

            response += "{emote_perker_nono}"

        elif stat == "first_blood":
            percent = f"{avg_value * 100:.2f}"
            response += f"{target_name} got first blood in **{percent}%** of **{games}** games "

            if playable_id is not None:
                response += f"when playing **{playable_name}** "

            if not for_all:
                response += "{emote_poggers}"

        elif stat == "rank":
            avg_rank = RANKS[int(avg_value)]
            response += f"{target_name}'s average rank is **{avg_rank}** in **{games}** games "

            if playable_name is not None:
                response += f"when playing **{playable_name}** "

            if not for_all:
                response += "{emote_poggers}"

        else:
            ratio = f"{avg_value:.2f}"
            response += f"{target_name} averages **{ratio}** {readable_stat} in **{games}** games "

            if playable_id is not None:
                response += f"of playing **{playable_name}** "

            if not for_all:
                response += "{emote_poggers}"

        if index < len(values) - 1:
            response += "\n"

    await message.channel.send(client.insert_emotes(response))

def get_game_summary(client, game, game_id, target_id, guild_id):
    """
    Return a string describing the outcome of the game with the given game_id,
    for the given player, in the given guild.
    """
    game_stats = stats_from_database(
        game,
        client.game_databases[game],
        client.api_clients[game],
        guild_id,
        game_id,
    )[0]
    return game_stats.get_finished_game_summary(target_id)

async def handle_stat_msg(client, message, best, game, stat, target_id):
    """
    Get the highest or lowest value of the requested stat for the given player
    and write it to Discord. If target_id is None, instead gets the highest/lowest
    value of all time for the given stat.
    """
    stat_descs = get_stat_quantity_descriptions(game)
    if stat in stat_descs: # Check if the requested stat is a valid stat.
        quantity_type = 0 if best else 1

        # Check whether to find the max or min of some value, when returning
        # 'his most/lowest [stat] ever was ... Usually highest is best,
        # lowest is worse, except with deaths, where the opposite is the case.
        maximize = not ((stat != "deaths") ^ best)

        # Get a readable description, such as 'most deaths' or 'lowest kp'.
        quantifier = stat_descs[stat][quantity_type]
        if quantifier is not None:
            readable_stat = quantifier + " " + stat
        else:
            readable_stat = stat

        readable_stat = readable_stat.replace("_", " ")

        response = ""
        check_all = target_id is None

        if check_all: # Get best/worst ever stat of everyone.
            (
                target_id, # <- Who got the highest/lowest stat ever
                min_or_max_value, # <- The highest/lowest value of the stat
                game_id # <- The game where it happened
            ) = client.game_databases[game].get_most_extreme_stat(stat, maximize)
        else:
            (
                stat_count, # <- How many times the stat has occured
                game_count, # <- How many games were the stat was relevant
                min_or_max_value, # <- Highest/lowest occurance of the stat value
                game_id
            ) = client.game_databases[game].get_best_or_worst_stat(stat, target_id, maximize)()

        recepient = client.get_discord_nick(target_id, message.guild.id)

        game_summary = None
        if min_or_max_value is not None and game_id is not None:
            min_or_max_value = api_util.round_digits(min_or_max_value)
            game_summary = get_game_summary(client, game, game_id, target_id, message.guild.id)

        emote_to_use = "{emote_pog}" if best else "{emote_peberno}"

        if check_all:
            if stat == "first_blood":
                quant = "most" if best else "least"
                response = f"The person who has gotten first blood the {quant} "
                response += f"is {recepient} with **{min_or_max_value}** games"
                response += client.insert_emotes(emote_to_use)
            else:
                response = f"The {readable_stat} ever in a game was **{min_or_max_value}** "
                response += f"by {recepient} " + client.insert_emotes(emote_to_use)
                if game_summary is not None:
                    response += f"\nHe got this when playing {game_summary}"
        else:
            played_id, played_count = client.game_databases[game].get_played_count_for_stat(
                stat, maximize, target_id
            )

            played_name = client.api_clients[game].get_playable_name(played_id)
            if game == "lol":
                played_type = "champion"
            elif game == "cs2":
                played_type = "map"

            game_specific_desc = f"The {played_type} he most often gets {readable_stat} on is **{played_name}** (**{played_count}** games)\n"

            response = (
                f"{recepient} has gotten {readable_stat} in a game " +
                f"**{stat_count}** times out of **{game_count}** games played " + client.insert_emotes(emote_to_use) + "\n"
                f"{game_specific_desc}"
            )
            if min_or_max_value is not None:
                # The target user has gotten most/fewest of 'stat' in at least one game.
                response += f"His {readable_stat} ever was "
                response += f"**{min_or_max_value}** when playing {game_summary}"

        await message.channel.send(response)

    else:
        emote = "{emote_carole_fucking_baskin}"
        response = f"Not a valid stat: '{stat}' {emote}. See `!stats` for a list of valid stats."
        await message.channel.send(client.insert_emotes(response))
        return

async def handle_match_history_msg(client, message, game, target_id=None):
    formatted_stat_names = get_formatted_stat_names(game)

    all_game_stats = stats_from_database(
        game,
        client.game_databases[game],
        client.api_clients[game],
        message.guild.id,
    )

    formatted_entries = []
    for game_stats in all_game_stats:
        date = datetime.fromtimestamp(game_stats.timestamp).strftime("%Y/%m/%d")
        dt_1 = datetime.fromtimestamp(time())
        dt_2 = datetime.fromtimestamp(time() + game_stats.duration)
        fmt_duration = api_util.format_duration(dt_1, dt_2)

        player_stats = game_stats.find_player_stats(target_id, game_stats.filtered_player_stats)

        if player_stats is None: # Target player was not in the game
            continue

        if game == "lol":
            map_or_champ = player_stats.champ_name
        else:
            map_or_champ = game_stats.map_name

        win_str = "Won" if game_stats.win == 1 else "Lost"

        # Int-Far description
        if game_stats.intfar_id == target_id:
            reasons = " and ".join(
                f"**{r}**" for c, r in zip(
                    game_stats.intfar_reason, get_intfar_reasons(game).values()
                )
                if c == "1"
            )
            intfar_description = f"Int-Far for {reasons}"
        else:
            intfar_description = "Not **Int-Far**"

        # Doinks description
        if player_stats.doinks is not None:
            reasons = " and ".join(
                f"**{r}**" for c, r in zip(
                    player_stats.doinks, get_doinks_reasons(game).values()
                )
                if c == "1"
            )
            doinks_description = f"Big Doinks for {reasons}"
        else:
            emote = client.insert_emotes("{emote_Doinks}")
            doinks_description = f"No {emote}"

        match_str = (
            f"- **{win_str}** game lasting **{fmt_duration}** on **{date}** playing **{map_or_champ}**\n"
            f"- {doinks_description}\n"
            f"- {intfar_description}\n"
            "```css\n"
        )

        # Get the formatted stat names and stat values and figure out the max width
        # of the stat names to pad all stat entries to the same width
        formatted_stats = []
        formatted_values = []
        for stat in player_stats.__dict__:
            if stat not in formatted_stat_names:
                continue

            fmt_stat = formatted_stat_names[stat]
            fmt_value = get_formatted_stat_value(game, stat, player_stats.__dict__[stat])

            formatted_stats.append(fmt_stat)
            formatted_values.append(fmt_value)

        max_width = max(len(s) for s in formatted_stats)

        for stat, value in zip(formatted_stats, formatted_values):
            padding = " " * (max_width - len(stat))

            match_str += f"\n{stat}:{padding} {value}"

        match_str += "\n```"

        formatted_entries.append(match_str)

    header = f"--- Match history for **{api_util.SUPPORTED_GAMES[game]}** ---"

    await client.paginate(message.channel, formatted_entries, 0, 1, header)

async def handle_champion_msg(client, message, champ_id, game, target_id):
    if champ_id is None:
        await message.channel.send(f"Champion is not valid.")
        return

    champ_name, winrate, games = get_winrate(client, champ_id, game, target_id)

    if winrate is None or games == 0:
        response = f"{user_name} has not played any games on {champ_name}."
        await message.channel.send(response)
        return

    user_name = client.get_discord_nick(target_id, message.guild.id)
    response = f"Stats for {user_name} on *{champ_name}*:\n"
    response += f"Winrate: **{winrate:.2f}%** in **{int(games)}** games.\n"

    stats_to_get = [
        "kills",
        "deaths",
        "assists",
        "kda",
        "cs",
        "cs_per_min",
        "damage",
        "gold",
        "vision_score",
        "vision_wards"
    ]
    min_games = 1
    text_rows = [
        ["Stat", "Value", "vs. Self", f"vs. {champ_name}s", "vs. All"]
    ]

    with client.game_databases["lol"] as database:
        stats = {
            stat: get_formatted_stat_value(
                game,
                stat,
                database.get_average_stat(stat, target_id, champ_id, min_games)()[0][1]
            )
            for stat in stats_to_get
        }

        formatted_stat_names = get_formatted_stat_names(game)
        for stat in stats:
            stat_name = formatted_stat_names[stat]

            row = [f"{stat_name}", f"{stats[stat]}"]

            for comparison in range(3):
                rank, total = database.get_average_stat_rank(
                    stat, target_id, champ_id, comparison + 1, min_games
                )()
                row.append(f"{rank}/{total}")

            text_rows.append(row)

    col_lengths = [max(len(row[col]) for row in text_rows) for col in range(len(text_rows[0]))]
    response += "```css\n"
    for row_index, row in enumerate(text_rows):
        if row_index == 1:
            response += "-" * (sum(col_lengths) + 15) + "\n"

        for col_index, entry in enumerate(row):
            padding = col_lengths[col_index] - len(entry)
            response += entry + " " * padding
            if col_index < len(row) - 1:
                response += " | "

        response += "\n"

    response += "```"

    await message.channel.send(response)
