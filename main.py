import json
from multiprocessing import Process, Pipe
import run_flask
from api.database import Database
from api.config import Config
from discbot.discord_bot import run_client

if __name__ == "__main__":
    auth = json.load(open("discbot/auth.json"))

    conf = Config()

    conf.log("Initializing database...")
    database_client = Database(conf)

    conf.log("Starting Flask web app...")
    flask_end, bot_end_flask = Pipe()
    flask_process = Process(target=run_flask.run_app, args=(database_client, flask_end))
    flask_process.start()

    conf.discord_token = auth["discordToken"]
    conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

    while True:
        conf.log("Starting Discord Client...")

        our_end, bot_end_us = Pipe()

        bot_process = Process(
            target=run_client, args=(conf, database_client, bot_end_us, bot_end_flask)
        )
        bot_process.start()

        try:
            our_end.recv() # Wait for bot to say it has died.
        except BrokenPipeError:
            print("Stopping bot.", flush=True)
            flask_process.kill()
