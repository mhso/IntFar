import api.util as api_util
from api import game_stats

async def handle_stats_msg(client, message):
    valid_stats = ", ".join("'" + cmd + "'" for cmd in api_util.STAT_COMMANDS)
    response = "**--- Valid stats ---**\n```"
    response += valid_stats
    response += "\n```"
    response += "You can use these stats with the following commands: "
    response += "`!average [stat]`, `!best [stat]`, or `!worst [stat]`"

    await message.channel.send(response)

async def handle_average_msg(client, message, stat, champ_id=None, disc_id=None):
    if stat in api_util.STAT_COMMANDS: # Check if the requested stat is a valid stat.
        if champ_id is not None:
            champ_name = client.riot_api.get_champ_name(champ_id)

        target_name = client.get_discord_nick(disc_id, message.guild.id)
        avg_value = client.database.get_average_stat(stat, disc_id, champ_id)

        # No games or no games on champ.
        if avg_value is None:
            response = f"{target_name} has not yet played any games "

            if champ_id is not None:
                response += f"on {champ_name} "

            response += "{emote_perker_nono}"

        elif stat == "first_blood":
            formatted_value = f"{avg_value * 100:.2f}"

            response = f"{target_name} gets first blood in **{formatted_value}%** of games "

            if champ_id is not None:
                response += f"when playing **{champ_name}** "

            response += "{emote_poggers}"

        else:
            formatted_value = f"{avg_value:.2f}"
            response = f"{target_name} averages **{formatted_value}** {stat} per game "

            if champ_id is not None:
                response += f"when playing **{champ_name}** "

            else:
                response += "over all his games "

            response += "{emote_poggers}"

        await message.channel.send(client.insert_emotes(response))

    else:
        response = f"Not a valid stat: '{stat}' "
        response += client.insert_emotes("{emote_carole_fucking_baskin}")
        await message.channel.send(response)

async def handle_stat_msg(client, message, best, stat, target_id):
    """
    Get the value of the requested stat for the requested player.
    F.x. '!best damage Obama'.
    """
    if stat in api_util.STAT_COMMANDS: # Check if the requested stat is a valid stat.
        stat_index = api_util.STAT_COMMANDS.index(stat)

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
        quantifier = api_util.STAT_QUANTITY_DESC[stat_index][quantity_type]
        if quantifier is not None:
            readable_stat = quantifier + " " + stat
        else:
            readable_stat = stat

        readable_stat = readable_stat.replace("_", " ")

        response = ""
        check_all = target_id is None

        if check_all: # Get best/worst ever stat of everyone.
            (
                target_id,
                min_or_max_value,
                game_id
            ) = client.database.get_most_extreme_stat(stat, maximize)
            recepient = client.get_discord_nick(target_id, message.guild.id)
        else:
            (
                stat_count, # <- How many times the stat has occured.
                min_or_max_value, # <- Highest/lowest occurance of the stat value.
                game_id
            ) = client.database.get_best_or_worst_stat(stat, target_id, maximize)
            recepient = client.get_discord_nick(target_id, message.guild.id)

        game_summary = None
        if min_or_max_value is not None and game_id is not None:
            min_or_max_value = api_util.round_digits(min_or_max_value)
            game_info = client.riot_api.get_game_details(game_id)
            if game_info is not None:
                summ_ids = client.database.summoner_from_discord_id(target_id)[2]
                game_summary = game_stats.get_finished_game_summary(game_info, summ_ids, client.riot_api)

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
                    response += f"\nHe got this as {game_summary}"
        else:
            champ_id, champ_count = client.database.get_champ_count_for_stat(
                stat, best, target_id
            )
            champ_name = client.riot_api.get_champ_name(champ_id)
            response = (
                f"{recepient} has gotten {readable_stat} in a game " +
                f"**{stat_count}** times " + client.insert_emotes(emote_to_use) + "\n"
                f"The champion he most often gets {readable_stat} with is "
                f"**{champ_name}** (**{champ_count}** games).\n"
            )
            if min_or_max_value is not None:
                # The target user has gotten most/fewest of 'stat' in at least one game.
                response += f"His {readable_stat} ever was "
                response += f"**{min_or_max_value}** as {game_summary}"

        await message.channel.send(response)

    else:
        response = f"Not a valid stat: '{stat}' "
        response += client.insert_emotes("{emote_carole_fucking_baskin}")
        await message.channel.send(response)
