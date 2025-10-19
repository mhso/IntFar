from datetime import datetime

import api.util as api_util
from api.awards import get_intfar_reasons
from api.register import register_for_game
from discbot.commands.base import *

class RegisterCommand(Command):
    NAME = "register"
    DESCRIPTION = (
        "Sign up for the Int-Far™ Tracker™ for the given game " +
        "by providing your ingame info. For LoL, this is just your summoner name. "
        "For CS2, this is your Steam ID, latest match token, and match authentication code. "
        "(For CS2, signing up on the website is a lot easier)."
    )
    MANDATORY_PARAMS = [GameParam("game"), CommandParam("user_name")]
    OPTIONAL_PARAMS = [CommandParam("user_id"), CommandParam("extra_info_1"), CommandParam("extra_info_2")]

    async def handle(self, game: str, username: str, *extra_args):
        disc_id = self.message.author.id
        status_code, status_msg = await register_for_game(
            self.client.meta_database,
            self.client.game_databases[game],
            self.client.api_clients[game],
            disc_id,
            username,
            *extra_args
        )

        if status_code > 0:
            users_in_voice = self.client.get_users_in_voice()
            for guild_id in users_in_voice:
                for disc_id in users_in_voice[guild_id][game]:
                    if self.message.author.id == disc_id: # User is already in voice channel.
                        await self.client.user_joined_voice(disc_id, guild_id)
                        break

        await self.message.channel.send(self.client.insert_emotes(status_msg))

class UnregisterCommand(Command):
    NAME = "unregister"
    DESCRIPTION = (
        "Leave the Int-Far™ Tracker™ for the given game. You can re-join later "
        "with !register and your data will not be deleted."
    )
    ACCESS_LEVEL = "all"
    MANDATORY_PARAMS = [GameParam("game")]

    async def handle(self, game: str):
        user_in_game = False
        for guild_id in api_util.GUILD_IDS:
            users_in_game = self.client.get_users_in_game(game, guild_id) or []
            for disc_id in users_in_game:
                # If user is in game, unregistration is not allowed.
                if disc_id == self.message.author.id:
                    user_in_game = True
                    break

        if user_in_game:
            response = (
                "You can't unregister in the middle of a game " +
                "(that would be cheating {emote_im_nat_kda_player_yo})"
            )
        else:
            self.client.game_databases[game].remove_user(self.message.author.id)
            game_name = api_util.SUPPORTED_GAMES[game]
            response = (
                f"You are no longer registered to the Int-Far™ Tracker™ for {game_name} " + "{emote_sadge} " +
                "Your games are no longer being tracked and your stats will not be shown. " +
                "However, your data has not been deleted and you can register again at any time."
            )

        await self.message.channel.send(self.client.insert_emotes(response))

class UsersCommand(Command):
    NAME = "users"
    DESCRIPTION = "List all users who are currently signed up for the Int-Far:tm: Tracker:tm:."
    OPTIONAL_PARAMS = [GameParam("game", default=None)]

    async def handle(self, game: str = None): 
        response = ""
        games = api_util.SUPPORTED_GAMES if game is None else [game]
        for game in games:
            database = self.client.game_databases[game]
            game_response = ""
            game_name = api_util.SUPPORTED_GAMES[game]
            for disc_id in database.game_users.keys():
                formatted_names = ", ".join(database.game_users[disc_id].player_name)
                nickname = self.client.get_discord_nick(disc_id, self.message.guild.id)
                game_response += f"\n- {nickname} ({formatted_names})"

            if game_response == "":
                if response != "":
                    response += "\n\n"

                response += (
                    f"**No lads are currently signed up for {game_name} "
                    "{emote_nat_really_fine} but you can change this!!**"
                )
            else:
                response += f"\n\n**--- Registered bois for {game_name} ---**" + game_response

        await self.message.channel.send(self.client.insert_emotes(response))

class HelpCommand(Command):
    NAME = "help"
    DESCRIPTION = "Show the helper text." 

    async def handle(self):
        """
        Write the helper message to Discord.
        """
        game_names = list(api_util.SUPPORTED_GAMES.values())
        before_and = ", ".join(game_names[:-1])
        after_and = game_names[-1]
        games_desc = f"{before_and} and {after_and}"

        response = "I gotchu fam {emote_nazi}\n"
        response += "The Int-Far™ Tracker™ is a highly sophisticated bot "
        response += f"that watches when people in this server plays {games_desc}, "
        response += "and judges them harshly if they suck too hard {emote_simp_but_closeup}\n"
        response += "- Write `!commands` to see a list of available commands, and their usages\n"
        response += "- Write `!stats` to see a list of available stats to check\n"
        response += "- Write `!betting` to see a list of events to bet on and how to do so"

        await self.message.channel.send(self.client.insert_emotes(response))

class CommandsCommand(Command):
    NAME = "commands"
    DESCRIPTION = "Show a list of commands to use with Int-Far."

    async def handle(self):
        header = "**--- Valid commands, and their usages: ---**"
        lines = []
        for cmd in commands_util.COMMANDS:
            cmd_obj = commands_util.COMMANDS[cmd](self.client, self.message)
            if self.message.guild.id in cmd_obj.GUILDS:
                cmd_str = f"`{cmd_obj}` - {cmd_obj.DESCRIPTION}"
                lines.append(cmd_str)

        await self.client.paginate(self.message.channel, lines, 0, 7, header)

class UsageCommand(Command):
    NAME = "usage"
    DESCRIPTION = "Show how to use a given command."
    MANDATORY_PARAMS = [CommandParam("command")]

    async def handle(self, command: str):
        valid_cmd, show_usage = is_command_valid(self.message, command, None)
        if not valid_cmd and not show_usage:
            await self.message.channel.send(f"Not a valid command: '{command}'.")
            return

        # Get main command (if it is an alias)
        cmd_obj: Command = commands_util.get_main_command(command)(self.client, self.message, self.called_name)
        response = f"Usage: `{cmd_obj}`\n"
        response += cmd_obj.DESCRIPTION

        if cmd_obj.ACCESS_LEVEL is not None:
            response += "\n\n*Note: This command requires you to be registered to Int-Far"

            if cmd_obj.ACCESS_LEVEL == "self":
                response += ", if targetted at yourself."
            elif cmd_obj.ACCESS_LEVEL == "all":
                response += "."
            response += "*"

        await self.message.channel.send(response)

def get_uptime(dt_init):
    dt_now = datetime.now()
    return api_util.format_duration(dt_init, dt_now)

class UptimeCommand(Command):
    NAME = "uptime"
    DESCRIPTION = "Show for how long the bot has been up and running."

    async def handle(self):
        uptime_formatted = get_uptime(self.client.time_initialized)
        await self.message.channel.send(f"Int-Far™ Tracker™ has been online for {uptime_formatted}")

class StatusCommand(Command):
    NAME = "status"
    DESCRIPTION = "Show overall stats about Int-Far for a game."
    OPTIONAL_PARAMS = [GameParam("game")]

    async def handle(self, game: str):
        """
        Gather meta stats about Int-Far and write them to Discord.
        """
        response = f"**Uptime:** {get_uptime(self.client.time_initialized)}\n"

        (
            games, earliest_game, latest_game, games_won,
            unique_game_guilds, longest_game_duration,
            longest_game_time, users, doinks_games,
            total_doinks, intfars, games_ratios,
            intfar_ratios, intfar_multi_ratios
        ) = self.client.game_databases[game].get_meta_stats()

        pct_games_won = (games_won / games) * 100

        longest_game_start = datetime.fromtimestamp(longest_game_time)
        longest_game_end = datetime.fromtimestamp(longest_game_time + longest_game_duration)
        longest_game_fmt = api_util.format_duration(longest_game_start, longest_game_end)
        longest_game_date = datetime.fromtimestamp(longest_game_time).strftime("%Y-%m-%d")

        sounds = self.client.audio_handler.get_sounds("alphabetical")
        unique_owners = set(sound_data[1] for sound_data in sounds)

        pct_intfar = int((intfars / games) * 100)
        pct_doinks = int((doinks_games / games) * 100)
        earliest_time = datetime.fromtimestamp(earliest_game).strftime("%Y-%m-%d")
        latest_time = datetime.fromtimestamp(latest_game).strftime("%Y-%m-%d")
        doinks_emote = self.client.insert_emotes("{emote_Doinks}")
        all_bets = self.client.game_databases[game].get_bets(False)

        tokens_name = self.client.config.betting_tokens
        bets_won = 0
        total_bets = 0
        total_amount = 0
        total_payout = 0
        highest_payout = 0
        highest_payout_user = None
        unique_guilds = set()

        for disc_id in all_bets:
            bet_data = all_bets[disc_id]
            total_bets += len(bet_data)
            for _, guild_id, _, amounts, _, _, _, result, payout in bet_data:
                for amount in amounts:
                    total_amount += amount

                unique_guilds.add(guild_id)

                if payout is not None:
                    if payout > highest_payout:
                        highest_payout = payout
                        highest_payout_user = disc_id

                    total_payout += payout

                if result == 1:
                    bets_won += 1

        pct_bets_won = int((bets_won / total_bets) * 100) if total_bets > 0 else 0
        highest_payout_name = self.client.get_discord_nick(highest_payout_user, self.message.guild.id)

        intfar_reasons = get_intfar_reasons(game).values()

        reason_ratio_msg = "\n".join(f"- **{count:.1f}%** were for {reason}" for count, reason in zip(intfar_ratios, intfar_reasons))
        count_literals = ["one", "two", "three", "four", "five", "six", "seven", "eight"]
        def multi_criterias_msg(index, max_count):
            if index == 1:
                quantifier = f"met just {count_literals[index-1]} criteria"
            elif index == max_count:
                quantifier = f"swept and met all {count_literals[index-1]} criterias"
            else:
                quantifier = f"met {count_literals[index-1]} criterias"

            return f"- **{intfar_multi_ratios[index-1]:.1f}%** of Int-Fars {quantifier}"

        reason_multi_ratio_msg = "\n".join(multi_criterias_msg(index, len(intfar_multi_ratios)) for index in range(1, len(intfar_multi_ratios)+1))

        highest_payout_msg = (
            "" if highest_payout_user is None
            else f"- **{api_util.format_tokens_amount(highest_payout)}** {tokens_name} was the biggest single win, by **{highest_payout_name}**\n"
        )

        response += (
            f"--- From **{earliest_time}** to **{latest_time}** ---\n"
            f"- **{games}** games of **{api_util.SUPPORTED_GAMES[game]}** have been played in {unique_game_guilds} servers (**{pct_games_won:.1f}%** was won)\n"
            f"- Longest game lasted **{longest_game_fmt}**, played on {longest_game_date}\n"
            f"- **{users}** users have signed up for this game\n"
            f"- **{intfars}** Int-Far awards have been given\n"
            f"- **{total_doinks}** {doinks_emote} have been earned\n"
            f"- **{len(sounds)}** sounds have been uploaded by **{len(unique_owners)}** people\n"
            f"- **{total_bets}** bets have been made (**{pct_bets_won}%** was won)\n"
            f"- Bets were made in **{len(unique_guilds)}** different servers\n"
            f"- **{api_util.format_tokens_amount(total_amount)}** {tokens_name} have been spent on bets\n"
            f"- **{api_util.format_tokens_amount(total_payout)}** {tokens_name} have been won from bets\n"
            f"{highest_payout_msg}"
            "--- Of all games played ---\n"
            f"- **{pct_intfar}%** resulted in someone being Int-Far\n"
            f"- **{pct_doinks}%** resulted in {doinks_emote} being handed out\n"
            f"- **{games_ratios[0]}%** were as a duo\n"
            f"- **{games_ratios[1]}%** were as a three-man\n"
            f"- **{games_ratios[2]}%** were as a four-man\n"
            f"- **{games_ratios[3]}%** were as a five-man stack\n"
            "--- When Int-Fars were earned ---\n"
            f"{reason_ratio_msg}\n"
            f"{reason_multi_ratio_msg}"
        )

        await self.message.channel.send(response)

class WebsiteCommand(Command):
    NAME = "website"
    DESCRIPTION = "See information about the Int-Far website."

    async def handle(self):
        response = (
            "Check out the amazing Int-Far website {emote_smol_gual}\n" +
            f"{api_util.get_website_link()}\n" +
            "Write `!website_verify` to sign in to the website, " +
            "allowing you to create bets, see stats, upload sounds, and more! "
            "You can also more easily sign up for CS2 here!"
        )

        await self.message.channel.send(self.client.insert_emotes(response))

class ProfileCommand(Command):
    NAME = "website_profile"
    DESCRIPTION = (
        "Get a link to your (or someone else's) Int-Far profile "
        "for the given game."
    )
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = [GameParam("game"), TargetParam("person")]

    async def handle(self, game: str, target_id: int = None):
        target_name = self.client.get_discord_nick(target_id, self.message.guild.id)

        response = f"URL to {target_name}'s personal Int-Far profile for {api_util.SUPPORTED_GAMES[game]}:\n"
        response += f"{api_util.get_website_link(game)}/user/{target_id}"

        await self.message.channel.send(response)

class VerifyCommand(Command):
    NAME = "website_verify"
    DESCRIPTION = (
        "Get a secret link that when opened will " +
        "verify and log you in on the Int-Far website."
    )
    ACCESS_LEVEL = "self"

    async def handle(self):
        """
        Handler for 'website_verify' command. Generates a unique URL that when accessed
        verifies a user and allows them to interact with the Int-Far website. This URL is
        then sent via. a Discord DM to the invoker of the command.
        """
        client_secret = self.client.meta_database.get_client_secret(self.message.author.id)
        url = f"{api_util.get_website_link()}/verify/{client_secret}"
        response_dm = "Go to this link to verify yourself (totally not a virus):\n"
        response_dm += url + "\n"
        response_dm += "This will enable you to interact with the Int-Far bot from "
        response_dm += "the website, fx. to see stats or place bets.\n"
        response_dm += "To log in to a new device (phone fx.), simply use the above link again.\n"
        response_dm += "Don't show this link to anyone, or they will be able to log in as you!"

        mention = self.client.get_mention_str(self.message.author.id, self.message.guild.id)
        response_server = (
            f"Psst, {mention}, I sent you a DM with a secret link, "
            "where you can sign up for the website {emote_peberno}"
        )

        await self.message.channel.send(self.client.insert_emotes(response_server))

        # Send DM to the user
        dm_sent = await self.client.send_dm(response_dm, self.message.author.id)
        if not dm_sent:
            await self.message.channel.send(
                "Error: DM Message could not be sent for some reason ;( Try again!"
            )

class DefaultGameCommand(Command):
    NAME = "default_game"
    DESCRIPTION = "Set your prefered default game for use with commands."
    ACCESS_LEVEL = "all"
    OPTIONAL_PARAMS = [GameParam("game", default=None)]

    async def handle(self, game=None):
        if game is None:
            game = self.client.meta_database.all_users[self.message.author.id].default_game
            game_name = api_util.SUPPORTED_GAMES[game]
            response = f"Your default game is *{game_name}*"

        else:
            self.client.meta_database.set_default_game(self.message.author.id, game)
            game_name = api_util.SUPPORTED_GAMES[game]
            response = f"Your default game is now set to *{game_name}*"

        await self.message.channel.send(response)
