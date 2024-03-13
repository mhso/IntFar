from argparse import ArgumentParser
from api.config import Config
from discbot.discord_bot import DiscordClient
from api.game_apis import get_api_client
from api.game_databases import get_database_client
from api.meta_database import MetaDatabase
from api.register import register_for_game
from api.util import SUPPORTED_GAMES, GUILD_MAP

parser = ArgumentParser()

parser.add_argument("game", choices=SUPPORTED_GAMES)
parser.add_argument("discord_name_or_id")
parser.add_argument("ingame_name")
parser.add_argument("--extra_1")
parser.add_argument("--extra_2")
parser.add_argument("--guild", choices=GUILD_MAP, default="nibs")

args = parser.parse_args()

config = Config()
meta_database = MetaDatabase(config)
game_databases = {game: get_database_client(game, config) for game in SUPPORTED_GAMES}
api_clients = {game: get_api_client(game, config) for game in SUPPORTED_GAMES}

client = DiscordClient(config, meta_database, game_databases, None, api_clients)

async def add_user(disc_id):
    game_args = [arg for arg in (args.ingame_name, args.extra_1, args.extra_2) if arg]
    status, msg = register_for_game(meta_database, game_databases[args.game], api_clients[args.game], disc_id, *game_args)

    print("Status code:", status)
    print(msg)

    await client.close()

async def find_discord_id():
    name_or_id = args.discord_name_or_id
    try:
        if not client.meta_database.user_exists(int(name_or_id)):
            raise ValueError("User not found")

        disc_id = int(name_or_id)
    except ValueError:
        disc_id = client.get_discord_id(name_or_id, GUILD_MAP[args.guild])

        if disc_id is None:
            print(f"Could not find discord ID for user '{name_or_id}'")
            await client.close()
            return

    await add_user(disc_id)

client.add_event_listener("ready", find_discord_id)
client.run(config.discord_token)
