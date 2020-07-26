import json
import threading
from time import sleep
from database import Database
from config import Config
from discord_bot import DiscordClient
import game_stats
import riot_api

GAME_ID = 4727422254

auth = json.load(open("auth.json"))

conf = Config()

conf.discord_token = auth["discordToken"]
conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

conf.log("Initializing database...")

database_client = Database(conf)

class TestMock(DiscordClient):
    async def on_ready(self):
        super().on_ready()
        self.users_in_game = [
            self.database.discord_id_from_summoner("prince jarvan lv"),
            self.database.discord_id_from_summoner("senile felines"),
            self.database.discord_id_from_summoner("dumbledonger"),
            self.database.discord_id_from_summoner("stirred martini"),
            self.database.discord_id_from_summoner("nønø")
        ]
        game = self.riot_api.get_game_details(GAME_ID)
        filtered = self.get_filtered_stats(game)
        _, doinks = self.get_big_doinks(filtered)
        self.database.record_stats(None, "0000", doinks, GAME_ID, filtered, self.users_in_game)

conf.log("Starting Discord Client...")

client = TestMock(conf, database_client)

api = riot_api.APIClient(conf)

client.run(conf.discord_token)
