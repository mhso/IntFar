from glob import glob
import os
import importlib

from discbot.discord_bot import DiscordClient
from discbot.commands.base import handle_command, Command

def collect_commands(cmd_class):
    if cmd_class.__subclasses__() == []:
        cmd_class.COMMANDS_DICT[cmd_class.NAME] = cmd_class
        return

    for sub_cls in cmd_class.__subclasses__():
        collect_commands(sub_cls)

def initialize_commands(client: DiscordClient):
    files = glob(os.path.dirname(__file__))

    for file in files:
        basename = os.path.basename(file)
        if basename.startswith("_") or basename in ("base.py", "util.py"):
            continue

        importlib.import_module(f".{basename}")

    collect_commands(Command)

    client.add_event_listener("command", handle_command)

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
    initialize_commands(client)

    client.run(config.discord_token)
