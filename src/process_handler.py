import json
from discord_bot import DiscordClient
from database import Database
from config import Config

def run_client(config, database):
    client = DiscordClient(config, database)
    client.run(config.discord_token)

if __name__ == "__main__":
    
    auth = json.load(open("auth.json"))

    conf = Config()

    conf.discord_token = auth["discordToken"]
    conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

    conf.log("Initializing database...")

    database_client = Database(conf)

    conf.log("Starting Discord Client...")

    run_client(conf, database_client)
