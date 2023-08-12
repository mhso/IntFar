from time import sleep
from multiprocessing import Process, Pipe
from argparse import ArgumentParser

from discord.opus import load_opus
from mhooge_flask.logging import logger
from mhooge_flask.restartable import restartable

import run_flask
from api.config import Config
from api.database import Database
from api.riot_api import RiotAPIClient
from api.util import SUPPORTED_GAMES
from api.bets import get_betting_handler
#from ai import model
from discbot import discord_bot

def start_discord_process(*args):
    """
    Run Discord bot in a separate process.
    """
    our_end, bot_end_us = Pipe()
    bot_process = Process(
        name="Discord Bot",
        target=discord_bot.run_client,
        args=args + (bot_end_us,)
    )
    bot_process.start()

    return bot_process, our_end

def start_flask_process(*args):
    flask_end, bot_end_flask = Pipe()
    flask_process = Process(
        name="Flask Web App",
        target=run_flask.run_app,
        args=(
            args + (flask_end,)
        )
    )
    flask_process.start()

    return flask_process, bot_end_flask

# def start_ai_process(config):
#     ai_end, bot_end_ai = Pipe()
#     ai_process = Process(
#         name="AI Model",
#         target=model.run_loop,
#         args=(config, ai_end)
#     )
#     ai_process.start()

#     return ai_process, bot_end_ai

@restartable
def main():
    parser = ArgumentParser()
    parser.add_argument("--steam_2fa_code", type=str, default=None)

    args = parser.parse_args()

    conf = Config()
    conf.steam_2fa_code = args.steam_2fa_code

    env_desc = "DEVELOPMENT" if conf.env == "dev" else "PRODUCTION"

    logger.info(f"+++++ Running in {env_desc} mode +++++")

    if conf.env == "production":
        load_opus("/usr/local/lib/libopus.so")

    logger.info("Initializing database...")

    database_client = Database(conf)
    betting_handlers = {game: get_betting_handler(game) for game in SUPPORTED_GAMES}
    riot_api = RiotAPIClient(conf)

    # Start process with machine learning model
    # that trains in the background after each game.
    #ai_process, our_end_ai = start_ai_process(conf)

    logger.info("Starting Flask web app...")
    flask_args = [database_client, betting_handlers, riot_api, conf]
    flask_process, bot_end_flask = start_flask_process(*flask_args)

    logger.info("Starting Discord Client...")
    discord_args = [conf, database_client, betting_handlers, riot_api, None, bot_end_flask]
    bot_process, _ = start_discord_process(*discord_args)

    while True:
        try:
            if flask_process.exitcode == 3:
                # 'Soft' reset processes.
                logger.info("Restarting Flask process.")

                flask_process, bot_end_flask = start_flask_process(*flask_args)
                #ai_process.kill()

                #ai_process, our_end_ai = start_ai_process(conf)
                bot_process.kill()
                bot_process, _ = start_discord_process(*discord_args)

            if flask_process.exitcode == 2 or bot_process.exitcode == 2:
                # We have issued a restart command on Discord or the website to restart the program.
                #ai_process.kill()
                flask_process.kill()
                bot_process.kill()

                # Wait for all subprocesses to exit.
                processes = [flask_process, bot_process]
                while all(p.is_alive() for p in processes):
                    sleep(0.5)

                logger.info(f"++++++ Restarting {__file__} ++++++")

                exit(2)

            sleep(1)

        except BrokenPipeError:
            logger.info("Stopping bot...")
            if bot_process.is_alive():
                bot_process.kill()
            #ai_process.kill()
            flask_process.kill()
            break

        except KeyboardInterrupt:
            logger.info("Stopping bot...")
            break

if __name__ == "__main__":
    main()
