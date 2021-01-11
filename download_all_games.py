import json
import os
from time import sleep
from api.config import Config
from api.riot_api import APIClient
from api.database import Database

auth = json.load(open("discbot/auth.json"))

config = Config()

config.riot_key = auth["riotDevKey"] if config.use_dev_token else auth["riotAPIKey"]

riot_api = APIClient(config)
database_client = Database(config)

game_ids = database_client.get_game_ids()

for game_id in game_ids:
    print(f"Downloading game with ID {game_id}...")
    filename = f"data/game_{game_id[0]}.json"
    if os.path.exists(filename):
        print("Game is already downloaded, skipping...")
        continue

    with open(f"data/game_{game_id[0]}.json", "w", encoding="utf-8") as fp:
        game_info = riot_api.get_game_details(game_id[0])
        json.dump(game_info, fp)

    sleep(2)
