import json
from database import Database
from config import Config
from discord_bot import DiscordClient
import game_stats
import riot_api

GAME_ID = 4774682598

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
        d5, sm5, si5 = self.database.discord_id_from_summoner("senile felines")
        self.active_game = GAME_ID
        game_info = self.riot_api.get_game_details(GAME_ID)
        filtered = self.get_filtered_stats(game_info)
        print(len(filtered))
        print(game_stats.get_outlier_stat("kills", filtered))

conf.log("Starting Discord Client...")

client = TestMock(conf, database_client)

api = riot_api.APIClient(conf)

client.run(conf.discord_token)
