import json
from database import Database
from config import Config
from discord_bot import DiscordClient

class TestMock(DiscordClient):
    async def on_ready(self):
        super().on_ready()
        self.users_in_game = [
            self.database.discord_id_from_summoner("prince jarvan lv"),
            self.database.discord_id_from_summoner("senile felines"),
            self.database.discord_id_from_summoner("kazpariuz"),
            self.database.discord_id_from_summoner("stirred martini"),
            self.database.discord_id_from_summoner("zapiens")
        ]
        game = self.riot_api.get_game_details(4725659303)
        filtered = self.get_filtered_stats(game)
        donks_data = self.get_big_doinks(filtered)
        print(donks_data)

auth = json.load(open("auth.json"))

conf = Config()

conf.discord_token = auth["discordToken"]
conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

conf.log("Initializing database...")

database_client = Database(conf)

conf.log("Starting Discord Client...")

client = TestMock(conf, database_client)

client.run(conf.discord_token)
