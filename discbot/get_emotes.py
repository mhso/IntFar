import json
from api.database import Database
from api.config import Config
from discbot.discord_bot import DiscordClient
import threading

conf = Config()

conf.log("Initializing database...")

database_client = Database(conf)

conf.log("Starting Discord Client...")

client = DiscordClient(conf, database_client, None, None, None)

def do_stuff(disc_client):
    print(disc_client.get_all_emojis())

threading.Thread(target=do_stuff, args=(client,)).start()

client.run(conf.discord_token)
