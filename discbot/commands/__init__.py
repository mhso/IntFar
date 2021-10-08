from discbot.commands.admin import *
from discbot.commands.bets import *
from discbot.commands.doinks import *
from discbot.commands.intfar import *
from discbot.commands.lists import *
from discbot.commands.meta import *
from discbot.commands.misc import *
from discbot.commands.shop import *
from discbot.commands.stats import *
from discbot.commands.sounds import *
from discbot.commands import util as commands_util
from api.database import DBException

class TargetParam:
    def __init__(self, name, default="me", end_index=None):
        self.name = name
        self.default = default
        self.end_index = end_index

    def extract_target_name(self, cmd_input, start_index):
        end_index = len(cmd_input) if self.end_index is None else self.end_index
        if len(cmd_input) > start_index:
            return " ".join(cmd_input[start_index:end_index])
        return self.default

    def get_target_id(self, arguments, index, client, author_id, guild_id, all_allowed):
        target_name = self.extract_target_name(arguments, index)
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
                raise ValueError("'All' target is not valid for this command.")

        # Try to match target_name with a user.
        target_id = client.try_get_user_data(target_name, guild_id)

        if target_id is None:
            msg = f"Error: Invalid summoner or Discord name {client.get_emoji_by_name('PepeHands')}"
            raise ValueError(msg)

        return target_id

    def __str__(self):
        return self.name

class RegularParam:
    def __init__(self, name):
        self.name = name

    def __str__(self):
        return self.name

class Command:
    def __init__(
        self, command, description, handler, target_all=False, access_level=None,
        mandatory_params=[], optional_params=[], aliases=[], parser=None
    ):
        self.cmd = command
        self.desc = description
        self.handler = handler
        self.target_all = target_all
        self.access_level = access_level
        self.mandatory_params = mandatory_params
        self.optional_params = optional_params
        self.aliases = aliases
        self.parser = parser

    async def parse_args(self, client, message, args):
        author_id = message.author.id
        user_is_registered = client.database.user_exists(author_id)

        # If command requires user to be registered, and he is not, send error msg.
        if not user_is_registered and self.access_level == "all":
            await message.channel.send(
                "You must be registered to Int-Far:tm: to use this command."
            )
            return None

        if self.parser is not None: # Use custom parser, if given (for '!bet' fx.).
            return self.parser(client, args)

        parsed_args = []
        for index, param in enumerate(self.mandatory_params + self.optional_params):
            if isinstance(param, TargetParam): # Parameter targetting a person.
                value = param.get_target_id( # Get Discord ID of targetted person.
                    args, index, client, message.author.id,
                    message.guild.id, self.target_all
                )
                # If we are targetting ourselves, but are not registered, send an error msg.
                if not user_is_registered and self.access_level == "self" and value == author_id:
                    await message.channel.send(
                        "You must be registered to Int-Far:tm: " +
                        "to target yourself with this command."
                    )
                    return None
                parsed_args.append(value)
            elif index < len(args): # Regular parameter.
                parsed_args.append(args[index])

        return parsed_args

    async def handle_command(self, client, message, input_list):
        try:
            handler_args = [client, message]
            cmd_specific_args = await self.parse_args(client, message, input_list)
            # If an error happened, or we are not authorized to use this command, return.
            if cmd_specific_args is None: 
                return

            handler_args += cmd_specific_args

            await self.handler(*handler_args) # Execute command using handler.

        except ValueError as arg_exception:
            await message.channel.send(client.insert_emotes(arg_exception.args[0]))
            client.config.log(arg_exception, client.config.log_error)

        except DBException as db_exception:
            response = "Something went wrong when querying the database! "
            response += client.insert_emotes("{emote_fu}")
            await message.channel.send(response)
            client.config.log(db_exception, client.config.log_error)

    def format_params_list(self, params):
        if params == "mandatory":
            params_list = self.mandatory_params
            l_brace, r_brace = "[", "]"
        else:
            params_list = self.optional_params
            l_brace, r_brace = "(", ")"

        if params_list == []:
            return ""

        param_list_str = [str(x) for x in params_list]

        return f"{l_brace}" + f"{r_brace} {l_brace}".join(param_list_str) + f"{r_brace}"

    def __str__(self):
        cmd_str = self.cmd
        for alias in self.aliases:
            cmd_str += f"/!{alias}"

        params_str_1 = self.format_params_list("mandatory")
        params_str_2 = self.format_params_list("optional")
        if params_str_1 != "":
            params_str_1 = " " + params_str_1

        if params_str_2 != "":
            params_str_2 = " " + params_str_2
        params_str = f"{params_str_1}{params_str_2}`"
        return f"`!{cmd_str}{params_str}"

def get_handler(cmd):
    cmd_name = cmd

    if cmd not in commands_util.COMMANDS:
        # Check in "cute" commands.
        if cmd in commands_util.CUTE_COMMANDS:
            return commands_util.CUTE_COMMANDS[cmd]

        # Check in admin commands.
        if cmd in commands_util.ADMIN_COMMANDS:
            return commands_util.ADMIN_COMMANDS[cmd]

        # Check for aliases.
        for possible_alias in commands_util.COMMANDS:
            if cmd in commands_util.COMMANDS[possible_alias].aliases:
                cmd_name = possible_alias
                break

    return commands_util.COMMANDS[cmd_name]

def register_command(
    name, desc, handler, target_all=False, access_level=None,
    mandatory_params=[], optional_params=[], aliases=[], parser=None,
    command_dict=commands_util.COMMANDS
):
    command_dict[name] = Command(
        name, desc, handler, target_all, access_level,
        mandatory_params, optional_params, aliases, parser
    )

def initialize_commands():
    """
    This is where all the commands are defined.
    """
    # register command
    register_name = "register"
    register_desc = (
        "Sign up for the Int-Far™ Tracker™ " +
        "by providing your summoner name."
    )
    register_command(
        register_name, register_desc, handle_register_msg,
        mandatory_params=[RegularParam("summoner_name")]
    )

    # unregister command
    unregister_name = "unregister"
    unregister_desc = (
        "Leave the Int-Far™ Tracker™. You can re-join later with !register, " +
        "and your data will not be deleted."
    )
    register_command(
        unregister_name, unregister_desc, handle_unregister_msg, access_level="all"
    )

    # users command
    users_name = "users"
    users_desc = "List all users who are currently signed up for the Int-Far:tm: Tracker:tm:."
    register_command(users_name, users_desc, handle_users_msg)

    # help command
    help_name = "help"
    help_desc = "Show the helper text." 
    register_command(help_name, help_desc, handle_helper_msg)

    # commands command
    commands_name = "commands"
    commands_desc = "Show this list of commands."
    register_command(commands_name, commands_desc, handle_commands_msg)

    # usage command
    usage_name = "usage"
    usage_desc = "Show how to use a given command."
    register_command(
        usage_name, usage_desc, handle_usage_msg,
        mandatory_params=[RegularParam("command")]
    )

    # stats command
    stats_name = "stats"
    stats_desc = "Show a list of available stat keywords to check."
    register_command(
        stats_name, stats_desc, handle_stats_msg
    )

    # intfar command.
    intfar_name = "intfar"
    intfar_desc = (
        "Show how many times you (or someone else) has been the Int-Far. " +
        "`!intfar all` lists Int-Far stats for all users."
    )
    register_command(
        intfar_name, intfar_desc, handle_intfar_msg, True, "self",
        optional_params=[TargetParam("person")]
    )

    # intfar relations command.
    intfar_relations_name = "intfar_relations"
    intfar_relations_desc = "Show who you (or someone else) int the most games with."
    register_command(
        intfar_relations_name, intfar_relations_desc, handle_intfar_relations_msg,
        access_level="self", optional_params=[TargetParam("person")]
    )

    # intfar criteria command
    intfar_criteria_name = "intfar_criteria"
    intfar_criteria_desc = (
        "List the things that need to happen for a person to get " +
        "Int-Far because of a specific criteria. Fx. `!intfar_criteria kda`."
    )
    register_command(
        intfar_criteria_name, intfar_criteria_desc, handle_intfar_criteria_msg,
        optional_params=[RegularParam("criteria")]
    )

    # doinks command
    doinks_name = "doinks"
    doinks_desc = (
        "Show big doinks plays you (or someone else) did! " +
        "`!doinks all` lists all doinks stats for all users."
    )
    register_command(
        doinks_name, doinks_desc, handle_doinks_msg, True, "self",
        optional_params=[TargetParam("person")]
    )

    # doinks relations command.
    doinks_relations_name = "doinks_relations"
    doinks_relations_desc = "Show who you (or someone else) get Big Doinks the most with."
    register_command(
        doinks_relations_name, doinks_relations_desc, handle_doinks_relations_msg,
        access_level="self", optional_params=[TargetParam("person")]
    )

    # doinks criteria command
    doinks_criteria_name = "doinks_criteria"
    doinks_criteria_desc = "Show the different criterias needed for acquiring a doink."
    register_command(doinks_criteria_name, doinks_criteria_desc, handle_doinks_criteria_msg)

    # best command
    best_name = "best"
    best_desc = (
        "Show how many times you (or someone else) " +
        "were the best in the specific stat. " +
        "Fx. `!best kda` shows how many times you had the best KDA in a game. " +
        "`!best [stat] all` shows what the best ever was for that stat, and who got it."
    )
    async def stats_best_wrapper(client, message, stat, target_id):
        await handle_stat_msg(client, message, True, stat, target_id)

    register_command(
        best_name, best_desc, stats_best_wrapper, True, "self",
        mandatory_params=[RegularParam("stat")], optional_params=[TargetParam("person")],
        aliases=["most", "highest"]
    )

    # worst command
    worst_name = "worst"
    worst_desc = (
        "Show how many times you (or someone else) " +
        "were the worst at the specific stat. " +
        "`!worst [stat] all` shows what the worst ever was for that stat, and who got it."
    )

    async def stats_worst_wrapper(client, message, stat, target_id):
        await handle_stat_msg(client, message, False, stat, target_id)

    register_command(
        worst_name, worst_desc, stats_worst_wrapper, True, "self",
        mandatory_params=[RegularParam("stat")], optional_params=[TargetParam("person")],
        aliases=["least", "lowest", "fewest"]
    )

    # uptime command
    uptime_name = "uptime"
    uptime_desc = "Show for how long the bot has been up and running."
    register_command(uptime_name, uptime_desc, handle_uptime_msg)

    # status command
    status_name = "status"
    status_desc = "Show overall stats about Int-Far."
    register_command(status_name, status_desc, handle_status_msg)

    # game command
    game_name = "game"
    game_desc = "See details about the league match the given person is in, if any."
    register_command(
        game_name, game_desc, handle_game_msg, mandatory_params=[TargetParam("person")]
    )

    # betting command
    betting_name = "betting"
    betting_desc = "Show information about betting, as well as list of possible events to bet on."
    register_command(betting_name, betting_desc, handle_betting_msg)

    # bet command
    bet_name = "bet"
    bet_desc = (
        "Bet a specific amount of credits on one or more events happening " +
        "in the current or next game. Fx. `!bet 100 game_win`, `!bet all intfar slurp` " +
        "or `!bet 20 game_win & 30 no_intfar` (bet on game win *AND* no Int-Far)."
    )
    register_command(
        bet_name, bet_desc, handle_make_bet_msg, access_level="all", parser=get_bet_params
    )

    # cancel bet command
    cancel_bet_name = "cancel_bet"
    cancel_bet_desc = (
        "Cancel a previously placed bet with the given parameters. " +
        "To cancel a multi-bet, provide the ticket generated for that bet. " +
        "A bet can't be cancelled when a game has started."
    )   
    register_command(
        cancel_bet_name, cancel_bet_desc, handle_cancel_bet_msg, access_level="all",
        mandatory_params=[RegularParam("event/ticket")],
        optional_params=[TargetParam("person", None)]
    )

    # give command
    give_name = "give"
    give_desc = "Give good-boi points to someone."
    register_command(
        give_name, give_desc, handle_give_tokens_msg, access_level="all",
        mandatory_params=[RegularParam("amount"), TargetParam("person")]
    )

    # active bets command
    active_bets_name = "active_bets"
    active_bets_desc = "See a list of your (or someone else's) active bets."
    register_command(
        active_bets_name, active_bets_desc, handle_active_bets_msg,
        True, "self", optional_params=[TargetParam("person")]
    )

    # bets command
    bets_name = "bets"
    bets_desc = "See a description your (or someone else's) lifetime bets."
    register_command(
        bets_name, bets_desc, handle_all_bets_msg, access_level="self",
        optional_params=[TargetParam("person")]
    )

    # betting tokens command
    betting_tokens_name = "betting_tokens"
    betting_tokens_desc = "See how many betting tokens you (or someone else) has."
    register_command(
        betting_tokens_name, betting_tokens_desc, handle_token_balance_msg,
        True, "self", optional_params=[TargetParam("person")],
        aliases=["gbp"]
    )

    # bet_return command
    bet_return_name = "bet_return"
    bet_return_disc = (
        "See the return award of a specific betting " +
        "event (targetting 'person', if given)."
    )
    register_command(
        bet_return_name, bet_return_disc, handle_bet_return_msg,
        access_level="self", mandatory_params=[RegularParam("event")],
        optional_params=[TargetParam("person", None)]
    )

    # website command
    website_name = "website"
    website_desc = "See information about the Int-Far website."
    register_command(website_name, website_desc, handle_website_msg)

    # website profile command
    website_profile_name = "website_profile"
    website_profile_desc = "Get a link to your (or someone else's) Int-Far profile."
    register_command(
        website_profile_name, website_profile_desc, handle_profile_msg,
        access_level="self", optional_params=[TargetParam("person")]
    )

    # website verify command
    website_verify_name = "website_verify"
    website_verify_desc = (
        "Get a secret link that when opened will " +
        "verify and log you in on the Int-Far website."
    )
    register_command(
        website_verify_name, website_verify_desc,
        handle_verify_msg, access_level="all"
    )

    # report command
    report_name = "report"
    report_desc = "Report someone, f.x. if they are being a poon."
    register_command(
        report_name, report_desc, handle_report_msg, access_level="all",
        mandatory_params=[TargetParam("person")]
    )

    # reports command
    report_name = "reports"
    report_desc = "See how many times someone (or yourself) has been reported."
    register_command(
        report_name, report_desc, handle_see_reports_msg, True, "self",
        optional_params=[TargetParam("person")]
    )

    # doinks sound command
    doinks_sound_name = "doinks_sound"
    doinks_sound_desc = "Set a sound to trigger when you are awarded Doinks."
    async def doinks_sound_wrapper(client, message, sound=None):
        await handle_set_event_sound(client, message, sound, "doinks")

    register_command(
        doinks_sound_name, doinks_sound_desc, doinks_sound_wrapper,
        access_level="all", optional_params=[RegularParam("sound")]
    )

    # intfar sound command
    intfar_sound_name = "intfar_sound"
    intfar_sound_desc = "Set a sound to trigger when you are awarded Doinks."
    async def intfar_sound_wrapper(client, message, sound=None):
        await handle_set_event_sound(client, message, sound, "intfar")

    register_command(
        intfar_sound_name, intfar_sound_desc, intfar_sound_wrapper,
        access_level="all", optional_params=[RegularParam("sound")]
    )

    # play command
    play_name = "play"
    play_desc = "Play a sound! (See `!sounds` for a list of them)."
    register_command(
        play_name, play_desc, handle_play_sound_msg,
        mandatory_params=[RegularParam("sound")]
    )

    # sounds command
    sounds_name = "sounds"
    sounds_desc = "See a list of all possible sounds to play."
    register_command(sounds_name, sounds_desc, handle_sounds_msg)

    # shop command
    shop_name = "shop"
    shop_desc = (
        "Get a list of totally real items that you " +
        "can buy with your hard-earned betting tokens!"
    )
    register_command(shop_name, shop_desc, handle_shop_msg)

    # buy command
    buy_name = "buy"
    buy_desc = (
        "Buy one or more copies of an item from the shop at a " +
        "given price (or cheapest if no price is given)."
    )
    register_command(
        buy_name, buy_desc, handle_buy_msg, access_level="all",
        mandatory_params=[RegularParam("quantity"), RegularParam("item")]
    )

    # sell command
    sell_name = "sell"
    sell_desc = "Add a listing in the shop for one or more copies of an item that you own."
    register_command(
        sell_name, sell_desc, handle_sell_msg, access_level="all",
        mandatory_params=[RegularParam("quantity"), RegularParam("item"), RegularParam("price")]
    )

    # cancel sell command
    cancel_sell_name = "cancel_sell"
    cancel_sell_desc = (
        "Cancel a listing in the shop that you made for " +
        "the given number of items at the given price"
    )
    register_command(
        cancel_sell_name, cancel_sell_desc, handle_cancel_sell_msg, access_level="all",
        mandatory_params=[RegularParam("quantity"), RegularParam("item"), RegularParam("price")]
    )

    # inventory command
    inventory_name = "inventory"
    inventory_desc = "List all the items that your or someone else owns."
    register_command(
        inventory_name, inventory_desc, handle_inventory_msg, access_level="self",
        optional_params=[TargetParam("person")]
    )

    # random champ command
    random_champ_name = "random_champ"
    random_champ_desc = (
        "Pick a random champion. If a list is given, only champs from this list is used. " +
        "Champion lists can be created at https://mhooge.com/intfar/lists/"
    )
    register_command(
        random_champ_name, random_champ_desc, handle_random_champ_msg,
        optional_params=[RegularParam("list")]
    )

    # random unplayed commmand
    random_unplayed_name = "random_unplayed"
    random_unplayed_desc = (
        "Pick a random champion that you have not played before (from all champs, not a list)."
    )
    register_command(
        random_unplayed_name, random_unplayed_desc, handle_random_unplayed_msg
    )

    # champ lists command
    champ_lists_name = "champ_lists"
    champ_lists_desc = (
        "See a list of all champion lists, or those created by a specific person."
    )
    register_command(
        champ_lists_name, champ_lists_desc, handle_champ_lists_msg, True, "self",
        optional_params=[TargetParam("person", None)]
    )

    # champs command
    champs_name = "champs"
    champs_desc = "See what champs are in a given champion list."
    register_command(
        champs_name, champs_desc, handle_champs_msg,
        mandatory_params=[RegularParam("list")]
    )

    # create list command
    create_list_name = "create_list"
    create_list_desc = "Create a list of champions."
    register_command(
        create_list_name, create_list_desc, handle_create_list_msg, access_level="all",
        mandatory_params=[RegularParam("name")]
    )

    # add champ command
    add_champ_name = "add_champ"
    add_champ_desc = (
        "Add champion(s) to given list. Add more than one champ at once " +
        "with comma-separated list. Fx. `!add_champ some_list aatrox, ahri, akali`"
    )
    register_command(
        add_champ_name, add_champ_desc, handle_add_champs, access_level="all",
        mandatory_params=[RegularParam("list"), RegularParam("champion(s)")],
        parser=parse_champs_params
    )

    # delete list command
    delete_list_name = "delete_list"
    delete_list_desc = "Delete a champion list that you own."
    register_command(
        delete_list_name, delete_list_desc, handle_delete_list, access_level="all",
        mandatory_params=[RegularParam("list")]
    )

    # remove champ command
    remove_champ_name = "remove_champ"
    remove_champ_desc = (
        "Remove champion(s) from given list. Remove more than one champ at once " +
        "with comma-separated list. Fx. `!remove_champ some_list aatrox, ahri, akali`"
    )
    register_command(
        remove_champ_name, remove_champ_desc, handle_remove_champ, access_level="all",
        mandatory_params=[RegularParam("list"), RegularParam("champion(s)")],
        parser=parse_champs_params
    )

    # summary command
    summary_name = "summary"
    summary_desc = (
        "Show a summary of you or someone else's stats across all recorded games."
    )
    register_command(
        summary_name, summary_desc, handle_summary_msg, access_level="self",
        optional_params=[TargetParam("person")]
    )

    # performance command
    performance_name = "performance"
    performance_desc = (
        "Show you or someone else's Personally Evaluated Normalized Int Score."
    )
    register_command(
        performance_name, performance_desc, handle_performance_msg, True, "self",
        optional_params=[TargetParam("person")]
    )

    # wr command
    wr_name = "wr"
    wr_desc = "Show winrate info on a champion for you or someone else."
    register_command(
        wr_name, wr_desc, handle_winrate_msg, access_level="self",
        mandatory_params=[RegularParam("champion")], optional_params=[TargetParam("person")]
    )
 
    # ===== CUTE COMMANDS =====

    # intdaddy command
    intdaddy_name = "intdaddy"
    intdaddy_desc = "Flirt with the Int-Far."
    async def intdaddy_wrapper(client, message):
        await handle_flirtation_msg(client, message, "english")

    register_command(
        intdaddy_name, intdaddy_desc, intdaddy_wrapper,
        command_dict=commands_util.CUTE_COMMANDS
    )

    # intpapi command
    intpapi_name = "intpapi"
    intpapi_desc = "Flirt with the Int-Far (in spanish)."
    async def intpapi_wrapper(client, message):
        await handle_flirtation_msg(client, message, "spanish")

    register_command(
        intpapi_name, intpapi_desc, intpapi_wrapper,
        command_dict=commands_util.CUTE_COMMANDS
    )

    # ===== ADMIN COMMANDS =====

    # kick command
    register_command(
        "kick", None, handle_kick_msg,
        mandatory_params=[TargetParam("person")],
        command_dict=commands_util.ADMIN_COMMANDS
    )

initialize_commands()
