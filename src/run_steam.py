import asyncio
from time import time
from gevent import monkey, sleep
monkey.patch_all()

from mhooge_flask.logging import logger

from intfar.api.config import Config
from intfar.api.meta_database import MetaDatabase
from intfar.api.game_apis.cs2 import SteamAPIClient
from argparse import ArgumentParser

RELOG_INTERVAL = 60 * 60 * 24

async def listen(database: MetaDatabase, client: SteamAPIClient):
    target_name = client.__class__.__name__
    sleep_time = 0.25
    time_since_relog = time()
    close = False

    while True:
        for cmd_id, command, args in database.get_queued_commands(target_name):
            if command == "close":
                close = True
                break

            try:
                result = getattr(client, command)

                if (
                    (asyncio.iscoroutinefunction(result) or callable(result))
                    and time() - time_since_relog > RELOG_INTERVAL
                    and (not client.is_logged_in() or not client.cs_client.ready)
                ):
                    # Check if we need to relog (Steam sometimes disconnects randomly)
                    logger.warning("Steam or CS2 client disconnected, trying to relog...")
                    client.login()
                    client.cs_client.launch()
                    time_since_relog = time()

                if asyncio.iscoroutinefunction(result):
                    result = await result(*args)
                elif callable(result):
                    result = result(*args)
            except AttributeError:
                result = None
            except Exception:
                logger.exception(f"Error in run_steam when calling '{command}'!")
                result = None

            database.set_command_result(cmd_id, target_name, result)

        if close:
            break

        try:
            sleep(sleep_time)
            await asyncio.sleep(sleep_time)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("game")
    args = parser.parse_args()

    logger.info("Starting Steam command handler process")

    config = Config()
    database = MetaDatabase(config)

    if config.env == "dev":
        exit(0)

    try:
        client = SteamAPIClient(args.game, config)
        asyncio.run(listen(database, client))

    except Exception as exc:
        print(exc)

    finally:
        if client:
            client.close()
