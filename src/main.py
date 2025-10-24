from run_flask import run_app as run_flask_app
from run_discord_bot import run_client as run_discord_client

from time import sleep
from multiprocessing import Process, Pipe, Manager

from discord.opus import load_opus
from mhooge_flask.logging import logger
from mhooge_flask.restartable import restartable

from api.config import Config
from api.meta_database import MetaDatabase
from api.game_databases import get_database_client
from api.util import SUPPORTED_GAMES
from api.proxy import ProxyManager

from api.game_apis.lol import RiotAPIClient
from api.game_apis.cs2 import SteamAPIClient
from api.bets import get_betting_handler
#from ai import model

def start_discord_process(*args):
    """
    Run Discord bot in a separate process.
    """
    our_end, bot_end_us = Pipe()
    bot_process = Process(
        name="Discord Bot",
        target=run_discord_client,
        args=args + (bot_end_us,)
    )
    bot_process.start()

    return bot_process, our_end

def start_flask_process(*args):
    flask_end, bot_end_flask = Pipe()
    flask_process = Process(
        name="Flask Web App",
        target=run_flask_app,
        args=(
            args + (flask_end,)
        )
    )
    flask_process.start()

    return flask_process, bot_end_flask

def kill_all_processes(processes):
    for process in processes:
        process.kill()

    max_sleep = 10
    time_slept = 0
    interval = 0.5

    while time_slept < max_sleep and any(p.is_alive() for p in processes):
        sleep(interval)
        time_slept += interval

    sleep(0.25)

    if time_slept >= max_sleep:
        logger.warning("Some processes could not be killed!")
        sleep(0.25)
        exit(1)

@restartable
def main():
    config = Config()

    env_desc = "DEVELOPMENT" if config.env == "dev" else "PRODUCTION"

    logger.info(f"+++++ Running in {env_desc} mode +++++")

    if config.env == "production":
        load_opus("/usr/local/lib/libopus.so")

    logger.info("Initializing databases...")
    sync_manager = Manager()

    game_databases = {game: get_database_client(game, config) for game in SUPPORTED_GAMES}

    meta_database = MetaDatabase(config)
    meta_database.clear_command_queue()

    # Convert database user dicts to synchronized proxies so they're synced across processes
    meta_database.all_users = sync_manager.dict(meta_database.all_users)
    for game_database in game_databases.values():
        game_database.game_users = sync_manager.dict(game_database.game_users)

    logger.info("Initializing game API clients...")
    proxy_manager = ProxyManager(SteamAPIClient, "cs2", meta_database)

    api_clients = {
        "lol": RiotAPIClient("lol", config),
        "cs2": proxy_manager.create_proxy(func_timeouts={"get_game_details": 200})
    }

    betting_handlers = {
        game: get_betting_handler(game, config, meta_database, game_databases[game])
        for game in SUPPORTED_GAMES
    }

    # Start flask app hosting Int-Far website
    logger.info("Starting Flask web app...")
    flask_args = [config, meta_database, game_databases, betting_handlers, api_clients]
    flask_process, bot_end_flask = start_flask_process(*flask_args)

    # Start Discord client process
    logger.info("Starting Discord Client...")
    discord_args = [config, meta_database, game_databases, betting_handlers, api_clients, None, bot_end_flask]
    bot_process, _ = start_discord_process(*discord_args)

    processes = [flask_process, bot_process, proxy_manager]

    while True:
        try:
            if flask_process.exitcode == 3:
                # 'Soft' reset processes.
                logger.info("Restarting Flask process.")

                flask_process, bot_end_flask = start_flask_process(*flask_args)

                bot_process.kill()
                bot_process, _ = start_discord_process(*discord_args)

            if flask_process.exitcode == 2 or bot_process.exitcode == 2:
                # We have issued a restart command on Discord or the website to restart the program.
                sync_manager.shutdown()

                # Wait for all subprocesses to exit.
                kill_all_processes(processes)

                exit(2)

            sleep(1)

        except BrokenPipeError:
            logger.info("Stopping bot...")
            if bot_process.is_alive():
                bot_process.kill()

            flask_process.kill()
            break

        except KeyboardInterrupt:
            logger.info("Stopping Int-Far...")
            kill_all_processes(processes)
            break

if __name__ == "__main__":
    main()
