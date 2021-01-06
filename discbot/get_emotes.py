import json
from api.database import Database
from api.config import Config
from discbot.discord_bot import DiscordClient
import threading

auth = json.load(open("discbot/auth.json"))

conf = Config()

conf.discord_token = auth["discordToken"]
conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

conf.log("Initializing database...")

database_client = Database(conf)

conf.log("Starting Discord Client...")

client = DiscordClient(conf, database_client, None, None, None)

def do_stuff(disc_client):
    print(disc_client.get_all_emojis())

threading.Thread(target=do_stuff, args=(client,)).start()

client.run(conf.discord_token)
