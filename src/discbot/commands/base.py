from abc import abstractmethod
from typing import Dict, List, Literal, Tuple
from discord import Message
from discbot.commands import util as commands_util
from discbot.discord_bot import DiscordClient
from api.meta_database import DEFAULT_GAME
from api.util import SUPPORTED_GAMES

from mhooge_flask.logging import logger
from mhooge_flask.database import DBException

class CommandParsingError(Exception):
    pass

class CommandParam:
    def __init__(self, name, default=None, choices=None, consume_if_unmatched=True):
        self.name = name
        self.default = default
        self.choices = choices
        self.consume_if_unmatched = consume_if_unmatched

    def __str__(self):
        return self.name

class TargetParam(CommandParam):
    def __init__(self, name, default="me", return_val: str = "disc_id", end_index=None):
        super().__init__(name, default)

        self.return_val = return_val
        self.end_index = end_index

    def extract_target_name(self, cmd_input, start_index, end_index):
        if len(cmd_input) > start_index:
            return " ".join(cmd_input[start_index:end_index])

        return self.default

    def get_target_id(self, arguments, index, client, author_id, guild_id, all_allowed):
        end_index = len(arguments) if self.end_index is None else self.end_index
        target_name = self.extract_target_name(arguments, index, end_index)

        if target_name is None:
            return None

        if target_name == "me": # Target ourselves.
            return author_id

        # Target someone else.
        target_name = target_name.lower().strip()
        if target_name in ("all", "ever"):
            if all_allowed:
                return None
            else:
                raise CommandParsingError("'All' target is not valid for this command.")

        # Try to match target_name with a user.
        target_id = client.try_get_user_data(target_name, guild_id)

        if target_id is None:
            msg = f"Error: Invalid summoner or Discord name {client.get_emoji_by_name('PepeHands')}"
            raise CommandParsingError(msg)

        return target_id

class PlayableParam(CommandParam):
    def get_played_id(self, game, cmd_input, start_index, client):
        index = start_index
        name = ""
        prev_played_id = None
        games_to_try = [game] if game is not None else SUPPORTED_GAMES

        while index < len(cmd_input):
            name = name + cmd_input[index]

            for game in games_to_try:
                played_id = client.api_clients[game].try_find_playable_id(name)
                if played_id is None and prev_played_id is not None:
                    return prev_played_id, index - start_index

            prev_played_id = played_id

            name += " "
            index += 1

        return prev_played_id, index - start_index

class GameParam(CommandParam):
    def __init__(self, name, default=DEFAULT_GAME):
        super().__init__(name, default)

class Command:
    NAME: str
    DESCRIPTION: str
    TARGET_ALL: bool = False
    ACCESS_LEVEL: Literal["all", "self", "unrestricted"] = "unrestricted"
    MANDATORY_PARAMS: List[CommandParam] = []
    OPTIONAL_PARAMS: List[CommandParam] = []
    ALIASES: List[str] = []
    GUILDS: List[str] = None
    COMMANDS_DICT: Dict[str, "Command"] = commands_util.COMMANDS

    def __init__(self, client: DiscordClient, message: Message):
        self.client = client
        self.message = message

    @abstractmethod
    async def handle(self, *args):
        ...

    async def parse_args(self, args: List[str]):
        author_id = self.message.author.id
        user = self.client.meta_database.all_users.get(author_id)

        parsed_args = []
        index = 0
        for param in self.MANDATORY_PARAMS + self.OPTIONAL_PARAMS:
            if isinstance(param, TargetParam): # Parameter targetting a person.
                value = param.get_target_id( # Get Discord ID of targetted person.
                    args,
                    index,
                    self.client,
                    self.message.author.id,
                    self.message.guild.id,
                    self.TARGET_ALL
                )

                # If we are targetting ourselves, but are not registered, send an error msg.
                if user is None and self.ACCESS_LEVEL == "self" and value == author_id:
                    await self.message.channel.send(
                        "You must be registered to Int-Far:tm: " +
                        "to target yourself with this command."
                    )
                    return None

                parsed_args.append(value)
                index += 1

            elif isinstance(param, PlayableParam):
                # Try to find game from previously parsed args
                game = user.default_game if user is not None else DEFAULT_GAME
                for arg in parsed_args:
                    if arg in SUPPORTED_GAMES:
                        game = arg
                        break

                played_id, consumed_params = param.get_played_id(game, args, index, self.client)
                if played_id is not None:
                    index += consumed_params

                parsed_args.append(played_id)

            elif isinstance(param, GameParam):
                if index >= len(args):
                    game_value = user.default_game or param.default if param.default else None

                    parsed_args.append(game_value)
                    continue

                if args[index] not in SUPPORTED_GAMES:
                    # If no game is supplied, but it was mandatory, show an error
                    if param in self.MANDATORY_PARAMS:
                        valid_games = ", ".join(f"`{game}`" for game in SUPPORTED_GAMES)
                        await self.message.channel.send(
                            f"Invalid game '{args[index]}'. This command targets a specific "
                            f"game which should be one of: {valid_games}."
                        )
                        return None

                    game_value = user.default_game or param.default if param.default else None

                    parsed_args.append(game_value)
                    continue

                parsed_args.append(args[index])
                index += 1

            elif index < len(args): # Regular parameter.
                if not param.choices or args[index] in param.choices:
                    parsed_args.append(args[index])
                    index += 1
                elif param.consume_if_unmatched:
                    index += 1

        return parsed_args

    async def __call__(self, args):
        try:
            user = self.client.meta_database.all_users.get(self.message.author.id)

            # If command requires user to be registered, and they are not, send error msg.
            if user is None and self.ACCESS_LEVEL == "all":
                await self.message.channel.send(
                    "You must be registered to Int-Far:tm: to use this command."
                )
                return

            parsed_args = await self.parse_args(args)
            # If an error happened, or we are not authorized to use this command, return.
            if parsed_args is None: 
                return

            await self.handle(*parsed_args) # Execute command using handler.

        except CommandParsingError as arg_exception:
            # Log error during command handling
            logger.bind(input_list=args).exception("Error when handling Discord command")
            await self.message.channel.send(self.client.insert_emotes(arg_exception.args[0]))

        except DBException:
            # Log database error during command handling
            logger.bind(input_list=args).exception("Database error when handling Discord command")

            response = "Something went wrong when querying the database! "
            response += self.client.insert_emotes("{emote_fu}")
            await self.message.channel.send(response)

        except Exception:
            logger.bind(input_list=args).exception("Unknown error when handling Discord command")

            mention_str = self.client.get_mention_str(commands_util.ADMIN_DISC_ID, self.message.guild.id)
            response = (
                "An error occurred when handling that command {emote_gual_yikes}\n"
                f"That's totally on {mention_str}, he'll fix it ASAP!"
            )
            await self.message.channel.send(self.client.insert_emotes(response))

    def format_params_list(self, params):
        """
        Create a string that shows which mandatory 
        and optional parameters the command accepts.
        """
        if params == "mandatory":
            params_list = self.MANDATORY_PARAMS
            l_brace, r_brace = "[", "]"
        else:
            params_list = self.OPTIONAL_PARAMS
            l_brace, r_brace = "(", ")"

        if params_list == []:
            return ""

        param_list_str = [
            f'{x}/"all"' if isinstance(x, TargetParam) and self.TARGET_ALL else str(x)
            for x in params_list
        ]

        return f"{l_brace}" + f"{r_brace} {l_brace}".join(param_list_str) + f"{r_brace}"

    def __str__(self):
        """
        Create string representation of command.
        This returns the name of the command
        as well as a description of the mandatory and optional parameters.
        """
        cmd_str = self.NAME
        for alias in self.ALIASES:
            cmd_str += f"/!{alias}"

        params_str_1 = self.format_params_list("mandatory")
        params_str_2 = self.format_params_list("optional")
        if params_str_1 != "":
            params_str_1 = " " + params_str_1

        if params_str_2 != "":
            params_str_2 = " " + params_str_2
        params_str = f"{params_str_1}{params_str_2}"

        return f"!{cmd_str}{params_str}"

def get_handler(cmd: str, client: DiscordClient, message: Message) -> Command:
    cmd_name = cmd
    handler = None

    if cmd not in commands_util.COMMANDS:
        # Check in "cute" commands.
        if cmd in commands_util.CUTE_COMMANDS:
            handler = commands_util.CUTE_COMMANDS[cmd]

        # Check in admin commands.
        elif cmd in commands_util.ADMIN_COMMANDS:
            handler = commands_util.ADMIN_COMMANDS[cmd]

        # Check for aliases.
        else:
            for possible_alias in commands_util.COMMANDS:
                if cmd in commands_util.COMMANDS[possible_alias].ALIASES:
                    cmd_name = possible_alias
                    break

            handler = commands_util.COMMANDS[cmd_name]
    
    else:
        handler = commands_util.COMMANDS[cmd_name]

    return handler(client, message)

def is_command_valid(message: Message, cmd: str, args: List[str]) -> Tuple[bool, bool]:
    """
    Check if a command, with the given arguments, appears valid
    and return the appropriate handler if so.
    """
    if cmd in commands_util.ADMIN_COMMANDS:
        return message.author.id == commands_util.ADMIN_DISC_ID, False

    if cmd in commands_util.CUTE_COMMANDS:
        return True, False

    is_main_cmd = cmd in commands_util.COMMANDS
    valid_cmd = None
    if is_main_cmd:
        valid_cmd = cmd

    for possible_alias in commands_util.COMMANDS:
        if cmd in commands_util.COMMANDS[possible_alias].ALIASES:
            valid_cmd = possible_alias
            break

    if valid_cmd is None:
        return False, False # Command is not valid.

    if message.guild.id not in commands_util.COMMANDS[valid_cmd].GUILDS:
        return False, False # Command is not valid in the current guild.

    mandatory_params = commands_util.COMMANDS[valid_cmd].MANDATORY_PARAMS

    for index in range(len(mandatory_params)):
        if args is None or len(args) <= index:
            return False, True # Command has missing mandatory params

    return True, False

def handle_command(client: DiscordClient, message: Message, command: str, args: List[str]):
    """
    Check if a command, with the given arguments, appears valid
    and return the appropriate handler if so.
    """
    valid_command, show_usage = is_command_valid(message, command, args)
    if valid_command:
        handler = get_handler(command, client, message)
    elif show_usage:
        handler = get_handler("usage", client, message)
    else:
        handler = None

    return handler
