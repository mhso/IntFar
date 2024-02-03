import os
from time import sleep

import requests

from api.meta_database import MetaDatabase
from api.config import Config
from discbot.discord_bot import DiscordClient

conf = Config()

database_client = MetaDatabase(conf)

client = DiscordClient(conf, database_client, None, None, None, None)

def download_emojis(disc_client: DiscordClient):
    emoji_data = disc_client.get_all_emojis()

    folder = "misc/emojis"

    if emoji_data and not os.path.exists(folder):
        os.mkdir(folder)

    for name, url in emoji_data:
        print(f"Downloading emoji '{name}'", flush=True)

        try:
            data = requests.get(url, stream=True)
            with open(f"{folder}/{name}.png", "wb") as fp:
                for chunk in data.iter_content(chunk_size=128):
                    fp.write(chunk)
        except requests.exceptions.RequestException as exc:
            print(f"Exception when getting emoji from Discord", flush=True)
            print(exc)

        sleep(1)

client.add_event_listener("ready", download_emojis, client)

client.run(conf.discord_token)
