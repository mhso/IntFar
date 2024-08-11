from argparse import ArgumentParser
import bz2
import os

from api.config import Config
from api.game_apis.cs2 import SteamAPIClient
from api.game_databases import get_database_client
from discbot.commands.util import ADMIN_DISC_ID

parser = ArgumentParser()

parser.add_argument("sharecode")
parser.add_argument("steam_2fa_code")

args = parser.parse_args()

config = Config()
config.steam_2fa_code = args.steam_2fa_code

database = get_database_client("cs2", config)
steam_api = SteamAPIClient("cs2", config)

user = database.game_users[ADMIN_DISC_ID]
steam_id = user.player_id[0]
auth_code = user.match_auth_code[0]

sharecode = args.sharecode

while sharecode is not None:
    demo_file = f"{config.resources_folder}/data/cs2/{sharecode}"

    if not os.path.exists(demo_file + ".dem"):
        game_stats = steam_api.get_basic_match_info(sharecode)
        round_stats = game_stats["matches"][0]["roundstatsall"]
        demo_url = round_stats[-1]["map"]

        filename = steam_api.download_demo_file(demo_file, demo_url)
        with open(filename + ".dem.bz2", "rb") as fp:
            all_bytes = fp.read()

        # Decompress the gz2 compressed demo file
        decompressed = bz2.decompress(all_bytes)
        with open(filename + ".dem", "wb") as fp:
            fp.write(decompressed)

        os.remove(filename + ".dem.bz2")
    
        print(f"Downloaded demo to {filename}.dem")

    sharecode = steam_api.get_next_sharecode(steam_id, auth_code, sharecode)
