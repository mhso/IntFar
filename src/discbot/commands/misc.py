import random

from discord import Message
import requests
from mhooge_flask.logging import logger

from api import util as api_util
from api.config import Config
from api.game_data import get_stat_parser, get_formatted_stat_names, get_formatted_stat_value
from discbot.commands.base import *
from discbot.discord_bot import DiscordClient

config = Config()

FLIRT_MESSAGES = {
    "english": api_util.load_flavor_texts(config, "flirt_english"),
    "spanish": api_util.load_flavor_texts(config, "flirt_spanish")
}

class GameCommand(Command):
    NAME = "game"
    DESCRIPTION = "See details about the match the given person is in, for the given game, if any."
    MANDATORY_PARAMS = [TargetParam("person")]
    OPTIONAL_PARAMS = [GameParam("game")]

    async def handle(self, target_id: int, game: str):
        database = self.client.game_databases[game]
        target_user = None
        target_name = self.client.get_discord_nick(target_id, self.message.guild.id)

        for disc_id in database.game_users.keys():
            if disc_id == target_id:
                target_user = database.game_users[disc_id]
                break

        response = ""
        game_data, active_id = await self.client.api_clients[game].get_active_game_for_user(target_user)

        if game_data is not None:
            stat_parser = get_stat_parser(game, game_data, self.client.api_clients[game], database.game_users, self.message.guild.id)
            response = f"{target_name} is "
            summary = stat_parser.get_active_game_summary(active_id)
            response += summary
            active_guild = None

            game_monitor = self.client.game_monitors[game]
            for guild_id in game_monitor.active_game:
                active_game = game_monitor.active_game.get(guild_id)
                if active_game is not None:
                    if active_game["id"] == game_data["gameId"]:
                        active_guild = guild_id
                        guild_name = self.client.get_guild_name(guild_id)
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
            elif self.client.ai_conn is not None:
                pct_win = self.client.get_ai_prediction(active_guild)
                response += f"\nPredicted chance of winning: **{pct_win}%**"
        else:
            response = f"{target_name} is not in a game at the moment "
            response += self.client.insert_emotes("{emote_simp_but_closeup}")

        await self.message.channel.send(response)

class ReportCommand(Command):
    NAME = "report"
    DESCRIPTION = "Report someone, f.x. if they are being a poon."
    ACCESS_LEVEL = "all"
    MANDATORY_PARAMS = [TargetParam("person")]

    async def handle(self, target_id: int):
        target_name = self.client.get_discord_nick(target_id, self.message.guild.id)
        mention = self.client.get_mention_str(target_id, self.message.guild.id)

        reports = self.client.meta_database.report_user(target_id)

        response = f"{self.message.author.name} reported {mention} " + "{emote_woahpikachu}\n"
        response += f"{target_name} has been reported {reports} time"
        if reports > 1:
            response += "s"
        response += "."

        await self.message.channel.send(self.client.insert_emotes(response))

class ReportsCommand(Command):
    NAME = "reports"
    DESCRIPTION = "See how many times someone (or yourself) has been reported."
    TARGET_ALL = True
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = [TargetParam("person")]

    async def handle(self, target_id: int):
        report_data = self.client.meta_database.get_reports(target_id)
        response = ""
        for disc_id, reports in report_data:
            name = self.client.get_discord_nick(disc_id, self.message.guild.id)
            response += f"{name} has been reported {reports} times.\n"

        await self.message.channel.send(response)

class BaseFlirtCommand(Command):
    COMMANDS_DICT = commands_util.CUTE_COMMANDS

    def __init__(self, client: DiscordClient, message: Message, language: str):
        super().__init__(client, message)
        self.language = language

    async def handle(self):
        messages = FLIRT_MESSAGES[self.language]
        flirt_msg = self.client.insert_emotes(messages[random.randint(0, len(messages)-1)])
        mention = self.client.get_mention_str(self.message.author.id, self.message.guild.id)
        await self.message.channel.send(f"{mention} {flirt_msg}")

class FlirtEnglishCommand(BaseFlirtCommand):
    NAME = "intdaddy"
    DESCRIPTION = "Flirt with Int-Far."

    def __init__(self, client: DiscordClient, message: Message):
        super().__init__(client, message, "english")

class FlirtSpanishCommand(BaseFlirtCommand):
    NAME = "intpapi"
    DESCRIPTION = "Flirt with Int-Far (in spanish)."

    def __init__(self, client: DiscordClient, message: Message):
        super().__init__(client, message, "spanish")

class SummaryCommand(Command):
    NAME = "summary"
    DESCRIPTION = (
        "Show a summary of you or someone else's stats across all recorded games."
    )
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = [GameParam("game"), TargetParam("person")]

    async def handle(self, game: str, target_id: int):
        database = self.client.game_databases[game]

        # Shows information about various stats a person has accrued.
        nickname = self.client.get_discord_nick(target_id, self.message.guild.id)
        games_played = database.get_intfar_stats(target_id)[0]
        num_played_ids = len(database.get_played_ids(target_id))

        total_winrate = database.get_total_winrate(target_id)
        total_ids = self.client.api_clients[game].playable_count

        longest_win_streak = database.get_longest_win_or_loss_streak(target_id, 1)
        longest_loss_streak = database.get_longest_win_or_loss_streak(target_id, -1)

        best_playable_wr, best_playable_games, best_playable_id = database.get_min_or_max_winrate_played(target_id, True)
        worst_playable_wr, worst_playable_games, worst_playable_id = database.get_min_or_max_winrate_played(target_id, False)

        if best_playable_id == worst_playable_id:
            # Person has not played 10 games with any champ/on any map. Try to get stats with 5 minimum games.
            worst_playable_wr, worst_playable_games, worst_playable_id = database.get_min_or_max_winrate_played(
                target_id, False, min_games=5
            )

        playable_name = "champions" if game == "lol" else "maps"

        response = (
            f"{nickname} has played a total of **{games_played}** games " +
            f"(**{total_winrate:.1f}%** was won).\n" +
            f"They have played **{num_played_ids}**/**{total_ids}** different {playable_name}.\n\n"
        )

        fmt_stat_names = get_formatted_stat_names(game)

        if game == "lol":
            rank_solo, rank_flex = database.get_current_rank(target_id)
            fmt_rank = get_formatted_stat_value(game, "rank_solo", rank_solo)
            response += f"Their current rank in {fmt_stat_names['rank_solo']} is **{fmt_rank}**.\n"

            fmt_rank = get_formatted_stat_value(game, "rank_solo", rank_flex)
            response += f"Their current rank in {fmt_stat_names['rank_flex']} is **{fmt_rank}**.\n\n"

        response += f"Their longest winning streak was **{longest_win_streak}** games.\n"
        response += f"Their longest loss streak was **{longest_loss_streak}** games.\n"

        if game == "cs2":
            ot_games, ot_winrate = database.get_overtime_winrate(target_id)
            response += f"Their winrate in overtime is **{ot_winrate}%** in **{ot_games}** games.\n\n"

        # If person has not played a minimum of 5 games with any champions/on any map, skip winrate stats.
        if best_playable_wr is not None and worst_playable_wr is not None and best_playable_id != worst_playable_id:
            best_playable_name = self.client.api_clients[game].get_playable_name(best_playable_id)
            worst_playable_name = self.client.api_clients[game].get_playable_name(worst_playable_id)
            response += (
                f"They perform best on **{best_playable_name}** (won " +
                f"**{best_playable_wr:.1f}%** of **{best_playable_games}** games).\n" +
                f"They perform worst on **{worst_playable_name}** (won " +
                f"**{worst_playable_wr:.1f}%** of **{worst_playable_games}** games).\n"
            )

        best_person_id, best_person_games, best_person_wr = database.get_winrate_relation(target_id, True)
        worst_person_id, worst_person_games, worst_person_wr = database.get_winrate_relation(target_id, False)

        if best_person_id == worst_person_id:
            worst_person_id, worst_person_games, worst_person_wr = database.get_winrate_relation(target_id, False, min_games=5)

        # If person has not played a minimum of 5 games with any person, skip person winrate stats.
        if best_person_wr is not None and worst_person_wr is not None and best_person_id != worst_person_id:
            best_person_name = self.client.get_discord_nick(best_person_id, self.message.guild.id)
            worst_person_name = self.client.get_discord_nick(worst_person_id, self.message.guild.id)
            response += (
                f"They perform best when playing with **{best_person_name}** (won " +
                f"**{best_person_wr:.1f}%** of **{best_person_games}** games).\n" +
                f"They perform worst when playing with **{worst_person_name}** (won " +
                f"**{worst_person_wr:.1f}%** of **{worst_person_games}** games).\n\n"
            )

        if game == "lol":
            role_stats = database.get_role_winrate(target_id)

            response += "Their winrate playing different roles:\n"

            for winrate, games, role in role_stats:
                role_name = get_formatted_stat_value(game, "role", role)
                response += (
                    f"- **{role_name}**: won **{winrate:.1f}%** of **{games}** games\n"
                )

            response += "\n"

        # Get performance score for person.
        score, rank, num_scores = database.get_performance_score(target_id)()

        response += (
            f"The *Personally Evaluated Normalized Int-Far Score* for {nickname} is " +
            f"**{score:.2f}**/**10**\nThis ranks them at **{rank}**/**{num_scores}**."
        )

        await self.message.channel.send(response)

class PerformanceCommand(Command):
    NAME = "performance"
    DESCRIPTION = (
        "Show you or someone else's Personally Evaluated Normalized Int Score."
    )
    TARGET_ALL = True
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = [GameParam("game"), TargetParam("person")]
    ALIASES = ["penis"]

    async def handle(self, game: str, target_id: int = None):
        performance_data = self.client.game_databases[game].get_performance_score(target_id)()
        game_name = api_util.SUPPORTED_GAMES[game]
        if target_id is None:
            response = f"*Personally Evaluated Normalized Int-Far Scores* for **{game_name}** for all users:"
            for score_id, score_value in performance_data:
                name = self.client.get_discord_nick(score_id, self.message.guild.id)
                response += f"\n- {name}: **{score_value:.2f}**"
        else:
            name = self.client.get_discord_nick(target_id, self.message.guild.id)
            score, rank, num_scores = performance_data

            response = (
                f"The *Personally Evaluated Normalized Int-Far Score* for {name} for **{game_name}** is " +
                f"**{score:.2f}**/**10**. This ranks him at **{rank}**/**{num_scores}**."
            )

        min_games = self.client.config.performance_mimimum_games
        score_fmt = "\nHigher score = better player (but smaller dick). Maximum is 10. "
        score_fmt += "These scores are" if target_id is None else "This score is"
        response += (
            f"\n{score_fmt} calculated using the ratio of " +
            "games being Int-Far, getting doinks, winning, being best in a stat, and total games played. " +
            f"You must have a minimum of {min_games} games to get a score."
        )

        await self.message.channel.send(response)

def get_winrate(client: DiscordClient, champ_or_map: str, game: str, target_id: int, role: str=None):
    winrate, games = client.game_databases[game].get_played_winrate(target_id, champ_or_map, role)
    qualified_name = client.api_clients[game].get_playable_name(champ_or_map)

    return qualified_name, winrate, games

class WinrateCommand(Command):
    NAME = "wr"
    DESCRIPTION = (
        "Show you or someone else's winrate. This command accepts different parameters "
        "for different games. For LoL you can see winrates on champions (f.x `!wr aphelios nønø`). "
        "In CS2 you can see winrates on maps (f.x. `!wr anubis`)."
    )
    ACCESS_LEVEL = "self"
    MANDATORY_PARAMS = [CommandParam("champion_or_map")]
    OPTIONAL_PARAMS = [
        GameParam("game"),
        CommandParam("role", choices=["top", "mid", "support", "bot", "jungle"], consume_if_unmatched=False),
        TargetParam("person")
    ]
    ALIASES = ["winrate"]

    async def handle(self, champ_or_map: str, game: str, role: str = None, target_id: int = None):
        playable_id = self.client.api_clients[game].try_find_playable_id(champ_or_map)

        if playable_id is None:
            played_name = "Champion" if game == "lol" else "Map"
            await self.message.channel.send(f"{played_name} is not valid.")
            return

        choices = WinrateCommand.OPTIONAL_PARAMS[1].choices
        if role is not None and role not in choices:
            target_id = role
            role = None

        qualified_name, winrate, games = get_winrate(self.client, playable_id, game, target_id, role)

        user_name = self.client.get_discord_nick(target_id, self.message.guild.id)
        if winrate is not None:
            if games == 0:
                response = f"{user_name} has not played any games on {qualified_name}."
            else:
                response = f"{user_name} has a **{winrate:.2f}%** winrate on {qualified_name} in **{int(games)}** games."
        else:
            response = f"{user_name} has not played any games on {qualified_name}."

        await self.message.channel.send(response)
