import json
from time import sleep
from database import Database
from config import Config
from discord_bot import DiscordClient

auth = json.load(open("auth.json"))

conf = Config()

conf.discord_token = auth["discordToken"]
conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

database_client = Database(conf)

client = DiscordClient(conf, database_client)
client.run(conf.discord_token)

# while True:
#     if client.polling_is_active():
#         GAME_OVER = client.check_game_status()
#         if GAME_OVER:
#             client.declare_intfar()

#     sleep(conf.status_interval)
