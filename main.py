import json
from os import getpid
from multiprocessing import Process, Pipe
import run_flask
from api.database import Database
from api.config import Config
from discbot.discord_bot import DiscordClient

def run_client(config, database, pipe):
    client = DiscordClient(config, database, pipe)
    print(f"Client process PID: {getpid()}", flush=True)
    client.run(config.discord_token)

if __name__ == "__main__":
    auth = json.load(open("discbot/auth.json"))

    conf = Config()

    conf.log("Starting Flask web app...")
    flask_process = Process(target=run_flask.run_app)
    flask_process.start()

    conf.discord_token = auth["discordToken"]
    conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

    while True:
        conf.log("Initializing database...")

        database_client = Database(conf)

        conf.log("Starting Discord Client...")

        our_end, bot_end = Pipe()

        print(f"Main PID: {getpid()}", flush=True)

        bot_process = Process(target=run_client, args=(conf, database_client, bot_end))
        bot_process.start()

        try:
            print(our_end.recv(), flush=True) # Wait for bot to say it has died.
        except BrokenPipeError:
            print("Stopping bot.")
            flask_process.kill()
