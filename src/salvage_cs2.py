from argparse import ArgumentParser
import asyncio
from glob import glob
import bz2
import os

from intfar.api.config import Config
from intfar.api.game_apis.cs2 import SteamAPIClient
from intfar.api.game_databases import get_database_client
from intfar.api.meta_database import MetaDatabase
from intfar.api.game_monitors.cs2 import CS2GameMonitor
from intfar.api.util import GUILD_MAP
from intfar.api.user import User
from intfar.discbot.commands.util import ADMIN_DISC_ID
from awpy import DemoParser

async def download_single_demo(config, steam_api, sharecode):
    demo_file = f"{config.resources_folder}/data/cs2/{sharecode}"

    if os.path.exists(demo_file + ".dem"):
        print(f"Demo file for sharecode '{sharecode}' already exists.")
        return

    game_stats = await steam_api.get_basic_match_info(sharecode)
    round_stats = game_stats["matches"][0]["roundstatsall"]
    demo_url = round_stats[-1]["map"]

    filename = await steam_api.download_demo_file(demo_file, demo_url)
    with open(filename + ".dem.bz2", "rb") as fp:
        all_bytes = fp.read()

    # Decompress the gz2 compressed demo file
    decompressed = bz2.decompress(all_bytes)
    with open(filename + ".dem", "wb") as fp:
        fp.write(decompressed)

    os.remove(filename + ".dem.bz2")

    print(f"Downloaded demo to {filename}.dem")

async def download_missing_demos(config, database, steam_api, sharecode):
    user = database.game_users[ADMIN_DISC_ID]
    steam_id = user.player_id[0]
    auth_code = user.match_auth_code[0]

    while sharecode is not None:
        await download_single_demo(config, steam_api, sharecode)

        sharecode = await steam_api.get_next_sharecode(steam_id, auth_code, sharecode)

async def parse_missing_demos(config, database, steam_api, sharecode):
    meta_database = MetaDatabase(config)
    game_monitor = CS2GameMonitor("cs2", config, meta_database, database, steam_api)
    guild_id = GUILD_MAP["nibs"]

    files = glob(f"{config.resources_folder}/data/cs2/*.dem")
    files.sort(key=lambda file: os.stat(file).st_ctime)

    skip = True
    for file in files:
        curr_sharecode = os.path.basename(file).split(".")[0]

        if skip and (sharecode is None or curr_sharecode == sharecode):
            skip = False

        if skip:
            continue

        print(f"Parsing {file}...")

        game_data = await steam_api.get_basic_match_info(curr_sharecode)
        game_data["gameId"] = sharecode

        parser = DemoParser(demofile=file)
        game_data.update(parser.parse())
        game_data["demo_parse_status"] = "parsed"

        active_players = []
        for disc_id in database.game_users.keys():
            active_players.append(database.game_users[disc_id])

        users_in_game = {}
        for player_data in game_data["playerConnections"]:
            for player in active_players:
                if player_data["steamID"] in player.player_id:
                    user = User.clone(player)
                    user.player_id = [player_data["steamID"]]
                    user.player_name = ["Name"]
                    users_in_game[player.disc_id] = user
                    break

        game_monitor.users_in_game[guild_id] = users_in_game

        status = game_monitor.get_finished_game_status(game_data, guild_id)
        if status != game_monitor.POSTGAME_STATUS_OK:
            print("Error, skipping:", file)
            continue

        game_monitor.handle_game_over(game_data, status, guild_id)
        os.remove(curr_sharecode + ".json")

if __name__ == "__main__":
    parser = ArgumentParser()

    parser.add_argument("task", choices=("download_one", "download_all", "parse"))
    parser.add_argument("sharecode")

    args = parser.parse_args()

    config = Config()
    database = get_database_client("cs2", config)
    steam_api = SteamAPIClient("cs2", config)

    loop = asyncio.new_event_loop()

    if args.task == "download_one":
        coroutine = download_single_demo(config, steam_api, args.sharecode)
    if args.task == "download_all":
        coroutine = download_missing_demos(config, database, steam_api, args.sharecode)
    elif args.task == "parse":
        coroutine = parse_missing_demos(config, database, steam_api, args.sharecode)

    loop.run_until_complete(coroutine)
