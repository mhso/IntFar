import asyncio
import random

import requests
from mhooge_flask.logging import logger

from api import util as api_util
from api import game_stats
from api.game_data import get_stat_parser
from discbot.commands import util as commands_util

FLIRT_MESSAGES = {
    "english": api_util.load_flavor_texts("flirt_english"),
    "spanish": api_util.load_flavor_texts("flirt_spanish")
}

async def handle_game_msg(client, message, game, target_id):
    ingame_ids = None
    target_name = client.get_discord_nick(target_id, message.guild.id)

    for disc_id in client.database.users[game]:
        if disc_id == target_id:
            ingame_ids = client.database.users[game][disc_id].ingame_id
            break

    response = ""
    game_data = None
    active_id = None
    for ingame_id in ingame_ids:
        api_client = client.api_clients[game]

        game_data = api_client.get_active_game(ingame_id)

        if game_data is not None:
            active_id = ingame_id
            break
        await asyncio.sleep(1)

    if game_data is not None:
        stat_parser = get_stat_parser(game, game_data, client.database.users[game])
        response = f"{target_name} is "
        summary = stat_parser.get_active_game_summary(active_id, api_client)
        response += summary
        active_guild = None

        game_monitor = client.game_monitors[game]
        for guild_id in game_monitor.active_game:
            active_game = game_monitor.active_game.get(guild_id)
            if active_game is not None:
                if active_game["id"] == game_data["gameId"]:
                    active_guild = guild_id
                    guild_name = client.get_guild_name(guild_id)
                    response += f"\nPlaying in *{guild_name}*"
                    break

        if False and commands_util.ADMIN_DISC_ID in [x[0] for x in users_in_game]:
            # Not used.
            predict_url = f"http://mhooge.com:5000/intfar/prediction?game_id={game_data['gameId']}"
            try:
                predict_response = requests.get(predict_url)
                if predict_response.ok:
                    pct_win = predict_response.json()["response"]
                    response += f"\nPredicted chance of winning: **{pct_win}%**"
                else:
                    error_msg = predict_response.json()["response"]
                    logger.error(f"Get game prediction error: {error_msg}")
            except requests.exceptions.RequestException as e:
                logger.error("Exception ignored in !game: " + str(e))
        elif client.ai_conn is not None:
            pct_win = client.get_ai_prediction(active_guild)
            response += f"\nPredicted chance of winning: **{pct_win}%**"
    else:
        response = f"{target_name} is not in a game at the moment "
        response += client.insert_emotes("{emote_simp_but_closeup}")

    await message.channel.send(response)

async def handle_report_msg(client, message, target_id):
    target_name = client.get_discord_nick(target_id, message.guild.id)
    mention = client.get_mention_str(target_id, message.guild.id)

    reports = client.database.report_user(target_id)

    response = f"{message.author.name} reported {mention} " + "{emote_woahpikachu}\n"
    response += f"{target_name} has been reported {reports} time"
    if reports > 1:
        response += "s"
    response += "."

    await message.channel.send(client.insert_emotes(response))

async def handle_see_reports_msg(client, message, target_id):
    report_data = client.database.get_reports(target_id)
    response = ""
    for disc_id, reports in report_data:
        name = client.get_discord_nick(disc_id, message.guild.id)
        response += f"{name} has been reported {reports} times.\n"

    await message.channel.send(response)

async def handle_flirtation_msg(client, message, language):
    messages = FLIRT_MESSAGES[language]
    flirt_msg = client.insert_emotes(messages[random.randint(0, len(messages)-1)])
    mention = client.get_mention_str(message.author.id, message.guild.id)
    await message.channel.send(f"{mention} {flirt_msg}")

async def handle_lol_summary_msg(client, message, target_id):
    # Shows information about various stats a person has accrued.
    nickname = client.get_discord_nick(target_id, message.guild.id)
    games_played = client.database.get_intfar_stats(target_id)[0]
    champs_played = client.database.get_champs_played(target_id)

    total_winrate = client.database.get_total_winrate(target_id)
    total_champs = len(client.api_clients["lol"].champ_ids)

    longest_win_streak = client.database.get_longest_win_or_loss_streak(target_id, True)
    longest_loss_streak = client.database.get_longest_win_or_loss_streak(target_id, False)

    best_champ_wr, best_champ_games, best_champ_id = client.database.get_min_or_max_league_winrate_champ(target_id, True)
    worst_champ_wr, worst_champ_games, worst_champ_id = client.database.get_min_or_max_league_winrate_champ(target_id, False)

    if best_champ_id == worst_champ_id:
        # Person has not played 10 games with any champ. Try to get stats with 5 minimum games.
        worst_champ_wr, worst_champ_games, worst_champ_id = client.database.get_min_or_max_league_winrate_champ(
            target_id, False, min_games=5
        )

    response = (
        f"{nickname} has played a total of **{games_played}** games " +
        f"(**{total_winrate:.1f}%** was won).\n" +
        f"He has played **{champs_played}**/**{total_champs}** different champions.\n\n"
    )

    response += f"His longest winning streak was **{longest_win_streak}** games.\n"
    response += f"His longest loss streak was **{longest_loss_streak}** games.\n\n"

    # If person has not played a minimum of 5 games with any champions, skip champ winrate stats.
    if best_champ_wr is not None and worst_champ_wr is not None and best_champ_id != worst_champ_id:
        best_champ_name = client.api_clients["lol"].get_champ_name(best_champ_id)
        worst_champ_name = client.api_clients["lol"].get_champ_name(worst_champ_id)
        response += (
            f"He performs best on **{best_champ_name}** (won " +
            f"**{best_champ_wr:.1f}%** of **{best_champ_games}** games).\n" +
            f"He performs worst on **{worst_champ_name}** (won " +
            f"**{worst_champ_wr:.1f}%** of **{worst_champ_games}** games).\n"
        )

    best_person_id, best_person_games, best_person_wr = client.database.get_winrate_relation(target_id, True)
    worst_person_id, worst_person_games, worst_person_wr = client.database.get_winrate_relation(target_id, False)

    if best_person_id == worst_person_id:
        worst_person_id, worst_person_games, worst_person_wr = client.database.get_winrate_relation(target_id, False, min_games=5)

    # If person has not played a minimum of 5 games with any person, skip person winrate stats.
    if best_person_wr is not None and worst_person_wr is not None and best_person_id != worst_person_id:
        best_person_name = client.get_discord_nick(best_person_id, message.guild.id)
        worst_person_name = client.get_discord_nick(worst_person_id, message.guild.id)
        response += (
            f"He performs best when playing with **{best_person_name}** (won " +
            f"**{best_person_wr:.1f}%** of **{best_person_games}** games).\n" +
            f"He performs worst when playing with **{worst_person_name}** (won " +
            f"**{worst_person_wr:.1f}%** of **{worst_person_games}** games).\n\n"
        )

    # Get performance score for person.
    score, rank, num_scores = client.database.get_performance_score(target_id)

    response += (
        f"The *Personally Evaluated Normalized Int-Far Score* for {nickname} is " +
        f"**{score:.2f}**/**10**\nThis ranks him at **{rank}**/**{num_scores}**."
    )   

    await message.channel.send(response)

async def handle_csgo_summary_msg(client, message, target_id):
    await message.channel.send("Not implemented yet :O")

async def handle_summary_msg(client, message, game, target_id):
    if game == "lol":
        return await handle_lol_summary_msg(client, message, target_id)
    elif game == "csgo":
        return await handle_csgo_summary_msg(client, message, target_id)

async def handle_performance_msg(client, message, game, target_id=None):
    performance_data = client.database.get_performance_score(game, target_id)
    game_name = api_util.SUPPORTED_GAMES[game]
    if target_id is None:
        response = f"*Personally Evaluated Normalized Int-Far Scores* for {game_name} for all users:"
        for score_id, score_value in performance_data:
            name = client.get_discord_nick(score_id, message.guild.id)
            response += f"\n- {name}: **{score_value:.2f}**"
    else:
        name = client.get_discord_nick(target_id, message.guild.id)
        score, rank, num_scores = performance_data

        response = (
            f"The *Personally Evaluated Normalized Int-Far Score* for {name} for {game_name} is " +
            f"**{score:.2f}**/**10**. This ranks him at **{rank}**/**{num_scores}**."
        )

    score_fmt = "\nHigher score = better player (but smaller dick). Maximum is 10. "
    score_fmt += "These scores are" if target_id is None else "This score is"
    response += (
        f"\n{score_fmt} calculated using the ratio of " +
        "games being Int-Far, getting doinks, or winning."
    )

    await message.channel.send(response)

async def handle_winrate_msg(client, message, game, champ_or_map, target_id):
    winrate = None
    games = None
    qualified_name = None

    if game == "lol":
        champ_id = client.api_clients[game].try_find_champ(champ_or_map)
        if champ_id is None:
            response = f"Not a valid champion: `{champ_or_map}`."
        else:
            winrate, games = client.database.get_league_champ_winrate(target_id, champ_id)
            qualified_name = client.api_clients[game].get_champ_name(champ_id)
    elif game == "csgo":
        map_id = client.steam_api.try_find_map(champ_or_map)
        if map_id is None:
            response = f"Not a valid map: `{champ_or_map}`"
        else:
            winrate, games = client.database.get_csgo_map_winrate(target_id, map_id)
            qualified_name = client.steam_api.get_map_name(map_id)

    if winrate is not None:
        user_name = client.get_discord_nick(target_id, message.guild.id)
        if games == 0:
            response = f"{user_name} has not played any games on {qualified_name}."
        else:
            response = f"{user_name} has a **{winrate:.2f}%** winrate on {qualified_name} in **{int(games)}** games.\n"

    await message.channel.send(response)
