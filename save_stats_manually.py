import asyncio
import argparse

from mhooge_flask.logging import logger

from api.awards import get_awards_handler
from api.bets import get_betting_handler
from api.config import Config
from api.database import Database
from api.game_data import get_stat_parser
from api.util import GUILD_IDS, SUPPORTED_GAMES
from ai.model import Model
from discbot.discord_bot import DiscordClient

GUILDS = {
    "nibs": GUILD_IDS[0],
    "circus": GUILD_IDS[1],
    "core": GUILD_IDS[2]
}

class MockChannel:
    async def send(self, data):
        await asyncio.sleep(0.1)

class TestMock(DiscordClient):
    def __init__(self, args, config, database, betting_handlers, riot_api, **kwargs):
        super().__init__(config, database, betting_handlers, riot_api, **kwargs)
        self.missing = args.missing
        self.game = args.game
        self.game_id = args.game_id
        self.guild_to_use = GUILDS.get(args.guild)
        self.task = args.task if not self.missing else "all"
        self.loud = not args.silent if not self.missing else False
        self.play_sound = args.sound.lower() in ("yes", "true", "1") if not self.missing else False
        self.ai_model = kwargs.get("ai_model")

    async def on_ready(self):
        await super(TestMock, self).on_ready()

        if self.missing:
            ids_to_save = self.database.get_missed_games(self.game)
        else:
            ids_to_save = [(self.game_id, self.guild_to_use)]

        for game_id, guild_id in ids_to_save:
            self.game_monitors[self.game].active_game[guild_id] = {"id": game_id}

            if self.game == "lol":
                game_info = self.riot_api.get_game_details(game_id)
                self.game_monitors[self.game].active_game[guild_id]["queue_id"] = game_info["queueId"]
            elif self.game == "csgo":
                game_info = self.steam_api.get_game_details(game_id)


            game_stats_parser = get_stat_parser(self.game, game_info, self.database.users[self.game])
            parsed_game_stats = game_stats_parser.parse_data()
            awards_handler = get_awards_handler(self.game, self.config, parsed_game_stats)

            intfar, response = self.get_intfar_data(awards_handler)

            doinks, doinks_response = self.get_doinks_data(awards_handler)
            if doinks_response is not None:
                response += "\n" + self.insert_emotes(doinks_response)

            game_streak_response = self.get_win_loss_streak_data(awards_handler)

            if game_streak_response is not None:
                response += "\n" + game_streak_response

            if self.loud and self.task == "all":
                await self.send_message_unprompted(response, guild_id)

            await asyncio.sleep(1)

            response = ""

            if self.task in ("all", "bets"):
                if not self.loud:
                    self.channels_to_write[guild_id] = MockChannel()

                response, max_tokens_id, new_max_tokens_id = self.resolve_bets(parsed_game_stats)
                if max_tokens_id != new_max_tokens_id:
                    await self.assign_top_tokens_role(max_tokens_id, new_max_tokens_id)

            if self.task in ("all", "stats"):
                try:
                    best_records, worst_records = self.save_stats(parsed_game_stats)

                    if best_records != [] or worst_records != []:
                        records_response = self.get_beaten_records_msg(
                            parsed_game_stats, best_records, worst_records
                        )
                        response = records_response + response
                except Exception:
                    logger.bind(game_id=game_id).exception(
                        f"Error when saving stats for {game_id}. Probably already exists."
                    )
                    continue

            if self.loud and self.task == "all":
                await self.send_message_unprompted(response, guild_id)

            if self.play_sound:
                await self.play_event_sounds(self.game, intfar, doinks, guild_id)

            # if self.ai_model is not None and self.task in ("all", "train"):
            #     logger.info("Training AI Model with new game data.")
            #     train_data = shape_predict_data(
            #         self.database, self.riot_api, self.config, users_in_game
            #     )
            #     loss = train_online(
            #         self.ai_model, train_data, filtered[0][1]["gameWon"]
            #     )
            #     self.ai_model.save()
            #     logger.info(f"Loss: {loss}")

            # if self.config.generate_predictions_img:
            #     predictions_img = None
            #     for user_data in users_in_game:
            #         if ADMIN_DISC_ID == user_data[0]:
            #             predictions_img = create_predictions_timeline_image()
            #             break

            #     if predictions_img is not None:
            #         await self.send_predictions_timeline_image(predictions_img, guild_id)

            self.database.remove_missed_game(self.game, game_id)

    async def user_joined_voice(self, member, guild, poll=False):
        pass

parser = argparse.ArgumentParser()

parser.add_argument("--missing", action="store_true")
parser.add_argument("--game_id", type=int)
parser.add_argument("--game", type=str)
parser.add_argument("--guild", type=str, choices=GUILDS)
parser.add_argument("--task", type=str, choices=("all", "bets", "stats", "train"))
parser.add_argument("--sound", type=str, choices=("True", "1", "False", "0", "Yes", "yes", "No", "no"))
parser.add_argument("-s", "--silent", action="store_true")

args = parser.parse_args()

if not args.missing:
    if None in (args.game, args.guild, args.task, args.sound):
        logger.warning("Either specificy --missing or all of --game, --guild, --task, and --sound")

conf = Config()

logger.info("Initializing database...")

database_client = Database(conf)

logger.info("Starting Discord Client...")

betting_handlers = {game: get_betting_handler(game, conf, database_client) for game in SUPPORTED_GAMES}
ai_model = Model(conf)
ai_model.load()

client = TestMock(args, conf, database_client, betting_handlers, ai_model=ai_model)

client.run(conf.discord_token)
