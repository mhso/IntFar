from gevent import monkey, sleep
monkey.patch_all()

import json

from api.config import Config
from api.meta_database import MetaDatabase
from api.game_apis.cs2 import SteamAPIClient
from argparse import ArgumentParser

if __name__ == "__main__":
    parser = ArgumentParser()

    parser.add_argument("game")
    parser.add_argument("steam_2fa_code")

    args = parser.parse_args()

    if args.steam_2fa_code is None or args.steam_2fa_code == "None":
        exit(0)

    config = Config()
    config.steam_2fa_code = args.steam_2fa_code
    database = MetaDatabase(config)

    try:
        client = SteamAPIClient(args.game, config)
        target_name = client.__class__.__name__
        sleep_time = 0.5
        close = False

        while True:
            for cmd_id, command, args_str in database.get_queued_commands(target_name):
                args = args_str.split(",")
                if command == "close":
                    close = True
                    break

                if len(args) == 1 and args[0] == "":
                    args = []

                try:
                    result = getattr(client, command)
                    if callable(result):
                        result = result(*args)
                except AttributeError:
                    result = None

                encoded_val = str(result)

                if isinstance(result, dict) or isinstance(result, list):
                    dtype = "json"
                    encoded_val = json.dumps(result)
                elif result is None:
                    dtype = "null"
                else:
                    dtype = type(result).__name__

                result_str = f"{dtype}:{encoded_val}"
                database.set_command_result(cmd_id, target_name, result_str)

            if close:
                break

            sleep(sleep_time)

    finally:
        client.close()
