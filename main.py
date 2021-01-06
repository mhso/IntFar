import json
from multiprocessing import Process, Pipe
import run_flask
from api.database import Database
from api.bets import BettingHandler
from api.config import Config
from api.riot_api import APIClient
from discbot.discord_bot import run_client

if __name__ == "__main__":
    auth = json.load(open("discbot/auth.json"))

    conf = Config()
    conf.discord_token = auth["discordToken"]
    conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]
    conf.env = auth["env"]

    env_desc = "DEVELOPMENT" if conf.env == "dev" else "PRODUCTION"
    conf.log(f"+++++ Running in {env_desc} mode +++++")

    conf.log("Initializing database...")
    database_client = Database(conf)
    betting_handler = BettingHandler(conf, database_client)

    riot_api = APIClient(conf)

    conf.log("Starting Flask web app...")
    flask_end, bot_end_flask = Pipe()
    flask_process = Process(
        name="Flask Web App",
        target=run_flask.run_app,
        args=(
            database_client, betting_handler, riot_api, conf, flask_end
        )
    )
    flask_process.start()

    while True:
        conf.log("Starting Discord Client...")

        our_end, bot_end_us = Pipe()

        bot_process = Process(
            name="Discord Bot",
            target=run_client,
            args=(
                conf, database_client, betting_handler, riot_api, bot_end_us, bot_end_flask
            )
        )
        bot_process.start()

        try:
            our_end.recv() # Wait for bot to say it has died.
        except BrokenPipeError:
            print("Stopping bot...", flush=True)
            flask_process.kill()
        except KeyboardInterrupt:
            conf.log("Stopping bot...")
            exit(0)
