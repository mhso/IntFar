import json
from time import sleep
from multiprocessing import Process, Pipe

import run_flask
from api.audio_handler import AudioHandler
from api.bets import BettingHandler
from api.config import Config
from api.database import Database
from api.shop import ShopHandler
from api.riot_api import APIClient
from ai import model
from discbot.discord_bot import run_client

def start_discord_process(config, database, betting_handler, riot_api, audio_handler, shop_handler, bot_end_ai, bot_end_flask):
    our_end, bot_end_us = Pipe()
    bot_process = Process(
        name="Discord Bot",
        target=run_client,
        args=(
            config, database, betting_handler, riot_api, audio_handler, shop_handler, bot_end_ai, bot_end_us, bot_end_flask
        )
    )
    bot_process.start()
    return bot_process, our_end

def start_flask_process(database, betting_handler, riot_api, config):
    flask_end, bot_end_flask = Pipe()
    flask_process = Process(
        name="Flask Web App",
        target=run_flask.run_app,
        args=(
            database, betting_handler, riot_api, config, flask_end
        )
    )
    flask_process.start()
    return flask_process, bot_end_flask

def start_ai_process(config):
    ai_end, bot_end_ai = Pipe()
    ai_process = Process(
        name="AI Model",
        target=model.run_loop,
        args=(config, ai_end)
    )
    ai_process.start()
    return ai_process, bot_end_ai

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
    shop_handler = ShopHandler(conf, database_client)
    audio_handler = AudioHandler(conf)
    riot_api = APIClient(conf)
    ai_process, our_end_ai = start_ai_process(conf)

    conf.log("Starting Flask web app...")
    flask_process, bot_end_flask = start_flask_process(
        database_client, betting_handler,
        riot_api, conf
    )

    conf.log("Starting Discord Client...")

    bot_process, our_end_bot = start_discord_process(
        conf, database_client, betting_handler, riot_api,
        audio_handler, shop_handler, our_end_ai, bot_end_flask
    )

    while True:
        try:
            if flask_process.exitcode == 1:
                conf.log("Restarting Flask process.")
                flask_process, bot_end_flask = start_flask_process(
                    database_client, betting_handler,
                    riot_api, conf
                )
                ai_process.kill()
                ai_process, our_end_ai = start_ai_process(conf)
                bot_process.kill()
                bot_process, our_end_bot = start_discord_process(
                    conf, database_client, betting_handler, riot_api,
                    audio_handler, shop_handler, our_end_ai, bot_end_flask
                )
            if bot_process.exitcode == 1:
                bot_process, our_end_bot = start_discord_process(
                    conf, database_client, betting_handler, riot_api,
                    audio_handler, shop_handler, our_end_ai, bot_end_flask
                )
        except BrokenPipeError:
            print("Stopping bot...", flush=True)
            ai_process.kill()
            flask_process.kill()
        except KeyboardInterrupt:
            conf.log("Stopping bot...")
            exit(0)

        sleep(1)
