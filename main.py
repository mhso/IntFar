import run_flask
from discbot import discord_bot

from time import sleep
from multiprocessing import Process, Pipe, Manager
from argparse import ArgumentParser

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

def kill_all_processes(processes):
    for process in processes:
        process.kill()

    while any(p.is_alive() for p in processes):
        sleep(0.1)


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
    sync_manager = Manager()

    game_databases = {game: get_database_client(game, conf) for game in SUPPORTED_GAMES}

    meta_database = MetaDatabase(conf)
    meta_database.clear_command_queue()

    # Convert database user dicts to synchronized proxies so they're synced across processes
    meta_database.all_users = sync_manager.dict(meta_database.all_users)
    for game_database in game_databases.values():
        game_database.game_users = sync_manager.dict(game_database.game_users)

    logger.info("Initializing game API clients...")
    proxy_manager = ProxyManager(SteamAPIClient, "cs2", meta_database, conf)

    api_clients = {
        "lol": RiotAPIClient("lol", conf),
        "cs2": proxy_manager.create_proxy()
    }

    betting_handlers = {game: get_betting_handler(game, conf, meta_database) for game in SUPPORTED_GAMES}

    # Start process with machine learning model
    # that trains in the background after each game.
    #ai_process, our_end_ai = start_ai_process(conf)

    logger.info("Starting Flask web app...")
    flask_args = [conf, meta_database, game_databases, betting_handlers, api_clients]
    flask_process, bot_end_flask = start_flask_process(*flask_args)

    logger.info("Starting Discord Client...")
    discord_args = [conf, meta_database, game_databases, betting_handlers, api_clients, None, bot_end_flask]
    bot_process, _ = start_discord_process(*discord_args)

    processes = [flask_process, bot_process, proxy_manager]

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
                sync_manager.shutdown()

                # Wait for all subprocesses to exit.
                kill_all_processes(processes)

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
            logger.info("Stopping Int-Far...")
            kill_all_processes(processes)
            break

if __name__ == "__main__":
    main()
