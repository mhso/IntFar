import asyncio
import random

import requests

from api import util as api_util
from api import game_stats
from ai.data import shape_predict_data
from discbot.commands import util as commands_util

FLIRT_MESSAGES = {
    "english": api_util.load_flavor_texts("flirt_english"),
    "spanish": api_util.load_flavor_texts("flirt_spanish")
}

async def handle_game_msg(self, message, target_id):
    summoner_ids = None
    target_name = self.get_discord_nick(target_id, message.guild.id)

    for disc_id, _, summ_ids in self.database.summoners:
        if disc_id == target_id:
            summoner_ids = summ_ids
            break

    response = ""
    game_data = None
    active_summoner = None
    for summ_id in summoner_ids:
        game_data = self.riot_api.get_active_game(summ_id)
        if game_data is not None:
            active_summoner = summ_id
            break
        await asyncio.sleep(1)

    if game_data is not None:
        response = f"{target_name} is "
        summary, users_in_game = game_stats.get_active_game_summary(
            game_data, active_summoner,
            self.database.summoners, self.riot_api
        )
        response += summary

        for guild_id in api_util.GUILD_IDS:
            active_game = self.active_game.get(guild_id)
            if active_game is not None:
                if active_game["id"] == game_data["gameId"]:
                    guild_name = self.get_guild_name(guild_id)
                    response += f"\nPlaying in *{guild_name}*"
                    break

        if commands_util.ADMIN_DISC_ID in [x[0] for x in users_in_game]:
            predict_url = f"http://mhooge.com:5000/intfar/prediction?game_id={game_data['gameId']}"
            try:
                predict_response = requests.get(predict_url)
                if predict_response.ok:
                    pct_win = predict_response.json()["response"]
                    response += f"\nPredicted chance of winning: **{pct_win}%**"
                elif self.ai_conn is not None:
                    input_data = shape_predict_data(
                        self.database, self.riot_api, self.config, users_in_game
                    )
                    self.ai_conn.send(("predict", [input_data]))
                    ratio_win = self.ai_conn.recv()
                    pct_win = int(ratio_win * 100)
                    response += f"\nPredicted chance of winning: **{pct_win}%**"
                else:
                    error_msg = predict_response.json()["response"]
                    self.config.log(f"Get game prediction error: {error_msg}")

            except requests.exceptions.RequestException as e:
                self.config.log("Exception ignored in !game: " + str(e))
    else:
        response = f"{target_name} is not in a game at the moment "
        response += self.insert_emotes("{emote_simp_but_closeup}")

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
