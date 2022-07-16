import sys, subprocess, signal
from time import sleep
from multiprocessing import Process, Pipe

from discord.opus import load_opus
from mhooge_flask.logging import logger

import run_flask
from api.audio_handler import AudioHandler
from api.bets import BettingHandler
from api.config import Config
from api.database import Database
from api.shop import ShopHandler
from api.riot_api import APIClient
from ai import model
from discbot import discord_bot

def start_discord_process(config, database, betting_handler, riot_api, audio_handler, shop_handler, bot_end_ai, bot_end_flask):
    our_end, bot_end_us = Pipe()
    bot_process = Process(
        name="Discord Bot",
        target=discord_bot.run_client,
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

def main():
    conf = Config()

    env_desc = "DEVELOPMENT" if conf.env == "dev" else "PRODUCTION"
    logger.info(f"+++++ Running in {env_desc} mode +++++")

    if conf.env == "production":
        load_opus("/usr/local/lib/libopus.so")

    logger.info("Initializing database...")

    database_client = Database(conf)
    betting_handler = BettingHandler(conf, database_client)
    shop_handler = ShopHandler(conf, database_client)
    audio_handler = AudioHandler(conf)
    riot_api = APIClient(conf)

    # Start process with machine learning model
    # that trains in the background after each game.
    ai_process, our_end_ai = start_ai_process(conf)

    logger.info("Starting Flask web app...")
    flask_process, bot_end_flask = start_flask_process(
        database_client, betting_handler, riot_api, conf
    )

    logger.info("Starting Discord Client...")

    bot_process, our_end_bot = start_discord_process(
        conf, database_client, betting_handler, riot_api,
        audio_handler, shop_handler, our_end_ai, bot_end_flask
    )

    while True:
        try:
            if flask_process.exitcode == 2:
                # 'Soft' reset processes.
                logger.info("Restarting Flask process.")

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

            if bot_process.exitcode == 2:
                # We have issued a restart command on Discord to restart the program.
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
            print("Stopping bot...", flush=True)
            if bot_process.is_alive():
                bot_process.kill()
            ai_process.kill()
            flask_process.kill()
            break

        except KeyboardInterrupt:
            logger.info("Stopping bot...")
            break

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "child":
        # This runs the actual program. It runs in a subprocess
        # if 'child' is given as an argument on the CLI.
        main()
        exit(0)

    # Run a master process that starts the actual program in a child process and monitors it.
    # If the child process exits with return code 2, restart it.
    try:
        while True:
            # Start child process that runs the actual program.
            process = subprocess.Popen([sys.executable, __file__, "child"])

            while process.poll() is None: # Wait for child process to exit.
                sleep(0.1)

            if process.returncode == 2: # Process requested a restart.
                sleep(1) # Sleep for a sec and restart while loop.
            else:
                break # Process exited naturally, terminate program.

    except KeyboardInterrupt:
        # We have to handle interrupt signal differently on Linux vs. Windows.
        if sys.platform == "linux":
            sig = signal.SIGINT
        else:
            sig = signal.CTRL_C_EVENT
    
        # End child process and terminate program.
        process.send_signal(sig)

        # Wait for child process to exit properly.
        while process.poll() is None:
            sleep(0.1)
