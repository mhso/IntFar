import asyncio
from io import BytesIO
from threading import Thread
from time import time
from math import ceil
from datetime import datetime

import discord
from discord.errors import NotFound, DiscordException, HTTPException, Forbidden

from mhooge_flask.logging import logger
from mhooge_flask.database import DBException
from streamscape import Streamscape

from discbot.montly_intfar import MonthlyIntfar
from discbot.app_listener import listen_for_request
from discbot import commands
from discbot.commands.meta import handle_usage_msg
from discbot.commands.split import handle_end_of_split_msg
from api.award_qualifiers import AwardQualifiers
from api.awards import get_awards_handler
from api.game_api_client import GameAPIClient
from api.game_data import get_empty_game_data
from api.game_data.lol import parse_player_rank
from api.game_stats import GameStats, PostGameStats
from api.game_monitor import GameMonitor
from api.game_monitors import get_game_monitor
from api.game_monitors.lol import LoLGameMonitor
from api.game_monitors.cs2 import CS2GameMonitor
from api.meta_database import MetaDatabase
from api.game_database import GameDatabase
from api.betting import BettingHandler
from api.audio_handler import AudioHandler
from api.shop import ShopHandler
from api.config import Config
import discbot.commands.util as commands_util
import api.util as api_util
#from ai.data import shape_predict_data

MAIN_CHANNEL_ID = 730744358751567902

CHANNEL_IDS = [ # List of channels that Int-Far will write to.
    MAIN_CHANNEL_ID,
    805218121610166272,
    808796236692848650
]

class DiscordClient(discord.Client):
    """
    Class that contains the logic for interacting with the dicscord.py API.
    This includes reacting to messages, sending messages, getting data about users,
    initializing game status polling, playing sounds, etc.
    """
    def __init__(
        self,
        config: Config,
        meta_database: MetaDatabase,
        game_databases: dict[str, GameDatabase],
        betting_handlers: dict[str, BettingHandler],
        api_clients: dict[str, GameAPIClient],
        **kwargs
    ):
        """
        Initialize the Discord client.

        :param config:              Config instance that holds all the configuration
                                    options for Int-Far
        :param meta_database:       SQLiteMetaDatabase instance that handles the logic
                                    of interacting with the sqlite database
        :param game_databases:      Game databases 
        :param betting_handlers:    BettingHandler instance that handles the logic
                                    of creating, resolving, and listing bets
        :param audio_handler:       AudioHandler instance that handles the logic of
                                    listing and playing sounds through Discord
        :param shop_handler:        ShopHandler instance that handles the logic of
                                    buying, selling, listing items for betting tokens
        :param **kwargs:            Various keyword arguments.
        """
        super().__init__(
            intents=discord.Intents(
                members=True,
                voice_states=True,
                guilds=True,
                emojis=True,
                reactions=True,
                guild_messages=True,
                message_content=True,
            )
        )
        self.config = config
        self.meta_database = meta_database
        self.game_databases = game_databases
        self.betting_handlers = betting_handlers
        self.api_clients = api_clients

        if self.config.env == "production":
           streamscape = Streamscape(chrome_executable="/usr/bin/google-chrome")
        else:
           streamscape = None

        self.audio_handler = AudioHandler(self.config, self.meta_database, streamscape)
        self.shop_handler = ShopHandler(self.config, self.meta_database)

        self.ai_conn = kwargs.get("ai_pipe")
        self.main_conn = kwargs.get("main_pipe")
        self.flask_conn = kwargs.get("flask_pipe")

        self.game_monitors = {
            game: get_game_monitor(
                game,
                self.config,
                self.meta_database,
                self.game_databases[game],
                self.api_clients[game],
                self.on_game_over
            )
            for game in api_util.SUPPORTED_GAMES
        }

        self.pagination_data = {}
        self.audio_action_data = {}
        self.cached_avatars = {}
        self.channels_to_write = {}
        self.test_guild = None
        self.initialized = False
        self.event_listeners = {}
        self.last_message_time = {}
        self.last_command_time = {}
        self.command_timeout_lengths = {}
        self.user_timeout_length = {}
        self.time_initialized = datetime.now()

    async def send_predictions_timeline_image(self, image, guild_id):
        channel = self.channels_to_write[guild_id]
        with BytesIO() as b_io:
            image.save(b_io, format="PNG")
            b_io.seek(0)
            file = discord.File(b_io, filename="predictions.png")
            await channel.send("Odds of winning throughout the game:", file=file)

    async def on_game_over(self, post_game_stats: PostGameStats):
        """
        Method called by a game monitor when a game is concluded and awards & stats
        should be saved.
        """
        if post_game_stats.status_code == GameMonitor.POSTGAME_STATUS_ERROR:
            # Something went terribly wrong when handling the end of game logic
            # Send error message to Discord to indicate things went bad.
            await self.send_error_msg(post_game_stats.guild_id)

        elif post_game_stats.status_code == GameMonitor.POSTGAME_STATUS_MISSING:
            # Send message pinging me about the error.
            mention_me = self.get_mention_str(commands_util.ADMIN_DISC_ID, post_game_stats.guild_id)
            game_name = api_util.SUPPORTED_GAMES[post_game_stats.game]
            message_str = (
                f"The API for {game_name} is being a dickfish, not much I can do :shrug:\n"
                f"{mention_me} will add the game manually later."
            )

            await self.send_message_unprompted(message_str, post_game_stats.guild_id)

        elif post_game_stats.status_code == GameMonitor.POSTGAME_STATUS_SOLO:
            response = "Only one person in that game. "
            response += "no Int-Far will be crowned "
            response += "and no stats will be saved."
            await self.channels_to_write[post_game_stats.guild_id].send(response)

        else:
            game_monitor = self.game_monitors[post_game_stats.game]
            func = getattr(self, f"on_{post_game_stats.game}_game_over")
            await func(post_game_stats, game_monitor)

    async def on_lol_game_over(self, post_game_stats: PostGameStats, game_monitor: LoLGameMonitor):
        """
        Method called when a League of Legends game is finished.

        :param game_info:   Dictionary containing un-filtered data about a finished
                            game fetched from Riot League API
        :param guild_id:    ID of the Discord server where the game took place
        :param status_code: Integer that describes the status of the finished game
        """
        if post_game_stats.status_code == game_monitor.POSTGAME_STATUS_URF:
            # Gamemode was URF. Don't save stats then.
            response = "That was an URF game {emote_poggers} "
            response += "no Int-Far will be crowned "
            response += "and no stats will be saved."
            await self.channels_to_write[post_game_stats.guild_id].send(self.insert_emotes(response))

        elif post_game_stats.status_code == game_monitor.POSTGAME_STATUS_INVALID_MAP:
            # Game is not on summoners rift. Same deal.
            response = "That game was not on SR, Nexus Blitz, or Arena "
            response += "{emote_woahpikachu} no Int-Far will be crowned "
            response += "and no stats will be saved."
            await self.channels_to_write[post_game_stats.guild_id].send(self.insert_emotes(response))

        elif post_game_stats.status_code == game_monitor.POSTGAME_STATUS_REMAKE:
            # Game was too short, most likely a remake.
            response = (
                f"That game lasted less than {game_monitor.min_game_minutes} minutes "
                "{emote_zinking} assuming it was a remake. "
                "No stats are saved."
            )
            await self.channels_to_write[post_game_stats.guild_id].send(self.insert_emotes(response))

        elif post_game_stats.status_code == game_monitor.POSTGAME_STATUS_OK:
            game_monitor = self.game_monitors[post_game_stats.game]
            if self.api_clients[post_game_stats.game].is_clash(game_monitor.active_game[post_game_stats.guild_id]["queue_id"]):
                # Game was played as part of a clash tournament, so it awards more betting tokens.
                multiplier = self.config.clash_multiplier
                await self.channels_to_write[post_game_stats.guild_id].send(
                    "**>>> THAT WAS A CLASH GAME! REWARDS ARE WORTH " +
                    f"{multiplier}x AS MUCH!!! <<<**"
                )

            await self.handle_game_over(post_game_stats)

    async def on_cs2_game_over(self, post_game_stats: PostGameStats, game_monitor: CS2GameMonitor):
        """
        Method called when a CS2 game is finished.

        :param data:        Dictionary containing un-filtered data about a finished
                            game fetched from CS2 and parsed with awpy
        :param guild_id:    ID of the Discord server where the game took place
        :param status_code: Integer that describes the status of the finished game
        """        
        if post_game_stats.status_code == game_monitor.POSTGAME_STATUS_SHORT_MATCH:
            # Game was too short, most likely an early surrender
            response = (
                "That game was a short match or was surrendered early, no stats are saved {emote_suk_a_hotdok}"
            )
            await self.channels_to_write[post_game_stats.guild_id].send(self.insert_emotes(response))

        elif post_game_stats.status_code == game_monitor.POSTGAME_STATUS_SURRENDER:
            # Game was too short, most likely an early surrender
            response = (
                f"That game lasted less than {game_monitor.min_game_minutes} minutes "
                "{emote_zinking} assuming it was an early surrender. "
                "No stats are saved."
            )
            await self.channels_to_write[post_game_stats.guild_id].send(self.insert_emotes(response))

        elif post_game_stats.status_code in (
            game_monitor.POSTGAME_STATUS_OK,
            game_monitor.POSTGAME_STATUS_DEMO_MISSING,
            game_monitor.POSTGAME_STATUS_DEMO_UNSUPORTED
        ):
            demo_response = None
            if post_game_stats.status_code == game_monitor.POSTGAME_STATUS_DEMO_MISSING:
                demo_response = (
                    "Demo file was not found on Valve's servers! Nothing we can do :( "
                    "Only basic data like kills, deaths, assists, etc. will be saved."
                )
            elif post_game_stats.status_code == game_monitor.POSTGAME_STATUS_DEMO_UNSUPORTED:
                demo_response = (
                    "Valve does not support demos for CS2 yet, nothing we can do :( "
                    "Only basic data like kills, deaths, assists, etc. will be saved."
                )

            if demo_response is not None:
                await self.channels_to_write[post_game_stats.guild_id].send(demo_response)

            await self.handle_game_over(post_game_stats)

    async def handle_game_over(self, post_game_stats: PostGameStats):
        """
        Called when a game is over and is valid. Handles all the post-game mentions
        about the intfar, doinks, bets, etc.

        :param post_game_data:  PostGameStats instance with the parsed data.
        """
        awards_handler = get_awards_handler(
            post_game_stats.game,
            self.config,
            self.api_clients[post_game_stats.game],
            post_game_stats.parsed_game_stats
        )
 
        response = self.insert_emotes(
            f"Good day for a **{api_util.SUPPORTED_GAMES[post_game_stats.game]}** game " + "{emote_happy_nono}"
        )

        # Get message about Int-Far or honorable mentions
        intfar_id, intfar_data, ties, ties_msg = post_game_stats.intfar_data
        intfar_streak, prev_intfar = post_game_stats.intfar_streak_data

        if post_game_stats.intfar_data[0] is not None:
            if ties:
                logger.info("There are Int-Far ties.")
                logger.info(ties_msg)

            intfar_response = self.get_intfar_message(
                awards_handler,
                intfar_id,
                intfar_data,
                ties,
                ties_msg,
                intfar_streak,
                prev_intfar
            )
        else:
            logger.info("No Int-Far that game.")
            intfar_response = self.get_honorable_mentions_msg(awards_handler, intfar_streak, prev_intfar)

        response += "\n" + intfar_response

        # Get message about big doinks awarded
        doinks_mentions, doinks = post_game_stats.doinks_data
        doinks_response = self.get_big_doinks_msg(awards_handler, doinks_mentions)
        if doinks_response is not None:
            response += "\n" + self.insert_emotes(doinks_response)

        # Get message about rank promotion/demotion
        rank_mentions = post_game_stats.ranks_data
        ranks_reponse = self.get_rank_mentions_msg(awards_handler, rank_mentions)
        if ranks_reponse is not None:
            response += "\n" + self.insert_emotes(ranks_reponse)

        # Get message about about win or loss streaks
        active_streaks, broken_streaks = post_game_stats.winstreak_data
        game_streak_response = self.get_win_loss_streak_message(awards_handler, active_streaks, broken_streaks)
        if game_streak_response is not None:
            response += "\n" + game_streak_response

        await self.channels_to_write[post_game_stats.guild_id].send(response)

        await asyncio.sleep(1)

        # Resolve any active bets made on the game.
        response, max_tokens_id, new_max_tokens_id = self.resolve_bets(post_game_stats.parsed_game_stats)

        if max_tokens_id != new_max_tokens_id: # Assign new 'goodest_boi' title.
            await self.assign_top_tokens_role(max_tokens_id, new_max_tokens_id)

        # Get message about timeline data events for the game
        timeline_mentions = post_game_stats.timeline_data
        timeline_response = self.get_timeline_msg(awards_handler, timeline_mentions)
        if timeline_response is not None:
            response = timeline_response + "\n" + response

        # Get message for other cool stats about players
        cool_stats_mentions = post_game_stats.cool_stats_data
        cool_stats_response = self.get_cool_stats_msg(awards_handler, cool_stats_mentions)
        if cool_stats_response is not None:
            response = cool_stats_response + "\n" + response

        # Get message for beaten records
        best_records, worst_records = post_game_stats.beaten_records_data
        if best_records != [] or worst_records != []:
            records_response = self.get_beaten_records_msg(
                post_game_stats.parsed_game_stats, best_records, worst_records
            )
            response = records_response + "\n" + response

        # Get message about lifetime achievements
        lifetime_mentions = post_game_stats.lifetime_data
        lifetime_stats = self.get_lifetime_stats_msg(awards_handler, lifetime_mentions)
        if lifetime_stats is not None:
            response = lifetime_stats + "\n" + response

        await self.channels_to_write[post_game_stats.guild_id].send(response)

        await self.play_event_sounds(post_game_stats.game, intfar_id, doinks, post_game_stats.guild_id)

    def get_game_start(self, game, guild_id):
        return self.game_monitors[game].active_game.get(guild_id, {}).get("start", None)

    def get_active_game(self, game, guild_id):
        return self.game_monitors[game].active_game.get(guild_id)

    def get_users_in_game(self, game, guild_id):
        return self.game_monitors[game].users_in_game.get(guild_id)

    def get_mention_str(self, disc_id, guild_id=api_util.MAIN_GUILD_ID):
        """
        Return a string that allows for @mention of the given user.
        """
        # Try and find the person in the specified guild.
        for guild in self.guilds:
            if guild.id == guild_id:
                for member in guild.members:
                    if member.id == disc_id:
                        return member.mention

        # If person is not found, find nickname from any guild instead.
        return self.get_discord_nick(disc_id, guild_id)

    def get_member_safe(self, disc_id, guild_id=api_util.MAIN_GUILD_ID):
        """
        Try to find a member in the guild with the given guild ID.
        If person is not found, search through all registered guilds instead.
        """
        if isinstance(disc_id, str):
            disc_id = int(disc_id)

        all_guilds = [g_id for g_id in api_util.GUILD_IDS if g_id != guild_id]

        for guild_to_search in [guild_id] + all_guilds:
            server = self.get_guild(guild_to_search)
            if server is None:
                return None

            for member in server.members:
                if member.id == disc_id:
                    return member

        return None

    def get_discord_nick(self, discord_id=None, guild_id=api_util.MAIN_GUILD_ID):
        """
        Return Discord nickname matching the given Discord ID.
        If 'discord_id' is None, returns all nicknames.
        """
        if discord_id is not None:
            member = self.get_member_safe(discord_id, guild_id)
            return None if member is None else member.display_name

        nicknames = {}
        for disc_id in self.meta_database.all_users.keys():
            member = self.get_member_safe(disc_id, guild_id)
            name = "Unnamed" if member is None else member.display_name
            nicknames[disc_id] = name

        return nicknames

    async def get_discord_avatar(self, discord_id=None, size=64):
        default_avatar = "app/static/img/questionmark.png"
        users_to_search = (
            [disc_id for disc_id in self.meta_database.all_users.keys()]
            if discord_id is None
            else [discord_id]
        )

        avatar_paths = {}
        for disc_id in users_to_search:
            member = self.get_member_safe(disc_id)
            if member is None:
                avatar_paths[disc_id] = default_avatar
                continue

            key = f"{member.id}_{size}"

            caching_time = self.cached_avatars.get(key, 0)
            time_now = time()
            # We cache avatars for an hour.
            path = f"app/static/img/avatars/{member.id}_{size}.png"
            if time_now - caching_time > 3600:
                try:
                    await member.display_avatar.with_format("png").with_size(size).save(path)
                    self.cached_avatars[key] = time_now
                except (DiscordException, HTTPException, NotFound):
                    logger.bind(disc_id=discord_id).exception("Could not load Discord avatar")
                    path = default_avatar

            avatar_paths[disc_id] = path

        return avatar_paths if discord_id is None else avatar_paths[discord_id]

    def get_discord_id(self, nickname, guild_id=api_util.MAIN_GUILD_ID, exact_match=True):
        matches = []
        guild = self.get_guild(guild_id)
        for member in guild.members:
            for attribute in (member.global_name, member.nick, member.display_name, member.name):
                if attribute is not None:
                    if exact_match and attribute.lower() == nickname:
                        return member.id
                    elif not exact_match and nickname in attribute.lower():
                        matches.append(member.id)
                        break

        return matches[0] if len(matches) == 1 else None

    def get_guilds_for_user(self, disc_id):
        guild_ids = []
        for guild_id in api_util.GUILD_IDS:
            guild = self.get_guild(guild_id)
            if guild is None:
                continue

            for member in guild.members:
                if member.id == disc_id:
                    guild_ids.append(guild_id)

        return guild_ids

    def get_guild_name(self, guild_id=None):
        guilds = sorted(
            self.guilds,
            key=lambda g: api_util.GUILD_IDS.index(g.id) if g.id in api_util.GUILD_IDS else -1
        )

        guild_names = {}
        for guild in guilds:
            if (guild.id in api_util.GUILD_IDS and
                    ((guild_id is None) or (guild.id == guild_id))
               ):
                guild_names[guild.id] = guild.name

        if guild_names == {}:
            logger.warning(f"get_guild_name: Could not find name of guild with ID '{guild_id}'")
            return None

        return guild_names if guild_id is None else guild_names[guild_id]

    def get_channel_name(self, guild_id=None):
        channel_names = []
        for g_id in api_util.GUILD_IDS:
            guild = self.get_guild(g_id)
            for c_id in CHANNEL_IDS:
                channel = guild.get_channel(c_id)
                if channel is not None:
                    if guild_id is not None and g_id == int(guild_id):
                        return channel.name
                    channel_names.append(channel.name)

        return channel_names

    def get_all_emojis(self):
        for guild in self.guilds:
            if guild.id == api_util.MAIN_GUILD_ID:
                return [(emoji.name, emoji.url) for emoji in guild.emojis]

        return None

    def get_emoji_by_name(self, emoji_name):
        """
        Return the ID of the emoji matching the given name.
        """
        for guild in self.guilds:
            if guild.id == api_util.MAIN_GUILD_ID:
                for emoji in guild.emojis:
                    if emoji.name == emoji_name:
                        return str(emoji)

        return None

    def get_users_in_voice(self):
        users_in_voice = {
            guild_id: {game: {} for game in api_util.SUPPORTED_GAMES}
            for guild_id in api_util.GUILD_IDS
        }

        for guild in self.guilds:
            if guild.id not in api_util.GUILD_IDS:
                continue

            for channel in guild.voice_channels:
                members_in_voice = channel.members
                for member in members_in_voice:
                    for game in api_util.SUPPORTED_GAMES:
                        member_id = int(member.id)
                        user_info = self.game_databases[game].game_user_data_from_discord_id(member_id)
                        if user_info is not None:
                            users_in_voice[guild.id][game][member_id] = user_info

        return users_in_voice

    def get_ai_prediction(self, guild_id):
        if self.ai_conn is not None and guild_id in self.game_monitor.users_in_game:
            # input_data = shape_predict_data(
            #     self.database, self.riot_api, self.config, self.game_monitor.users_in_game[guild_id]
            # )
            input_data = None
            self.ai_conn.send(("predict", [input_data]))
            ratio_win = self.ai_conn.recv()
            return int(ratio_win * 100)

        return None

    def add_event_listener(self, event, callback, *args):
        listeners = self.event_listeners.get(event, [])
        listeners.append((callback, args))
        self.event_listeners[event] = listeners

    def try_get_user_data(self, name, guild_id):
        if name.startswith("<@"): # Mention string
            start_index = 3 if name[2] == "!" else 2
            return int(name[start_index:-1])

        disc_id_candidates = set()
        for game in api_util.SUPPORTED_GAMES:
            discord_id = self.game_databases[game].discord_id_from_ingame_info(exact_match=False, player_name=name)
            if discord_id is not None:
                disc_id_candidates.add(discord_id)

        if len(disc_id_candidates) != 1: # Summoner name gave no unanimous result, try Discord name.
            return self.get_discord_id(name, guild_id, exact_match=False)

        return disc_id_candidates.pop()

    def insert_emotes(self, text):
        """
        Finds all occurrences of '{emote_some_emote}' in the given string and replaces it with
        the id of the actual emote matching 'some_emote'.
        """
        replaced = text
        emote_index = replaced.find("{emote_")

        while emote_index > -1:
            emote = ""
            end_index = emote_index + 7

            while replaced[end_index] != "}":
                emote += replaced[end_index]
                end_index += 1

                if end_index == len(replaced):
                    # The closing brace for the emote could not be found
                    raise ValueError(
                        f"Could not find closing brace for emote in text: '{text}'"
                    )

            emoji = self.get_emoji_by_name(emote)
            if emoji is None:
                emoji = "" # Replace with empty string if emoji could not be found.

            replaced = replaced.replace("{emote_" + emote + "}", emoji)
            emote_index = replaced.find("{emote_")

        return replaced

    async def assign_top_tokens_role(self, old_holder, new_holder):
        """
        Asssign the 'goodest boi' role on Discord to a new person who now
        has the most betting tokens of everyone.
        """
        role_id = 750111830529146980
        nibs_guild = None

        # Find the relevant Discord server where roles are assigned
        for guild in self.guilds:
            if guild.id == api_util.MAIN_GUILD_ID:
                nibs_guild = guild
                break

        # Get the 'goodest-boi' role
        role = nibs_guild.get_role(role_id)

        # Find the member who previously had the role and remove it from them
        old_head_honcho = nibs_guild.get_member(old_holder)
        if old_head_honcho is not None:
            await old_head_honcho.remove_roles(role)

        # Find the member who should now have the role and add it to them
        new_head_honcho = nibs_guild.get_member(new_holder)
        if new_head_honcho is not None:
            await new_head_honcho.add_roles(role)

    def resolve_bets(self, game_stats: GameStats):
        """
        Resolves any active bets after a game has concluded and award points
        to the players in the game and to players getting doinks.
        The BettingHandler class is used to determine if bets are won or lost,
        and how many points they should award.

        :param game_info:       List containing a tuple of (discord_id, game_stats)
                                for each Int-Far registered player on our team
        :param intfar:          Discord ID of the Int-Far in the finished game.
                                This is None if no one was Int-Far
        :param intfar_reason:   String that encodes the reasons why a person was the
                                Int-Far in the finished game. This is None if no one
                                was Int-Far
        :param doinks:          List of Discord IDs of people who got doinks
        :param guild_id:        ID of the Discord server where the game took place
        """
        guild_id = game_stats.guild_id
        tokens_name = self.config.betting_tokens
        game_database = self.game_databases[game_stats.game]
        duration_fmt = api_util.format_duration_seconds(game_stats.duration)

        if game_stats.win == 1:
            game_desc = f"**Game won** after {duration_fmt}!"
            tokens_gained = self.config.betting_tokens_for_win
        elif game_stats.win == -1:
            game_desc = f"**Game lost** after {duration_fmt}."
            tokens_gained = self.config.betting_tokens_for_loss
        else:
            game_desc = f"**Game tied** after {duration_fmt}."
            tokens_gained = 0

        bet_multiplier = 1

        # Check if we are playing clash. If so, points are worth more.
        if game_stats.game == "lol" and self.api_clients[game_stats.game].is_clash(self.game_monitors["lol"].active_game[guild_id]["queue_id"]):
            bet_multiplier = self.config.clash_multiplier
            tokens_gained *= bet_multiplier

        tokens_gained_desc = f"Everybody gains **{tokens_gained}** {tokens_name}" if tokens_gained != 0 else f"No one gets any {tokens_name}"
        response = (
            "=" * 38 +
            f"\n{game_desc} {tokens_gained_desc}."
        )
        response_bets = "**\n--- Results of bets made that game ---**\n"
        max_tokens_holder = self.meta_database.get_max_tokens_details()[1]
        betting_handler = self.betting_handlers[game_stats.game]

        any_bets = False # Bool to indicate whether any bets were made.
        for disc_id in game_database.game_users.keys():
            # See if the user corresponding to 'disc_id' was in-game.
            player_stats = game_stats.find_player_stats(disc_id, game_stats.filtered_player_stats)

            gain_for_user = 0
            if player_stats is not None: # If current user was in-game, they gain tokens for playing.
                gain_for_user = tokens_gained
                if player_stats.doinks is not None: # If user was awarded doinks, they get more tokens.
                    number_of_doinks = sum(map(int, player_stats.doinks))
                    gain_for_user += (self.config.betting_tokens_for_doinks * number_of_doinks)

                betting_handler.award_tokens_for_playing(disc_id, gain_for_user)

            # Get list of active bets for the current user.
            bets_made = game_database.get_bets(True, disc_id, guild_id)
            balance_before = self.meta_database.get_token_balance(disc_id)
            tokens_earned = gain_for_user # Variable for tracking tokens gained for the user.
            tokens_lost = -1 # Variable for tracking tokens lost for the user.
            disc_name = self.get_discord_nick(disc_id, guild_id)

            if bets_made is not None: # There are active bets for the current user.
                mention = self.get_mention_str(disc_id, guild_id)
                if any_bets:
                    response_bets += "-----------------------------\n"
                response_bets += f"Result of bets {mention} made:\n"

                for bet_ids, _, _, amounts, events, targets, bet_timestamp, _, _ in bets_made:
                    any_bets = True
                    # Resolve current bet which the user made. Marks it as won/lost in database.
                    bet_success, payout = betting_handler.resolve_bet(
                        disc_id,
                        bet_ids,
                        amounts,
                        bet_timestamp,
                        events,
                        targets,
                        game_stats,
                        bet_multiplier
                    )

                    response_bets += "- "
                    total_cost = 0 # Track total cost of the current bet.
                    for index, (amount, event, target) in enumerate(zip(amounts, events, targets)):
                        person = None
                        if target is not None:
                            person = self.get_discord_nick(target, guild_id)

                        bet_desc = betting_handler.get_dynamic_bet_desc(event, person)

                        response_bets += f"`{bet_desc}`"
                        if index != len(amounts) - 1: # Bet was a multi-bet.
                            response_bets += " **and** "

                        total_cost += amount

                    if len(amounts) > 1: # Again, bet was a multi-bet.
                        response_bets += " (multi-bet)"

                    if bet_success: # Bet was won. Track how many tokens it awarded.
                        response_bets += f": Bet was **won**! It awarded **{api_util.format_tokens_amount(payout)}** {tokens_name}!\n"
                        tokens_earned += payout
                    else: # Bet was lost. Track how many tokens it cost.
                        response_bets += f": Bet was **lost**! It cost **{api_util.format_tokens_amount(total_cost)}** {tokens_name}!\n"
                        tokens_lost += total_cost

                balance_before += tokens_lost
                if tokens_lost >= balance_before / 2: # Betting tokens was (at least) halved by losing.
                    quant_desc = "half"
                    if tokens_lost == balance_before: # Current bet cost ALL the user's tokens.
                        quant_desc = "all"
                    elif tokens_lost > balance_before / 2:
                        quant_desc = "more than half"
                    response_bets += f"{disc_name} lost {quant_desc} his {tokens_name} that game!\n"

                elif tokens_earned >= balance_before: # Betting tokens balanced was (at least) doubled.
                    quant_desc = "" if tokens_earned == balance_before else "more than"
                    response_bets += f"{disc_name} {quant_desc} doubled his amount of {tokens_name} that game!\n"

        new_max_tokens_holder = self.meta_database.get_max_tokens_details()[1]
        if new_max_tokens_holder != max_tokens_holder: # See if user now has most tokens after winning.
            max_tokens_name = self.get_discord_nick(new_max_tokens_holder, guild_id)

            # This person now has the most tokens of all users!
            response_bets += f"{max_tokens_name} now has the most {tokens_name} of everyone! "
            response_bets += "***HAIL TO THE KING, BABY!!!*** :crown:\n"

        if any_bets:
            response += response_bets

        return response, max_tokens_holder, new_max_tokens_holder

    async def play_event_sounds(self, game: str, intfar: int, doinks: list[int], guild_id: int):
        """
        Play potential Int-Far and Doinks sounds after a game has finished.

        :param game:        The name of the game that was played
        :param intfar:      Discord ID of the person that is Int-Far (or None)
        :param doinks:      List of Discord IDs of people who got doinks
        :param guild_id:    ID of the Discord server where the game took place
        """
        database = self.game_databases[game]
        users_in_voice = self.get_users_in_voice()
        voice_state = None

        # Check if any users from the game are in a voice channel
        for game_disc_id in self.game_monitors[game].users_in_game[guild_id]:
            for voice_disc_id in users_in_voice[guild_id][game]:
                if game_disc_id == int(voice_disc_id):
                    # Get voice state for member in voice chat
                    member = self.get_member_safe(game_disc_id, guild_id)
                    if member is None:
                        continue

                    voice_state = member.voice
                    break

        if voice_state is not None:
            # One or more users from the game is in a voice channel
            sounds_to_play = []

            # Add Int-Far sound to queue (if it exists)
            intfar_sound = database.get_event_sound(intfar, "intfar")
            if intfar_sound is not None:
                sounds_to_play.append(intfar_sound)

            # Add each doinks sound to queue (if any exist)
            for disc_id in doinks:
                doinks_sound = database.get_event_sound(disc_id, "doinks")
                if doinks_sound is not None:
                    sounds_to_play.append(doinks_sound)

            await self.audio_handler.play_sound(sounds_to_play, voice_state)

    def get_beaten_records_msg(
        self,
        parsed_game_stats: GameStats,
        best_records: list[tuple],
        worst_records: list[tuple]
    ):
        """
        Return a mesage describing any potentially beaten records (good or bad),
        such as a player getting the most kills ever, or most deaths ever, etc.

        :param best_records:    A list of data for broken good records (fx. most kills)
        :param worst_records:   A list of data for broken bad records (fx. least gold)
        :param guild_id:        ID of the Discord server where the game took place
        """
        response = "=" * 38

        for index, record_list in enumerate((best_records, worst_records)):
            best = index == 0

            for stat, value, disc_id, prev_value, prev_id in record_list:
                player_stats = parsed_game_stats.find_player_stats(disc_id, parsed_game_stats.filtered_player_stats)
                stat_quantity_desc = player_stats.stat_quantity_desc()

                stat_fmt = api_util.round_digits(value)
                stat_name_fmt = stat.replace('_', ' ')

                readable_stat = f"{stat_quantity_desc[stat][index]} {stat_name_fmt}"
                name = self.get_mention_str(disc_id, parsed_game_stats.guild_id)
                prev_name = self.get_discord_nick(prev_id, parsed_game_stats.guild_id)
                emote = "poggers" if best else "im_nat_kda_player_yo"
                best_fmt = "best" if best else "worst"
                by_fmt = "also by" if disc_id == prev_id else "by"

                response += (
                    f"\n{name} got the {readable_stat} EVER " +
                    f"with **{stat_fmt}** {stat_name_fmt}!!!" + " {emote_" + emote + "} " +
                    f"Prev {best_fmt} was **{api_util.round_digits(prev_value)}** " +
                    f"{by_fmt} {prev_name}"
                )

        return self.insert_emotes(response)

    def get_big_doinks_msg(self, awards_handler: AwardQualifiers, doinks: dict[list[tuple]]):
        """
        Return a message describing doinks criterias met for each player.
        These criterias include a lot of kills, high kda, high cs/min, etc.

        :param doinks:      Dictionary mapping discord IDs, for each player, to
                            a list of doink criterias met for that player
        :param guild_id:    ID of the Discord server where the game took place
        """
        mentions_str = ""
        any_mentions = False

        for disc_id in doinks:
            user_str = ""
            if doinks[disc_id] != []:
                prefix = "\n " if any_mentions else ""
                user_str = f"{prefix}{self.get_mention_str(disc_id, awards_handler.guild_id)} was insane that game! "
                user_str += f"He is awarded {len(doinks[disc_id])} " + "{emote_Doinks} for "
                any_mentions = True

            for (count, (stat_index, stat_value)) in enumerate(doinks[disc_id]):
                prefix = " *and* " if count > 0 else ""
                user_str += prefix + awards_handler.get_flavor_text("doinks", stat_index, "random", value=stat_value)

            mentions_str += user_str

            multiplier = 1
            if awards_handler.game == "lol" and self.api_clients[awards_handler.game].is_clash(
                self.game_monitors[awards_handler.game].active_game[awards_handler.guild_id]["queue_id"]
            ):
                # Doinks are worth 5x more during clash
                multiplier = self.config.clash_multiplier

            points = self.config.betting_tokens_for_doinks * len(doinks[disc_id]) * multiplier
            tokens_name = self.config.betting_tokens
            mentions_str += f"\nHe is also given **{points}** bonus {tokens_name} "
            mentions_str += "for being great {emote_swell}"

        return None if not any_mentions else mentions_str

    def get_rank_mentions_msg(self, awards_handler: AwardQualifiers, rank_mentions: dict[int, int]):
        ranks_str = "=" * 38

        for disc_id in rank_mentions:
            demotion, rank_index = rank_mentions[disc_id]
            formatted_flavor = awards_handler.get_flavor_text("rank", demotion, rank_index)
            ranks_str += f"\n{self.get_mention_str(disc_id, awards_handler.guild_id)} {formatted_flavor}"

        return None if rank_mentions == {} else self.insert_emotes(ranks_str)

    def get_cool_stats_msg(self, awards_handler: AwardQualifiers, cool_stats: dict[int, list[tuple]]):
        """
        Return a message describing random notable events that happened during
        the game that are not worthy of intfars, doinks, or honorable mentions,
        but are still interesting enough to mention. This includes stuff like
        stealing epic monsters, being dead for more than 10 minutes,
        and destroying 7 turrets or more.

        :param cool_stats:  Dictionary mapping discord IDs, for each player, to
                            a list of interesting events related to that player
        :param guild_id:    ID of the Discord server where the game took place
        """
        stats_str = "=" * 38 + "\n"
        any_stats = False

        for disc_id in cool_stats:
            user_str = ""

            if cool_stats[disc_id] != []:
                prefix = "\n" if any_stats else ""
                user_str = f"{prefix}{self.get_mention_str(disc_id, awards_handler.guild_id)} "
                any_stats = True

            for (count, (stat_index, stat_value)) in enumerate(cool_stats[disc_id]):
                prefix = " **and** " if count > 0 else ""
                user_str += prefix + awards_handler.get_flavor_text("stats", stat_index, "random", value=stat_value)

            stats_str += user_str

        return None if not any_stats else self.insert_emotes(stats_str)

    def get_timeline_msg(self, awards_handler: AwardQualifiers, timeline_mentions: list[tuple[int, int, int]]):
        """
        Return a message describing interesting events that happened during the game
        that relate to the Riot timeline API. This includes whether the team came
        back from a large gold deficit or threw a huge gold lead.

        ### Parameters
        :param awards_handler:      AwardQualifiers instance for getting relevant timeline
                                    flavor texts from the given mentions
        :param timeline_mentions:   List of timeline events that occured during the game.
                                    This is a tuple of (event_index, value, discord_id)

        ### Returns
        String describing timeline events that occured during the game
        or None if no timeline events occurred.
        """
        timeline_str = "=" * 38 + "\n"
        any_stats = False

        for event_index, value, disc_id in timeline_mentions:
            if not any_stats:
                event_str = ""
                any_stats = True
            else:
                event_str = "\n"

            if disc_id is not None: # User specific event.
                event_str += f"{self.get_mention_str(disc_id, awards_handler.guild_id)} "
            else: # Team-wide event.
                event_str += "We "

            event_str += awards_handler.get_flavor_text("timeline", event_index, "random", value=value)

            timeline_str += event_str

        return None if timeline_mentions == [] else self.insert_emotes(timeline_str)

    def get_lifetime_stats_msg(self, awards_handler: AwardQualifiers, lifetime_mentions: dict[int, list[tuple]]):
        stats_str = "=" * 38 + "\n"
        any_stats = False

        for disc_id in lifetime_mentions:
            user_str = ""

            if lifetime_mentions[disc_id] != []:
                prefix = "\n" if any_stats else ""
                user_str = f"{prefix}{self.get_mention_str(disc_id, awards_handler.guild_id)} "
                any_stats = True

            for (count, (stat_index, stat_value)) in enumerate(lifetime_mentions[disc_id]):
                prefix = " **and** " if count > 0 else ""
                user_str += prefix + awards_handler.get_flavor_text("lifetime_events", stat_index, value=stat_value)

            stats_str += user_str

        return None if not any_stats else self.insert_emotes(stats_str)

    def get_intfar_streak_msg(
        self,
        awards_handler: AwardQualifiers,
        intfar_id: int,
        intfar_streak: int,
        prev_intfar: int
    ):
        """
        Return a message describing the current Int-Far streak.
        This happens if someone ends their Int-Far streak, either by playing well,
        or by someone else getting Int-Far.
        It also describes whether someone is currently on an Int-Far streak.

        :param intfar_id:       Discord ID of the person who is Int-Far
        :param guild_id:        ID of the Discord server where the game took place
        :param intfar_streak:   Currently active Int-Far streak. I.e. how many games
                                in a row the same person has been the current Int-Far
        :param prev_intfar:     Discord ID of the person who was Int-Far
                                in the previous game
        """
        guild_id = awards_handler.guild_id
        current_nick = self.get_discord_nick(intfar_id, guild_id)
        current_mention = self.get_mention_str(intfar_id, guild_id)
        prev_mention = self.get_mention_str(prev_intfar, guild_id)

        if intfar_id is None:
            if intfar_streak > 1: # No one was Int-Far this game, but a streak was active.
                for disc_id in awards_handler.parsed_game_stats.filtered_player_stats:
                    if disc_id == prev_intfar:
                        return (
                            f"{prev_mention} has redeemed himself! " +
                            f"His Int-Far streak of {intfar_streak} has been broken. " +
                            "Well done, my son {emote_uwu}"
                        )
            return None

        if intfar_id == prev_intfar: # Current Int-Far was also previous Int-Far.
            streak = intfar_streak + 1
            streak_flavors = len(awards_handler.flavor_texts["intfar_streak"])
            streak_index = streak - 2 if streak - 2 < streak_flavors else streak_flavors - 1
            return awards_handler.get_flavor_text("intfar_streak", streak_index, nickname=current_mention, streak=streak)

        if intfar_streak > 1: # Previous Int-Far has broken his streak!
            return (
                f"Thanks to {current_nick}, the {intfar_streak} games Int-Far streak of " +
                f"{prev_mention} is over " + "{emote_woahpikachu}"
            )
    
        return None

    def get_ifotm_lead_msg(self, awards_handler: AwardQualifiers, intfar_id: int):
        """
        Return a message describing whether the person being Int-Far
        is now in the lead for Int-Far Of The Month (IFOTM)
        after acquring their new Int-Far award.

        :param intfar_id:   Discord ID of the person who is Int-Far
        :param guild_id:    ID of the Discord server where the game took place
        """
        database = self.game_databases[awards_handler.game]
        mention_str = self.get_mention_str(intfar_id, awards_handler.guild_id)
        message = f"{mention_str} has now taken the lead for Int-Far of the Month " + "{emote_nazi}"

        intfar_details = database.get_intfars_of_the_month()
        monthly_games, monthly_intfars = database.get_intfar_stats(intfar_id, monthly=True)

        if intfar_details == []: # No one was Int-Far yet this month.
            if monthly_games == self.config.ifotm_min_games - 1:
                return message # Current Int-Far is the first qualified person for IFOTM.
            return None

        highest_intfar = intfar_details[0]
        if highest_intfar[0] == intfar_id: # Current Int-Far is already in lead for IFOTM.
            return f"{mention_str} is still in the lead for Int-Far of the month " + "{emote_peberno}"

        curr_num_games = 1
        curr_intfars = 0
        for (disc_id, games, intfars, _) in intfar_details[1:]:
            if disc_id == intfar_id:
                curr_num_games = games + 1
                curr_intfars = intfars + 1
                break

        if curr_intfars == 0: # Current Int-Far was not qualified for IFOTM yet.
            curr_num_games = monthly_games + 1
            if curr_num_games == self.config.ifotm_min_games:
                # Current Int-Far has played enough games to qualify for IFOTM.
                curr_intfars = len(monthly_intfars) + 1

        new_pct = (curr_intfars / curr_num_games) * 100

        if new_pct > highest_intfar[3]:
            return message

        return None

    def get_intfar_message(
        self,
        awards_handler: AwardQualifiers,
        intfar_id: int,
        intfar_data: list[tuple[str, int]],
        ties: bool,
        ties_msg: str,
        intfar_streak: int,
        prev_intfar: int
    ):
        """
        Get message detailing who was the Int-Far and what condition(s) they met.

        :param disc_id:         Discord ID of the person being Int-Far
        :param guild_id:        ID of the Discord server where the game took place
        :param reason:          String describing the reason(s) for being Int-Far.
        :param ties_msg:        Message describing any potential ties that had to be
                                resolved between Int-Far candidates. Fx. if two people
                                both met the deaths criteria and had the same deaths
        :param intfar_streak:   Currently active Int-Far streak. I.e. how many games
                                in a row the same person has been the current Int-Far
        :param prev_intfar:     Discord ID of the person who was Int-Far
                                in the previous game
        """
        # Go through the criteria the chosen Int-Far met and list them in a readable format.
        reasons_list = list(awards_handler.INTFAR_REASONS())
        reason = ""
        for (count, (stat, value)) in enumerate(intfar_data):
            reason_index = reasons_list.index(stat)
            reason_text = awards_handler.get_flavor_text("intfar", reason_index, "random", **{stat: value})

            if count > 0:
                reason_text = " **AND** " + reason_text
            reason += reason_text

        full_ties_msg = ""
        if ties:
            full_ties_msg = "There are Int-Far ties! " + ties_msg + "\n"

        guild_id = awards_handler.guild_id
        mention_str = self.get_mention_str(intfar_id, guild_id)

        message = full_ties_msg
        message += awards_handler.get_flavor_text("intfar", "random", nickname=mention_str, reason=reason)

        # Get message detailing whether current Int-Far is on an Int-Far streak,
        # or whether them getting Int-Far broken another persons streak
        streak_msg = self.get_intfar_streak_msg(awards_handler, intfar_id, intfar_streak, prev_intfar)
        if streak_msg is not None:
            message += "\n" + streak_msg

        # Get message describing whether current Int-Far is now Int-Far Of The Month
        ifotm_lead_msg = self.get_ifotm_lead_msg(awards_handler, intfar_id)
        if ifotm_lead_msg is not None:
            message += "\n" + ifotm_lead_msg

        return self.insert_emotes(message)

    def get_honorable_mentions_msg(self, awards_handler: AwardQualifiers, intfar_streak: int, prev_intfar: int):
        """
        Return a message describing honorable mentions for events that
        happened during the game that were bad, but not bad enough to warrant
        someone getting Int-Far because of them. These events include
        not buying pinkwards, farming poorly, etc.

        :param mentions:    Dictionary mapping discord IDs, for each player, to
                            a list of events worth an honorable mention 
                            related to that player
        :param guild_id:    ID of the Discord server where the game took place
        """
        message = awards_handler.get_flavor_text("no_intfar", "random")
        honorable_mentions = awards_handler.get_honorable_mentions()

        mentions_str = "Honorable mentions goes out to:\n"
        any_mentions = False

        for disc_id in honorable_mentions:
            user_str = ""

            if honorable_mentions[disc_id] != []:
                prefix = "\n" if any_mentions else ""
                user_str = f"{prefix}- {self.get_mention_str(disc_id, awards_handler.guild_id)} for "
                any_mentions = True

            for (count, (stat_index, stat_value)) in enumerate(honorable_mentions[disc_id]):
                prefix = " **and** " if count > 0 else ""
                user_str += prefix + awards_handler.get_flavor_text("honorable", stat_index, "random", value=stat_value)

            mentions_str += user_str

        if any_mentions:
            message += "\n" + mentions_str

        # Get info about a potential Int-Far streak the person is currently on.
        streak_msg = self.get_intfar_streak_msg(awards_handler, None, intfar_streak, prev_intfar)
        if streak_msg is not None:
            message += "\n" + streak_msg

        return self.insert_emotes(message)

    def get_win_loss_streak_message(
        self,
        awards_handler: AwardQualifiers,
        active_streaks: dict[int, list[int]],
        broken_streaks: dict[int, list[int]]
    ):
        """
        Get message describing the win/loss streak of all players in game
        after it has concluded. Returns None if the streak is less than 3.

        :param filtered_stats:  List containing a tuple of (discord_id, game_stats)
                                for each Int-Far registered player on our team
        :param guild_id:        ID of the Discord server where the game took place
        """
        game_result = awards_handler.parsed_game_stats.win

        response = ""
        min_streak = self.config.stats_min_win_loss_streak

        for streak in active_streaks:
            mention_list = [
                self.get_mention_str(disc_id, awards_handler.guild_id)
                for disc_id in active_streaks[streak]
            ]

            flavor = "win_streak" if game_result == 1 else "loss_streak"
            quantifier = "is" if len(mention_list) == 1 else "are"
            nicknames_str = ", ".join(mention_list)
            num_streak_flavors = len(awards_handler.flavor_texts[flavor])
            streak_index = streak - min_streak if streak - min_streak < num_streak_flavors else num_streak_flavors - 1

            awards_handler.get_flavor_text(flavor, streak_index, nicknames=nicknames_str, quantifier=quantifier, streak=streak)

            response += "\n" + awards_handler.get_flavor_text(
                flavor,
                streak_index,
                nicknames=nicknames_str,
                quantifier=quantifier,
                streak=streak
            )

        for streak in broken_streaks:
            mention_list = [
                self.get_mention_str(disc_id, awards_handler.guild_id)
                for disc_id in broken_streaks[streak]
            ]

            flavor = "broken_loss_streak" if game_result == 1 else "broken_win_streak"
            nicknames_str = ", ".join(mention_list)

            response += "\n" + awards_handler.get_flavor_text(
                flavor,
                "random",
                nicknames=nicknames_str,
                streak=streak
            )

        if response != "":
            response = "=" * 38 + response

        return self.insert_emotes(response) if response != "" else None

    def save_stats(self, parsed_game_stats: GameStats):
        """
        Save all the stats after a finished game. This includes who was the Int-Far,
        information about doinks, general information about the game, such as
        duration, timestamp, and stats of players such as kills, gold earned, etc.

        :param filtered_stats:  List containing a tuple of (discord_id, game_stats)
                                for each Int-Far registered player on our team
        :param intfar_id:       Discord ID of the user who is the Int-Far.
                                This is None if no one was Int-Far
        :param intfar_reason:   String that encodes the reasons why a person was the
                                Int-Far in the finished game. This is None if no one
                                was Int-Far
        :param doinks:          Dictionary mapping discord IDs, for each player, to
                                a list of doink criterias met for that player
        :param guild_id:        ID of the Discord server where the game took place
        """
        try:
            # Save stats to database.
            database = self.game_databases[parsed_game_stats.game]
            best_records, worst_records = database.save_stats(parsed_game_stats)

            # Create backup of databases
            self.meta_database.create_backup()
            database.create_backup()
            logger.info("Game over! Stats were saved succesfully.")

            return best_records, worst_records

        except DBException as exception:
            # Log error along with relevant variables.
            game_id = self.game_monitors[game_id].active_game.get(parsed_game_stats.guild_id, {}).get("id")
            logger.bind(
                game_id=game_id,
                intfar_id=parsed_game_stats.intfar_id,
                intfar_reason=parsed_game_stats.intfar_reason,
                doinks=[player_stats.doinks for player_stats in parsed_game_stats.filtered_player_stats],
                guild_id=parsed_game_stats.guild_id
            ).exception("Game stats could not be saved!")

            raise exception

    async def user_joined_voice(
        self,
        disc_id: int,
        guild_id: int,
        poll_immediately=False,
        play_join_sound=True
    ):
        """
        Called when a user joins a voice channel in a server.
        Starts polling for active games whenever 2 or more people
        are in the same voice channel.

        :param disc_id:             Discord ID of the user that joined the channel
        :param guild_id:            ID of the Discord server of the voice channel
        :param poll_immediately:    Whether to start polling immediately,
                                    or wait a bit
        """
        guild_name = self.get_guild_name(guild_id)
        logger.debug(f"User joined voice in {guild_name}: {disc_id}")

        # Play sound that triggers when joining a voice channel, if any is set
        if (
            play_join_sound
            and (join_sound := self.meta_database.get_join_sound(disc_id)) is not None
            and (member := self.get_member_safe(disc_id, guild_id)) is not None
        ):
            await self.audio_handler.play_sound(join_sound, member.voice)

        users_in_voice = self.get_users_in_voice()[guild_id]
        for game in users_in_voice:
            user_game_info = self.game_databases[game].game_user_data_from_discord_id(disc_id)
            if user_game_info is not None:
                game_monitor = self.game_monitors[game]
                game_monitor.set_users_in_voice_channels(users_in_voice[game], guild_id)
                logger.debug(f"Game user joined voice: {user_game_info.player_name}")

                if game_monitor.should_poll(guild_id):
                    logger.info(f"Polling is now active for {api_util.SUPPORTED_GAMES[game]}!")
                    game_monitor.polling_active[guild_id] = True
                    asyncio.create_task(
                        game_monitor.poll_for_game_start(guild_id, guild_name, poll_immediately)
                    )

            logger.info(f"Active users in {guild_name} for {game}: {len(users_in_voice[game])}")

    async def user_left_voice(self, disc_id: int, guild_id: int):
        """
        Called when a user leaves a voice channel in a server.
        Stops polling for active games whenever 1 or less people
        are in the same voice channel.

        :param disc_id:             Discord ID of the user that joined the channel
        :param guild_id:            ID of the Discord server of the voice channel
        """
        guild_name = self.get_guild_name(guild_id)
        logger.debug(f"User left voice in {guild_name}: {disc_id}")

        users_in_voice = self.get_users_in_voice()[guild_id]
        for game in users_in_voice:
            game_monitor = self.game_monitors[game]
            game_monitor.set_users_in_voice_channels(users_in_voice[game], guild_id)
            if game_monitor.should_stop_polling(guild_id):
                game_monitor.stop_polling(guild_id)

    def get_role(self, role_name, guild):
        """
        Find a Discord role with the given name in the given guild.
        """
        for guild_role in guild.roles:
            if guild_role.name == role_name:
                return guild_role

        return None

    async def remove_intfar_role(self, intfar_id, role_id):
        """
        Find the Int-Far of the Month Discord role for a user and remove it.
        """
        nibs_guild = None
        for guild in self.guilds:
            if guild.id == api_util.MAIN_GUILD_ID:
                nibs_guild = guild
                break

        member = nibs_guild.get_member(intfar_id)
        role = nibs_guild.get_role(role_id)
        await member.remove_roles(role)

    async def reset_monthly_intfar_roles(self, game, guild):
        """
        When a new year has started, we remove Int-Far of the Month roles
        from all users who got them the previous year.
        """
        for month in range(12):
            month_name = api_util.MONTH_NAMES[month]
            old_role_name = f"Int-Far of the Month - {month_name}"
            role_name = f"Int-Far of the Month ({game}) - {month_name}"

            for role in guild.roles:
                if role.name == role_name or role_name == old_role_name:
                    for member in role.members:
                        logger.info(f"Removing {role.name} from {member.name}.")
                        await member.remove_roles(role)

    async def assign_monthly_intfar_role(self, game, month, winner_ids):
        nibs_guild = None
        for guild in self.guilds:
            if guild.id == api_util.MAIN_GUILD_ID:
                nibs_guild = guild
                break

        prev_month = month - 1 if month != 1 else 12

        if prev_month == 1: # Prev month was January, reset previous years IFOTM roles.
            await self.reset_monthly_intfar_roles(game, nibs_guild)

        # Colors:
        # Light blue, dark blue, cyan, mint,
        # light green, dark green, red, pink,
        # gold, yellow, orange, purple
        colors = [
            (0, 102, 204), (0, 0, 204), (0, 255, 255), (51, 255, 153),
            (0, 204, 0), (0, 51, 0), (255, 0, 0), (255, 102, 255),
            (153, 153, 0), (255, 255, 51), (255, 128, 0), (127, 0, 255)
        ]

        month_name = api_util.MONTH_NAMES[prev_month-1]
        color = discord.Color.from_rgb(*colors[prev_month-1])
        role_name = f"Int-Far of the Month ({game}) - {month_name}"

        role = self.get_role(role_name, nibs_guild)

        if role is None:
            role = await nibs_guild.create_role(name=role_name, colour=color)

        for intfar_id in winner_ids:
            member = nibs_guild.get_member(intfar_id)
            if member is not None:
                await member.add_roles(role)
            else:
                logger.bind(intfar_id=intfar_id).error("Int-Far to add badge to was None!")

    async def declare_monthly_intfar(self, game, monthly_monitor):
        """
        Retrieve the top three people who have gotten the most Int-Far awards this month
        for the given game and send out a message congratulating/shaming them.
        """
        curr_month = monthly_monitor.time_at_announcement.month
        prev_month = curr_month - 1 if curr_month != 1 else 12
        month_name = api_util.MONTH_NAMES[prev_month-1]

        intfar_data = self.game_databases[game].get_intfars_of_the_month()

        logger.bind(event="ifotm", data=intfar_data).info("IFOTM player data")

        if intfar_data == [] or game in monthly_monitor.disabled_games:
            # No one has played enough games to quality for IFOTM this month
            # or game isn't one for which we announce IFOTM
            logger.bind(event="ifotm_skipped").info(f"Skipping announcing IFOTM for {month_name}...")
            return

        game_stats = get_empty_game_data(game)
        intro_desc = get_awards_handler(
            game, self.config, self.api_clients[game], game_stats
        ).get_flavor_text("ifotm", curr_month - 1) + "\n\n"
        intro_desc += f"{api_util.SUPPORTED_GAMES[game]} Int-Far of the month for {month_name} is...\n"
        intro_desc += "***DRUM ROLL***\n"

        intfar_details = [
            (self.get_mention_str(disc_id), games, intfars, ratio)
            for (disc_id, games, intfars, ratio) in intfar_data
        ]

        desc, num_winners = monthly_monitor.get_description_and_winners(intfar_details)
        desc += ":clap: :clap: :clap: :clap: :clap: \n"
        desc += "{emote_uwu} {emote_sadbuttrue} {emote_smol_dave} "
        desc += "{emote_extra_creme} {emote_happy_nono} {emote_hairy_retard}"

        final_msg = self.insert_emotes(intro_desc + desc)

        await self.channels_to_write[api_util.MAIN_GUILD_ID].send(final_msg)

        # Assign Int-Far of the Month 'badge' (role) to the top Int-Far.
        winners = [tupl[0] for tupl in intfar_data[:num_winners]]

        await self.assign_monthly_intfar_role(game, curr_month, winners)

    async def set_newest_usernames(self):
        for game in api_util.SUPPORTED_GAMES:
            database = self.game_databases[game]
            for disc_id in database.game_users.keys():
                user = database.game_users[disc_id]
                try:
                    player_names = await self.api_clients[game].get_player_names_for_user(user)
                    for player_id, old_name, new_name in zip(user.player_id, user.player_name, player_names):
                        if new_name is not None and new_name != old_name:
                            logger.info(f"Updated username from {old_name} to {new_name} in {game}")
                            database.set_user_name(disc_id, player_id, new_name)
                except Exception:
                    logger.bind(event="set_newest_usernames", disc_id=disc_id, game=game).exception(
                        "Failed to get new username"
                    )

                    await asyncio.sleep(2)

    async def send_end_of_split_message(self):
        min_games = 10
        offset_secs = 30 * 24 * 60 * 60
        now = datetime.now().timestamp()
        database = self.game_databases["lol"]

        # Check if all player ranks have been reset
        all_reset = True
        for disc_id in database.game_users.keys():
            curr_rank_solo, curr_rank_flex = database.get_current_rank(disc_id)
            summ_id = database.game_users[disc_id].player_id[0]
            rank_data = await self.api_clients["lol"].get_player_rank(summ_id, now - offset_secs)
            new_rank_solo, new_rank_flex = parse_player_rank(rank_data)

            if all(rank is None for rank in (curr_rank_solo, curr_rank_flex, new_rank_solo, new_rank_flex)):
                continue

            if (
                (curr_rank_solo is not None and new_rank_solo is not None)
                or (curr_rank_flex is not None and new_rank_flex is not None)
            ):
                all_reset = False
                break

        # If ranks are reset, get the start of the previous split and send
        # end of split summary to players with more than 10 games that split
        if all_reset:
            prev_split_start = database.get_split_start(offset=offset_secs)
            for disc_id in database.game_users.keys():
                latest_timestamp = database.get_split_message_status(disc_id)
                if (
                    latest_timestamp is not None
                    and database.get_games_count(disc_id, prev_split_start) >= min_games
                ):
                    try:
                        await handle_end_of_split_msg(self, disc_id)
                        database.set_split_message_sent(disc_id, now)
                        logger.bind(event="end_split_message_success").info(f"Sent end-of-split message to {disc_id}")
                    except Exception:
                        logger.exception(event="end_split_message_error").info(f"Error when sending end-of-split message to {disc_id}")

    async def polling_loop(self):
        """
        Incrementally polls for a few things.
        Firstly, checks whether it's the first day of the month.
        If so, the Int-Far of the previous month is announced.
        Secondly, once every day, the newest patch for League
        is checked for, to see if any new champs have been released
        that we need to download data for.
        """
        ifotm_monitor = MonthlyIntfar(self.config.hour_of_ifotm_announce)
        logger.info("Starting Int-Far-of-the-month monitor... ")

        format_time = ifotm_monitor.time_at_announcement.strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"Monthly Int-Far will be crowned at {format_time} UTC+1")

        dt_now = datetime.now()
        duration = api_util.format_duration(dt_now, ifotm_monitor.time_at_announcement)
        logger.info(f"Time until then: {duration}")

        curr_day = dt_now.day

        time_to_sleep = 30
        while not ifotm_monitor.should_announce():
            new_day = datetime.now().day
            if new_day != curr_day:
                logger.bind(event="ifotm_announce_date").info(f"IFOTM annouce date on day {new_day}")
                try:
                    # Download latest information from Riot API.
                    self.api_clients["lol"].get_latest_data()
                except Exception:
                    logger.bind(event="get_latest_data", game="lol").exception(
                        "Failed to retrieve latest info from Riot API"
                    )

                # Get latest usernames for all players in all games, if they've changed
                await self.set_newest_usernames()

                # Check if a ranked split in League have ended, by seeing
                # if people's ranks are reset and send a end-of-split
                # summary message, if so
                #await self.send_end_of_split_message()

                curr_day = new_day

            await asyncio.sleep(time_to_sleep)

        for game in api_util.SUPPORTED_GAMES:
            await self.declare_monthly_intfar(game, ifotm_monitor)

        await asyncio.sleep(3600) # Sleep for an hour before resetting.
        asyncio.create_task(self.polling_loop())

    async def announce_jeopardy_winner(self, player_data):
        iteration = api_util.JEOPARDY_ITERATION
        edition = api_util.JEOPADY_EDITION

        ties = 0
        for index, data in enumerate(player_data[1:], start=1):
            if player_data[index-1]["score"] > data["score"]:
                break

            ties += 1

        if ties == 0:
            mention = self.get_mention_str(player_data[0]["id"])
            winner_desc = (
                f"{mention} is the winner of the *LoL Jeopardy {edition}* with **{player_data[0]['score']} points**!!! "
                "All hail the king :crown:\n"
                "They get a special badge of honor on Discord and wins a **1350 RP** skin!"
            )

        elif ties == 1:
            mention_1 = self.get_mention_str(player_data[0]["id"])
            mention_2 = self.get_mention_str(player_data[1]["id"])
            winner_desc = (
                f"{mention_1} and {mention_2} both won the *LoL Jeopardy {edition}* with "
                f"**{player_data[0]['score']} points**!!!\n"
                "They both get a special badge of honor on Discord and win a **975 RP** skin!"
            )

        elif ties > 1:
            players_tied = ", ".join(
                self.get_mention_str(data["id"]) for data in player_data[:ties]
            ) + self.get_mention_str(player_data[ties]["id"])
            winner_desc = (
                f"{players_tied} all got the same score (with **{player_data[0]['score']} points**) "
                f"in the *LoL Jeopardy {edition}*!!!\n"
                "They all get a special badge of honor on Discord and all win a **975 RP** skin!"
            )

        # Hand out a special badge to the winner(s)
        guild_id = api_util.MY_GUILD_ID if self.config.env == "dev" else api_util.GUILD_MAP["core"]
        guild = self.get_guild(guild_id)
        role = self.get_role(f"Jeopardy v{iteration} Master", guild)
        if role is not None:
            for data in player_data[:ties+1]:
                member = guild.get_member(data["id"])
                if member is not None:
                    await member.add_roles(role)

        channel_id = 512363920044982274 if self.config.env == "dev" else 808796236692848650
        channel = guild.get_channel(channel_id)

        await channel.send(winner_desc)

    async def send_error_msg(self, guild_id):
        """
        This method is called whenenver a critical error occurs.
        It causes the bot to post an error message to the channel, pinging me to fix it.
        """
        mention_me = self.get_mention_str(commands_util.ADMIN_DISC_ID, guild_id)
        message = "Oh frick, It appears I've crashed {emote_nat_really_fine} "
        message += f"{mention_me}, come and fix me!!! " + "{emote_angry_gual}"
        await self.channels_to_write[guild_id].send(self.insert_emotes(message))

    async def get_all_messages(self, channel):
        counter = 0
        with self.meta_database:
            try:
                print(f"Retrieving messages from guild {channel.guild.name}, channel {channel.name}")
                async for message in channel.history(limit=None, oldest_first=True):
                    if message.content.startswith("!play"):
                        split = message.content.split(" ")
                        if len(split) > 1 and self.audio_handler.is_valid_sound(split[1].strip()):
                            self.meta_database.add_sound_hit(split[1].strip(), message.created_at)

                            counter += 1
                            if counter % 100 == 0:
                                print(f"Saved {counter} plays.", flush=True)
            except discord.errors.Forbidden:
                print(f"Can't retrieve messages, insufficient permissions")

        print(f"Done getting {counter} plays!", flush=True)

    def get_main_channel(self):
        return (
            self.channels_to_write[api_util.MAIN_GUILD_ID]
            if self.config.env == "production"
            else self.channels_to_write[api_util.MY_GUILD_ID]
        )

    async def on_connect(self):
        logger.info("Client connected")

    async def on_disconnect(self):
        logger.info("Client disconnected...")

    async def on_ready(self):
        if self.initialized:
            logger.warning("Ready was called, but bot was already initialized... Weird stuff.")
            return

        await self.change_presence( # Change Discord activity.
            activity=discord.Activity(
                name="you inting in league",
                type=discord.ActivityType.watching
            )
        )

        logger.info('Logged on as {0}!'.format(self.user))
        self.initialized = True

        for guild in self.guilds:
            await guild.chunk()

            if guild.id in api_util.GUILD_IDS:
                for voice_channel in guild.voice_channels:
                    members_in_voice = voice_channel.members
                    for member in members_in_voice:
                        # Start polling for an active game
                        # if more than one user is active in voice.
                        await self.user_joined_voice(member.id, guild.id, True, False)

                for text_channel in guild.text_channels:
                    # Find the channel to write in for each guild.
                    if text_channel.id in CHANNEL_IDS and self.config.env == "production":
                        self.channels_to_write[guild.id] = text_channel
                        break

            elif guild.id == api_util.MY_GUILD_ID and self.config.env == "dev":
                CHANNEL_IDS.append(guild.text_channels[0].id)
                self.channels_to_write[guild.id] = guild.text_channels[0]

        # Call any potential listeners on the 'ready' event
        for (callback, args) in self.event_listeners.get("ready", []):
            evaluated = callback(*args)
            if asyncio.iscoroutine(evaluated):
                await evaluated

        asyncio.create_task(self.polling_loop())

        if self.flask_conn is not None: # Listen for external commands from web page.
            event_loop = asyncio.get_event_loop()
            Thread(target=listen_for_request, args=(self, event_loop)).start()

    async def paginate(self, channel, data, chunk, lines_per_page, header=None, footer=None, message=None):
        chunk_start = chunk * lines_per_page
        first_chunk = chunk_start == 0

        chunk_end = (chunk + 1) * lines_per_page
        last_chunk = chunk_end >= len(data)
        if last_chunk:
            chunk_end = len(data)

        text = ""
        if header is not None:
            text = header + "\n"
        text += "\n".join(data[chunk_start:chunk_end])
        if footer is not None:
            text += "\n" + footer
        text += f"\n**Page {chunk+1}/{ceil(len(data) / lines_per_page)}**"

        if message is None:
            message = await channel.send(text)
        else:
            await message.clear_reactions()
            await message.edit(content=text)

        self.pagination_data[message.id] = {
            "message": message, "data": data, "header": header,
            "footer": footer, "chunk": chunk, "lines": lines_per_page
        }

        if not first_chunk:
            await message.add_reaction("◀")
        if not last_chunk:
            await message.add_reaction("▶")

    async def on_raw_reaction_add(self, react_event):
        seconds_max = 60 * 60 * 12

        # Clean up old pagination messages.
        messages_to_remove = []
        for message_id in self.pagination_data:
            created_at = self.pagination_data[message_id]["message"].created_at
            if time() - created_at.timestamp() > seconds_max:
                messages_to_remove.append(message_id)

        for message_id in messages_to_remove:
            del self.pagination_data[message_id]

        # Clean up old audio control reacts
        messages_to_remove = []
        for message_id in self.audio_action_data:
            created_at = self.audio_action_data[message_id]["timestamp"]
            if time() - created_at > seconds_max:
                messages_to_remove.append(message_id)

        for message_id in messages_to_remove:
            del self.audio_action_data[message_id]

        message_id = react_event.message_id
        guild_id = react_event.guild_id
        if (
            react_event.event_type == "REACTION_ADD"
            and react_event.member != self.user
        ):
            if (message_id in self.pagination_data 
                and react_event.emoji.name in ("▶", "◀")
                and self.pagination_data[message_id]["message"].created_at
            ):
                message_data = self.pagination_data[message_id]
                reaction_next = react_event.emoji.name == "▶"
                new_chunk = message_data["chunk"] + 1 if reaction_next else message_data["chunk"] - 1
                await self.paginate(
                    message_data["message"].channel, message_data["data"],
                    new_chunk, message_data["lines"], message_data["header"],
                    message_data["footer"], message_data["message"]
                )
            elif (
                self.audio_handler.playback_msg.get(guild_id) is not None
                and message_id == self.audio_handler.playback_msg[guild_id].id
                and react_event.emoji.name in self.audio_handler.AUDIO_CONTROL_EMOJIS
            ):
                channel = self.get_channel(react_event.channel_id)
                if message_id not in self.audio_action_data:
                    self.audio_action_data[message_id] = {
                        "timestamp": time(),
                        "users": {}
                    }

                self.audio_action_data[message_id]["users"][react_event.member.id] = react_event.emoji
                await self.audio_handler.audio_control_pressed(react_event.emoji, react_event.member, channel)

    async def on_raw_reaction_remove(self, react_event):
        """
        Trigger the same actions in audio_handler when a user adds a reaction
        as when they remove an reaction that corresponds to an audio player action.
        """
        message_id = react_event.message_id
        user_id = react_event.user_id
        guild_id = react_event.guild_id
        if (
            user_id != self.user.id
            and self.audio_handler.playback_msg.get(guild_id) is not None
            and message_id == self.audio_handler.playback_msg[guild_id].id
            and message_id in self.audio_action_data
            and react_event.emoji.name in self.audio_handler.AUDIO_CONTROL_EMOJIS
        ):
            if (
                user_id in self.audio_action_data[message_id]["users"]
                and react_event.emoji == self.audio_action_data[message_id]["users"][user_id]
            ):
                del self.audio_action_data[message_id]["users"][user_id]
                channel = self.get_channel(react_event.channel_id)
                member = self.get_member_safe(user_id, react_event.guild_id)
                await self.audio_handler.audio_control_pressed(react_event.emoji, member, channel)

    async def send_dm(self, text, disc_id):
        """
        Send a private message to the user with the given Discord ID.
        """
        user = self.get_user(disc_id)
        try:
            await user.send(content=text)
            return True
        except (HTTPException, Forbidden):
            return False

    async def not_implemented_yet(self, message):
        msg = self.insert_emotes("This command is not implemented yet {emote_peberno}")
        await message.channel.send(msg)

    async def on_message(self, message):
        """
        Method that is called when a message is sent on Discord
        in any of the channels that Int-Far is active in. 
        """
        if message.author == self.user: # Ignore message since it was sent by us (the bot).
            return

        if ((self.config.env == "dev" and message.guild.id != api_util.MY_GUILD_ID)
                or (self.config.env == "production" and message.guild.id not in api_util.GUILD_IDS)):
            # If Int-Far is running in dev mode, only handle messages that are sent from
            # my personal sandbox Discord server.
            return

        msg = message.content.strip()
        if msg.startswith("!"): # Message is a command.
            split = msg.split(None)
            command = split[0][1:].lower()

            valid_cmd, show_usage = commands_util.valid_command(message, command, split[1:])
            if not valid_cmd:
                if command == "usage":
                    await message.channel.send(
                        f"Write `!usage [command]` to see how to use a specific command."
                    )
                elif show_usage:
                    await handle_usage_msg(self, message, command)
                else:
                    possible_commands = [
                        cmd for cmd in commands_util.COMMANDS
                        if message.guild.id in commands_util.COMMANDS[cmd].guilds
                    ]

                    if (closest_match := api_util.get_closest_match(command, possible_commands)) is not None:
                        await message.channel.send(
                            f"Invalid command `!{command}`, did you mean `!{closest_match}`?"
                        )
                return

            # The following lines are spam protection.
            time_from_last_msg = time() - self.last_message_time.get(message.author.id, 0)
            self.last_message_time[message.author.id] = time()
            curr_timeout = self.user_timeout_length.get(message.author.id, 0)
            if time_from_last_msg < curr_timeout: # User has already received a penalty for spam.
                if curr_timeout < 10:
                    curr_timeout *= 2 # Increase penalty...
                    if curr_timeout > 10: # ... Up to 10 secs. max.
                        curr_timeout = 10
                    self.user_timeout_length[message.author.id] = curr_timeout
                return

            if time_from_last_msg < self.config.message_timeout:
                # Some guy is sending messages too fast!
                self.user_timeout_length[message.author.id] = self.config.message_timeout
                await message.channel.send("Slow down cowboy! You are sending messages real sped-like!")
                return

            self.user_timeout_length[message.author.id] = 0 # Reset user timeout length.

            timeout_length = self.command_timeout_lengths.get(command, 1)
            time_since_last_command = time() - self.last_command_time.get(command, 0)
            if time_since_last_command < timeout_length:
                time_left = timeout_length - time_since_last_command
                await message.channel.send(
                    f"Hold your horses! This command is on cooldown for {time_left:.1f} seconds."
                )
                return

            self.last_command_time[command] = time()

            command_handler = commands.get_handler(command)
            await command_handler.handle_command(self, message, split[1:])

    async def send_message_unprompted(self, message, guild_id):
        try:
            await self.channels_to_write[int(guild_id)].send(message)
        except Exception:
            logger.bind(
                message=message,
                guild_id=guild_id
            ).exception("Could not send message unprompted.")

    async def on_voice_state_update(self, member, before, after):
        if member.guild.id in api_util.GUILD_IDS:
            if before.channel is None and after.channel is not None: # User joined.
                await self.user_joined_voice(member.id, member.guild.id)
            elif before.channel is not None and after.channel is None: # User left.
                await self.user_left_voice(member.id, member.guild.id)

    async def close(self):
        await super().close()

        self.api_clients["cs2"].close()

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
    client.run(config.discord_token)
