import asyncio
import argparse

from mhooge_flask.logging import logger

from api.bets import get_betting_handler
from api.game_api import get_api_client
from api.config import Config
from api.database import Database
from api.util import GUILD_IDS, SUPPORTED_GAMES
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
    def __init__(self, args, config, database, betting_handlers, api_clients, **kwargs):
        super().__init__(config, database, betting_handlers, api_clients, **kwargs)
        self.missing = args.missing
        self.game = args.game
        self.game_id = args.game_id
        self.guild_to_use = GUILDS.get(args.guild)
        self.task = args.task if not self.missing else "all"
        self.loud = not args.silent if not self.missing else False
        self.play_sound = args.sound.lower() in ("yes", "true", "1") if not self.missing else False
        self.users_in_game = args.users
        self.ai_model = kwargs.get("ai_model")

    async def on_ready(self):
        await super(TestMock, self).on_ready()

        if self.missing:
            ids_to_save = self.database.get_missed_games(self.game)
        else:
            ids_to_save = [(self.game_id, self.guild_to_use)]

        for game_id, guild_id in ids_to_save:
            game_monitor = self.game_monitors[self.game]
            game_monitor.active_game[guild_id] = {"id": game_id}
            game_monitor.users_in_game[guild_id] = {
                disc_id: self.database.users_by_game[self.game][disc_id]
                for disc_id in self.users_in_game
            }

            if not self.loud:
                self.channels_to_write[guild_id] = MockChannel()

            try:
                game_info, status = await game_monitor.get_finished_game_info(guild_id)
            except Exception:
                logger.exception("Failed to get game info for some reason!")
                exit(0)

            await self.on_game_over(self.game, game_info, guild_id, status)

            self.database.remove_missed_game(self.game, game_id)

    async def user_joined_voice(self, member, guild, poll=False):
        pass

parser = argparse.ArgumentParser()

parser.add_argument("--missing", action="store_true")
parser.add_argument("--game", type=str)
parser.add_argument("--game_id", type=int)
parser.add_argument("--guild", type=str, choices=GUILDS)
parser.add_argument("--task", type=str, choices=("all", "bets", "stats", "train"))
parser.add_argument("--sound", type=str, choices=("True", "1", "False", "0", "Yes", "yes", "No", "no"))
parser.add_argument("--steam_2fa_code", type=str)
parser.add_argument("--users", type=int, nargs="+")
parser.add_argument("-s", "--silent", action="store_true")

args = parser.parse_args()

if not args.missing:
    if None in (args.game, args.guild, args.task, args.sound, args.users):
        logger.warning("Either specificy --missing or all of --game, --guild, --task, and --sound")
        exit(0)

if not args.game in SUPPORTED_GAMES:
    logger.warning(f"Invalid game: {args.game}")
    exit(0)

conf = Config()
conf.steam_2fa_code = args.steam_2fa_code

logger.info("Initializing database...")

database_client = Database(conf)

logger.info("Starting Discord Client...")

betting_handlers = {game: get_betting_handler(game, conf, database_client) for game in SUPPORTED_GAMES}
api_clients = {game: get_api_client(game, conf) for game in SUPPORTED_GAMES}

client = TestMock(args, conf, database_client, betting_handlers, api_clients)

client.run(conf.discord_token)
