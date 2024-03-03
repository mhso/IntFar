import asyncio
import argparse

from mhooge_flask.logging import logger

from api.bets import get_betting_handler
from api.game_apis import get_api_client
from api.game_databases import get_database_client
from api.config import Config
from api.meta_database import MetaDatabase
from api.util import GUILD_IDS, SUPPORTED_GAMES
from discbot.discord_bot import DiscordClient
from api.game_stats import GameStats

GUILDS = {
    "nibs": GUILD_IDS[0],
    "circus": GUILD_IDS[1],
    "core": GUILD_IDS[2]
}

class MockChannel:
    def __init__(self, dry_run=False):
        self.dry_run = dry_run

    async def send(self, data):
        if self.dry_run:
            print(data)

        await asyncio.sleep(0.1)

class TestMock(DiscordClient):
    def __init__(self, args, config, database, game_databases, betting_handlers, api_clients, **kwargs):
        super().__init__(config, database, game_databases, betting_handlers, api_clients, **kwargs)
        self.missing = args.missing
        self.game = args.game
        self.game_id = args.game_id
        self.guild_to_use = GUILDS.get(args.guild)
        self.task = args.task if not self.missing else "all"
        self.loud = not args.silent if not self.missing else False
        self.dry_run = args.dry_run
        self.forget_sharecode = args.forget_sharecode
        self.play_sound = args.sound.lower() in ("yes", "true", "1") if not self.missing else False
        self.users_in_game = args.users
        self.ai_model = kwargs.get("ai_model")

    def set_sharecode_mock(self, disc_id, steam_id, sharecode):
        pass

    def get_users_in_cs2_game(self, game_info):
        users_in_game = {}
        all_users = self.game_databases["cs2"].game_users
        round_stats = game_info["matches"][0]["roundstatsall"]

        max_player_round = 0
        max_players = 0
        for index, round_data in enumerate(round_stats):
            players_in_round = len(round_data["reservation"]["accountIds"])
            if players_in_round > max_players:
                max_players = players_in_round
                max_player_round = index

        for disc_id in all_users.keys():
            for steam_id in all_users[disc_id].ingame_id:
                account_id = self.api_clients[self.game].get_account_id(int(steam_id))
                if account_id in round_stats[max_player_round]["reservation"]["accountIds"]:
                    users_in_game[disc_id] = all_users[disc_id]
                    break

        return users_in_game

    def get_users_in_lol_game(self, game_info):
        users_in_game = {}
        all_users = self.game_databases["lol"].game_users

        for participant in game_info["participants"]:
            for disc_id in all_users.keys():
                if participant["summonerId"] in all_users[disc_id].ingame_id:
                    users_in_game[disc_id] = all_users[disc_id]
                    break

        return users_in_game

    async def play_event_sounds(self, game, intfar, doinks, guild_id):
        if self.play_sound:
            await super().play_event_sounds(game, intfar, doinks, guild_id)

    def save_stats(self, parsed_game_stats: GameStats):
        if self.task in ("all", "stats") and not self.dry_run:
            return super().save_stats(parsed_game_stats)

        return [], []

    async def on_ready(self):
        await super(TestMock, self).on_ready()

        if self.missing:
            ids_to_save = self.game_databases[self.game].get_missed_games()
        else:
            ids_to_save = [(self.game_id, self.guild_to_use)]

        for game_id, guild_id in ids_to_save:
            game_monitor = self.game_monitors[self.game]
            game_monitor.active_game[guild_id] = {"id": game_id}

            if not self.loud or self.dry_run:
                self.channels_to_write[guild_id] = MockChannel(self.dry_run)

            if self.forget_sharecode or self.dry_run:
                self.game_databases["cs2"].set_new_cs2_sharecode = self.set_sharecode_mock

            try:
                game_info = self.api_clients[self.game].get_game_details(self.game_id)
                if game_info is None:
                    raise ValueError("Game info is None!")
            except Exception:
                logger.exception("Failed to get game info for some reason!")
                continue

            if self.game == "cs2":
                game_monitor.users_in_game[guild_id] = self.get_users_in_cs2_game(game_info)
            elif self.game == "lol":
                game_monitor.users_in_game[guild_id] = self.get_users_in_lol_game(game_info)

            status = await game_monitor.get_finished_game_status(game_info, guild_id)

            await self.on_game_over(self.game, game_info, guild_id, status)

            if not self.dry_run:
                self.game_databases[self.game].remove_missed_game(game_id)

        await self.close()
        exit(0)

    async def user_joined_voice(self, member, guild, poll=False, join_sound=False):
        pass

parser = argparse.ArgumentParser()

parser.add_argument("--missing", action="store_true")
parser.add_argument("--game", type=str)
parser.add_argument("--game_id", type=str)
parser.add_argument("--guild", type=str, choices=GUILDS)
parser.add_argument("--task", type=str, choices=("all", "bets", "stats", "train"))
parser.add_argument("--sound", type=str, choices=("True", "1", "False", "0", "Yes", "yes", "No", "no"))
parser.add_argument("--forget_sharecode", "-fs", action="store_true")
parser.add_argument("--steam_2fa_code", type=str)
parser.add_argument("--users", type=int, nargs="+")
parser.add_argument("--dry_run", action="store_true")
parser.add_argument("-s", "--silent", action="store_true")

args = parser.parse_args()

if not args.missing:
    if None in (args.game, args.game_id, args.guild, args.task, args.sound):
        logger.warning("Either specificy --missing or all of --game, --guild, --task, and --sound")
        exit(0)

if not args.game in SUPPORTED_GAMES:
    logger.warning(f"Invalid game: {args.game}")
    exit(0)

conf = Config()
conf.steam_2fa_code = args.steam_2fa_code

logger.info("Initializing database...")

meta_database = MetaDatabase(conf)

logger.info("Starting Discord Client...")

game_databases = {game: get_database_client(game, conf) for game in SUPPORTED_GAMES}
betting_handlers = {game: get_betting_handler(game, conf, meta_database, game_databases[game]) for game in SUPPORTED_GAMES}
api_clients = {game: get_api_client(game, conf) for game in SUPPORTED_GAMES}

client = TestMock(args, conf, meta_database, game_databases, betting_handlers, api_clients)

client.run(conf.discord_token)
