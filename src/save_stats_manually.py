import json
import threading
from time import sleep
from database import Database
from config import Config
from discord_bot import DiscordClient
import game_stats
import riot_api

GAME_ID = 4730151627

auth = json.load(open("auth.json"))

conf = Config()

conf.discord_token = auth["discordToken"]
conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

conf.log("Initializing database...")

database_client = Database(conf)

class TestMock(DiscordClient):
    async def on_ready(self):
        await super(TestMock, self).on_ready()
        d1, sm1, si1 = self.database.discord_id_from_summoner("prince jarvan lv")
        d2, sm2, si2 = self.database.discord_id_from_summoner("dumbledonger")
        d3, sm3, si3 = self.database.discord_id_from_summoner("nønø")
        d4, sm4, si4 = self.database.discord_id_from_summoner("stirred martini")
        d5, sm5, si5 = self.database.discord_id_from_summoner("senile felines")
        self.users_in_game = [
            (d1, [sm1], [si1]),
            (d2, [sm2], [si2]),
            (d3, [sm3], [si3]),
            (d4, [sm4], [si4]),
            (d5, [sm5], [si5])
        ]

        self.active_game = GAME_ID
        await self.declare_intfar()

conf.log("Starting Discord Client...")

client = TestMock(conf, database_client)

api = riot_api.APIClient(conf)

client.run(conf.discord_token)
