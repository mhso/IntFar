import asyncio
import random

import requests

from api import util as api_util
from api import game_stats
from discbot.commands import util as commands_util

FLIRT_MESSAGES = {
    "english": api_util.load_flavor_texts("flirt_english"),
    "spanish": api_util.load_flavor_texts("flirt_spanish")
}

async def handle_game_msg(client, message, target_id):
    summoner_ids = None
    target_name = client.get_discord_nick(target_id, message.guild.id)

    for disc_id, _, summ_ids in client.database.summoners:
        if disc_id == target_id:
            summoner_ids = summ_ids
            break

    response = ""
    game_data = None
    active_summoner = None
    for summ_id in summoner_ids:
        game_data = client.riot_api.get_active_game(summ_id)
        if game_data is not None:
            active_summoner = summ_id
            break
        await asyncio.sleep(1)

    if game_data is not None:
        response = f"{target_name} is "
        summary, users_in_game = game_stats.get_active_game_summary(
            game_data, active_summoner,
            client.database.summoners, client.riot_api
        )
        response += summary
        active_guild = None

        for guild_id in api_util.GUILD_IDS:
            active_game = client.active_game.get(guild_id)
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
                    client.config.log(f"Get game prediction error: {error_msg}")
            except requests.exceptions.RequestException as e:
                client.config.log("Exception ignored in !game: " + str(e))
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

async def handle_summary_msg(client, message, target_id):
    # Shows an infographic about various stats a person has accrued.
    nickname = client.get_discord_nick(target_id, message.guild.id)
    games_played = client.database.get_intfar_stats(target_id)[0]
    champs_played = client.database.get_champs_played(target_id)

    total_winrate = client.database.get_total_winrate(target_id)
    total_champs = len(client.riot_api.champ_ids)

    best_champ_wr, best_champ_games, best_champ_id = client.database.get_min_or_max_winrate_champ(target_id, True)
    worst_champ_wr, worst_champ_games, worst_champ_id = client.database.get_min_or_max_winrate_champ(target_id, False)

    if best_champ_id == worst_champ_id:
        # Person has not played 10 games with any champ. Try to get stats with 5 minimum games.
        worst_champ_wr, worst_champ_games, worst_champ_id = client.database.get_min_or_max_winrate_champ(
            target_id, False, min_games=5
        )

    response = (
        f"{nickname} has played a total of **{games_played}** games " +
        f"(**{total_winrate:.1f}%** was won).\n" +
        f"He has played **{champs_played}**/**{total_champs}** different champions.\n"
    )
    # If person has not played a minimum of 5 games with any champions, skip champ winrate stats.
    if best_champ_wr is not None and worst_champ_wr is not None and best_champ_id != worst_champ_id:
        best_champ_name = client.riot_api.get_champ_name(best_champ_id)
        worst_champ_name = client.riot_api.get_champ_name(worst_champ_id)
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
            f"**{worst_person_wr:.1f}%** of **{worst_person_games}** games).\n"
        )

    # Get performance score for person.
    score, rank, num_scores = client.database.get_performance_score(target_id)

    response += (
        f"The *Personally Evaluated Normalized Int-Far Score* for {nickname} is " +
        f"**{score:.2f}**/**10**\nThis ranks him at **{rank}**/**{num_scores}**."
    )

    await message.channel.send(response)

async def handle_performance_msg(client, message, target_id=None):
    performance_data = client.database.get_performance_score(target_id)
    if target_id is None:
        response = "*Personally Evaluated Normalized Int-Far Scores* for all users:"
        for score_id, score_value in performance_data:
            name = client.get_discord_nick(score_id, message.guild.id)
            response += f"\n- {name}: **{score_value:.2f}**"
    else:
        name = client.get_discord_nick(target_id, message.guild.id)
        score, rank, num_scores = performance_data

        response = (
            f"The *Personally Evaluated Normalized Int-Far Score* for {name} is " +
            f"**{score:.2f}**/**10**. This ranks him at **{rank}**/**{num_scores}**."
        )

    score_fmt = "\nHigher score = better player (but smaller dick). Maximum is 10. "
    score_fmt += "These scores are" if target_id is None else "This score is"
    response += (
        f"\n{score_fmt} calculated using the ratio of " +
        "games being Int-Far, getting doinks, or winning."
    )

    await message.channel.send(response)

async def handle_winrate_msg(client, message, champ_name, target_id):
    champ_id = client.riot_api.try_find_champ(champ_name)
    if champ_id is None:
        response = f"Not a valid champion: `{champ_name}`."
    else:
        winrate, games = client.database.get_champ_winrate(target_id, champ_id)
        champ_name = client.riot_api.get_champ_name(champ_id)
        user_name = client.get_discord_nick(target_id, message.guild.id)
        if games == 0:
            response = f"{user_name} has not played any games on {champ_name}."
        else:
            response = f"{user_name} has a **{winrate:.2f}%** winrate with {champ_name} in **{int(games)}** games.\n"

    await message.channel.send(response)
