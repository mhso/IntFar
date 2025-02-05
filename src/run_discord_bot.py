import asyncio
from glob import glob
import os
import importlib
import traceback

from mhooge_flask.logging import logger

from api.config import Config
from api.util import GUILD_IDS, MY_GUILD_ID
from discbot.discord_bot import DiscordClient
from discbot.commands.base import handle_command, Command

def collect_commands(cmd_class: Command):
    """
    Go through each subclass of cmd_class.
    """
    if cmd_class.__subclasses__() == [] and cmd_class.NAME not in cmd_class.COMMANDS_DICT:
        if not cmd_class.GUILDS:
            cmd_class.GUILDS = GUILD_IDS

        if MY_GUILD_ID not in cmd_class.GUILDS:
           cmd_class.GUILDS.append(MY_GUILD_ID)

        cmd_class.COMMANDS_DICT[cmd_class.NAME] = cmd_class
        return

    for sub_cls in cmd_class.__subclasses__():
        collect_commands(sub_cls)

def initialize_commands(config: Config):
    files = glob(f"{config.src_folder}/discbot/commands/*.py")

    for file in files:
        basename = os.path.basename(file).replace(".py", "")
        if basename.startswith("_") or basename in ("base", "util"):
            continue

        importlib.import_module(f"discbot.commands.{basename}")

    collect_commands(Command)

def run_client(config, meta_database, game_databases, betting_handlers, api_clients, ai_pipe, flask_pipe, main_pipe):
    client = DiscordClient(
        config,
        meta_database,
        game_databases,
        betting_handlers,
        api_clients,
        ai_pipe=ai_pipe,
        flask_pipe=flask_pipe,
        main_pipe=main_pipe,
    )
    initialize_commands(client.config)
    client.add_event_listener("command", handle_command)

    async def runner():
        async with client:
            await client.start(config.discord_token, reconnect=True)

    try:
        asyncio.run(runner())
    except KeyboardInterrupt:
        return
    except Exception:
        logger.exception("Unhandled exception in Discord client")
        traceback.print_exc()
