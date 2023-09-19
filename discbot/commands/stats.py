import api.util as api_util
from api.game_data import get_stat_quantity_descriptions, stats_from_database
from api.game_data.csgo import RANKS

async def handle_stats_msg(client, message, game):
    valid_stats = ", ".join(f"'{cmd}'" for cmd in get_stat_quantity_descriptions(game))
    response = "**--- Valid stats ---**\n```"
    response += valid_stats
    response += "\n```"
    response += "You can use these stats with the following commands: "
    response += "`!average [stat]`, `!best [stat]`, or `!worst [stat]`"

    await message.channel.send(response)

async def handle_average_msg_lol(client, message, stat, champ_id=None, disc_id=None):
    champ_name = None
    if champ_id is not None:
        champ_name = client.api_clients["lol"].get_champ_name(champ_id)

    minimum_games = 10 if champ_id is None else 5
    values = client.database.get_average_stat_league(stat, disc_id, champ_id, minimum_games)

    for_all = disc_id is None
    readable_stat = stat.replace("_", " ")

    response = ""

    for index, (disc_id, avg_value, games) in enumerate(values):
        if for_all:
            response += "- "

        target_name = client.get_discord_nick(disc_id, message.guild.id)

        if avg_value is None:
            # No games or no games on the given champ.
            response += f"{target_name} has not yet played at least {minimum_games} games "

            if champ_id is not None:
                response += f"on {champ_name} "

            response += "{emote_perker_nono}"

        elif stat == "first_blood":
            percent = f"{avg_value * 100:.2f}"
            response += f"{target_name} got first blood in **{percent}%** of **{games}** games "

            if champ_id is not None:
                response += f"when playing **{champ_name}** "

            if not for_all:
                response += "{emote_poggers}"

        else:
            ratio = f"{avg_value:.2f}"
            response += f"{target_name} averages **{ratio}** {readable_stat} in **{games}** games "

            if champ_id is not None:
                response += f"of playing **{champ_name}** "

            if not for_all:
                response += "{emote_poggers}"

        if index < len(values) - 1:
            response += "\n"

    await message.channel.send(client.insert_emotes(response))

async def handle_average_msg_csgo(client, message, stat, map_id=None, disc_id=None):
    map_name = None
    if map_id is not None:
        map_name = client.api_clients["csgo"].get_map_name(map_id)

    minimum_games = 10 if map_id is None else 5
    values = client.database.get_average_stat_csgo(stat, disc_id, map_id, minimum_games)

    for_all = disc_id is None
    readable_stat = stat.replace("_", " ")

    response = ""

    for index, (disc_id, avg_value, games) in enumerate(values):
        if for_all:
            response += "- "

        target_name = client.get_discord_nick(disc_id, message.guild.id)

        if avg_value is None:
            # No games or no games on the given map.
            response += f"{target_name} doesn't have at least {minimum_games} games with that stat "

            if map_name is not None:
                response += f"on {map_name} "

            response += "{emote_perker_nono}"

        elif stat == "rank":
            avg_rank = RANKS[int(avg_value)]
            response += f"{target_name}'s average rank is **{avg_rank}** in **{games}** games "

            if map_name is not None:
                response += f"when playing **{map_name}** "

            if not for_all:
                response += "{emote_poggers}"

        else:
            ratio = f"{avg_value:.2f}"
            response += f"{target_name} averages **{ratio}** {readable_stat} in **{games}** games "

            if map_name is not None:
                response += f"of playing **{map_name}** "

            if not for_all:
                response += "{emote_poggers}"

        if index < len(values) - 1:
            response += "\n"

    await message.channel.send(client.insert_emotes(response))

async def handle_average_msg(client, message, game, stat, champ_or_map=None, disc_id=None):
    quantity_descs = get_stat_quantity_descriptions(game)
    if stat not in quantity_descs: # Check if the requested stat is a valid stat.
        emote = "{emote_carole_fucking_baskin}"
        response = f"Not a valid stat: '{stat}' {emote}. See `!stats` for a list of valid stats."
        await message.channel.send(client.insert_emotes(response))
        return

    if game == "lol":
        await handle_average_msg_lol(client, message, stat, champ_or_map, disc_id)
    elif game == "csgo":
        await handle_average_msg_csgo(client, message, stat, champ_or_map, disc_id)

def get_game_summary(client, game, game_id, target_id, guild_id):
    game_stats = stats_from_database(
        game,
        game_id,
        client.database,
        client.api_clients[game],
        client.database.users_by_game[game],
        guild_id
    )
    return game_stats.get_finished_game_summary(target_id)

async def handle_stat_msg(client, message, game, best, stat, target_id):
    """
    Get the value of the requested stat for the requested player.
    F.x. '!best lol damage Obama'.
    """
    stat_descs = get_stat_quantity_descriptions(game)
    if stat in stat_descs: # Check if the requested stat is a valid stat.
        if best:
            best = stat != "deaths"
        else:
            best = stat == "deaths"

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
            ) = client.database.get_most_extreme_stat(game, stat, maximize)
        else:
            (
                stat_count, # <- How many times the stat has occured.
                min_or_max_value, # <- Highest/lowest occurance of the stat value.
                game_id
            ) = client.database.get_best_or_worst_stat(game, stat, target_id, maximize)

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
                response += f"is {recepient} with **{min_or_max_value}** games "
                response += client.insert_emotes(emote_to_use)
            else:
                response = f"The {readable_stat} ever in a game was **{min_or_max_value}** "
                response += f"by {recepient} " + client.insert_emotes(emote_to_use)
                if game_summary is not None:
                    response += f"\nHe got this when playing {game_summary}"
        else:
            game_specific_desc = ""
            if game == "lol":
                champ_id, champ_count = client.database.get_league_champ_count_for_stat(
                    stat, best, target_id
                )
                champ_name = client.api_clients[game].get_champ_name(champ_id)
                game_specific_desc = f"The champion he most often gets {readable_stat} with is **{champ_name}** (**{champ_count}** games).\n"
            elif game == "csgo":
                map_id, map_count = client.database.get_csgo_map_count_for_stat(
                    stat, best, target_id
                )
                map_name = client.api_clients[game].get_map_name(map_id)
                game_specific_desc = f"The map he most often gets {readable_stat} on is **{map_name}** (**{map_count}** games)\n"

            response = (
                f"{recepient} has gotten {readable_stat} in a game " +
                f"**{stat_count}** times " + client.insert_emotes(emote_to_use) + "\n"
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
        await message.channel.send(response)
        return
