import json
from database import Database
from config import Config
from discord_bot import DiscordClient

auth = json.load(open("auth.json"))

conf = Config()

conf.discord_token = auth["discordToken"]
conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

conf.log("Initializing database...")

database_client = Database(conf)

conf.log("Starting Discord Client...")

client = DiscordClient(conf, database_client)
client.run(conf.discord_token)
