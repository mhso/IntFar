from time import sleep
from multiprocessing import Process, Pipe
from multiprocessing.connection import Connection

from discord.opus import load_opus
from mhooge_flask.logging import logger
from mhooge_flask.restartable import restartable

import run_flask
from api.bets import BettingHandler
from api.config import Config
from api.database import Database
from api.riot_api import RiotAPIClient
from ai import model
from discbot import discord_bot

def start_discord_process(
    config: Config,
    database: Database,
    betting_handler: BettingHandler,
    riot_api: RiotAPIClient,
    bot_end_ai: Connection,
    bot_end_flask: Connection
):
    """
    Run Discord bot in a separate process.
    """
    our_end, bot_end_us = Pipe()
    bot_process = Process(
        name="Discord Bot",
        target=discord_bot.run_client,
        args=(
            config, database, betting_handler, riot_api, bot_end_ai, bot_end_us, bot_end_flask
        )
    )
    bot_process.start()

    return bot_process, our_end

def start_flask_process(
    config: Config,
    database: Database,
    betting_handler: BettingHandler,
    riot_api: RiotAPIClient
):
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

@restartable
def main():
    conf = Config()

    env_desc = "DEVELOPMENT" if conf.env == "dev" else "PRODUCTION"

    logger.info(f"+++++ Running in {env_desc} mode +++++")

    if conf.env == "production":
        load_opus("/usr/local/lib/libopus.so")

    logger.info("Initializing database...")

    database_client = Database(conf)
    betting_handler = BettingHandler(conf, database_client)
    riot_api = RiotAPIClient(conf)

    # Start process with machine learning model
    # that trains in the background after each game.
    ai_process, our_end_ai = start_ai_process(conf)

    logger.info("Starting Flask web app...")
    flask_process, bot_end_flask = start_flask_process(
        conf, database_client, betting_handler, riot_api
    )

    logger.info("Starting Discord Client...")

    bot_process, our_end_bot = start_discord_process(
        conf, database_client, betting_handler, riot_api, our_end_ai, bot_end_flask
    )

    while True:
        try:
            if flask_process.exitcode == 3:
                # 'Soft' reset processes.
                logger.info("Restarting Flask process.")

                flask_process, bot_end_flask = start_flask_process(
                    conf,
                    database_client,
                    betting_handler,
                    riot_api
                )
                ai_process.kill()

                ai_process, our_end_ai = start_ai_process(conf)
                bot_process.kill()
                bot_process, our_end_bot = start_discord_process(
                    conf, database_client, betting_handler, riot_api, our_end_ai, bot_end_flask
                )

            if flask_process.exitcode == 2 or bot_process.exitcode == 2:
                # We have issued a restart command on Discord or the website to restart the program.
                ai_process.kill()
                flask_process.kill()
                bot_process.kill()

                # Wait for all subprocesses to exit.
                processes = [ai_process, flask_process, bot_process]
                while all(p.is_alive() for p in processes):
                    sleep(0.5)

                logger.info(f"++++++ Restarting {__file__} ++++++")

                exit(2)

            sleep(1)

        except BrokenPipeError:
            logger.info("Stopping bot...")
            if bot_process.is_alive():
                bot_process.kill()
            ai_process.kill()
            flask_process.kill()
            break

        except KeyboardInterrupt:
            logger.info("Stopping bot...")
            break

if __name__ == "__main__":
    main()
