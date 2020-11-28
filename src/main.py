import json
from multiprocessing import Process, Pipe
from database import Database
from config import Config
from discord_bot import DiscordClient

def run_client(config, database, pipe):
    client = DiscordClient(config, database, pipe)
    client.run(conf.discord_token)

auth = json.load(open("auth.json"))

conf = Config()

conf.discord_token = auth["discordToken"]
conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

while True:
    conf.log("Initializing database...")

    database_client = Database(conf)

    conf.log("Starting Discord Client...")

    our_end, bot_end = Pipe()

    p = Process(target=run_client, args=(conf, database_client, bot_end))
    p.start()

    try:
        our_end.recv() # Wait for bot to say it has died.
    except BrokenPipeError:
        print("Stopping bot.")
