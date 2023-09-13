from gevent import monkey
monkey.patch_all()

import sys
import json

from gevent._socketcommon import wait_read

from api.config import Config
from api.game_api.csgo import SteamAPIClient
from argparse import ArgumentParser

parser = ArgumentParser()

parser.add_argument("game")
parser.add_argument("steam_2fa_code")

args = parser.parse_args()

config = Config()
config.steam_2fa_code = args.steam_2fa_code

log_stuff = open("sub_log.txt", "w", encoding="utf-8")

try:
    client = SteamAPIClient(args.game, config)

    while True:
        wait_read(sys.stdin.fileno())
        cmd = sys.stdin.readline()[:-2]

        log_stuff.write(f"Command: {cmd}\n")

        attr, *raw_args = cmd.split(":")
        args_str = ":".join(raw_args)
        args = args_str.split(";")

        log_stuff.write(f"Attribute: {attr}\n")
        log_stuff.write(f"Args: {args_str}\n")

        if attr == "close":
            break

        try:
            result = getattr(client, attr)
            if callable(result):
                result = result(*args)
        except AttributeError:
            result = None

        log_stuff.write(f"Result: {result}\n\n")

        if isinstance(result, dict) or isinstance(result, list):
            dtype = "json"
            encoded_val = json.dumps(result)
        else:
            dtype = "str"
            encoded_val = str(result)

        sys.stdout.write(f"{dtype}: {encoded_val}\n")
        sys.stdout.flush()

finally:
    log_stuff.close()
    client.close()