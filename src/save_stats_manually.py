import json
from database import Database
from config import Config
from discord_bot import DiscordClient
import riot_api

GAME_ID = 4772024774

auth = json.load(open("auth.json"))

conf = Config()

conf.discord_token = auth["discordToken"]
conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

conf.log("Initializing database...")

database_client = Database(conf)

class TestMock(DiscordClient):
    async def on_ready(self):
        await super(TestMock, self).on_ready()
        d1, sm1, si1 = self.database.discord_id_from_summoner("dumbledonger")
        d2, sm2, si2 = self.database.discord_id_from_summoner("nønø")
        d5, sm5, si5 = self.database.discord_id_from_summoner("senile felines")
        # self.users_in_game = [
        #     (d1, sm1, si1),
        #     (d2, sm2, si2),
        #     (d5, sm5, si5)
        # ]
        self.users_in_game = []
        self.active_game = GAME_ID
        game_info = self.riot_api.get_game_details(GAME_ID)
        filtered = self.get_filtered_stats(game_info)
        await self.save_stats(filtered, None, None, {})

conf.log("Starting Discord Client...")

client = TestMock(conf, database_client)

api = riot_api.APIClient(conf)

client.run(conf.discord_token)
