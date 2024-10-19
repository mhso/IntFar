import asyncio
from gevent import monkey, sleep
monkey.patch_all()

from mhooge_flask.logging import logger

from api.config import Config
from api.meta_database import MetaDatabase
from api.game_apis.cs2 import SteamAPIClient
from argparse import ArgumentParser

async def listen(database: MetaDatabase, client: SteamAPIClient):
    target_name = client.__class__.__name__
    sleep_time = 0.25
    close = False

    while True:
        for cmd_id, command, args in database.get_queued_commands(target_name):
            if command == "close":
                close = True
                break

            try:
                result = getattr(client, command)
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

    try:
        client = SteamAPIClient(args.game, config)

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()

        loop.run_until_complete(listen(database, client))

    except Exception as exc:
        print(exc)

    finally:
        client.close()
