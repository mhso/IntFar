import random
import asyncio
from io import BytesIO
from threading import Thread
from time import time
from math import ceil
from datetime import datetime

import discord
from discord.errors import NotFound, DiscordException, HTTPException, Forbidden

from mhooge_flask.logging import logger

from discbot.montly_intfar import MonthlyIntfar
from discbot.app_listener import listen_for_request
from discbot import commands
from discbot.commands.meta import handle_usage_msg
from api import game_stats, bets, award_qualifiers
from api.game_monitor import GameMonitor
from api.database import DBException, Database
from api.bets import BettingHandler
from api.audio_handler import AudioHandler
from api.shop import ShopHandler
from api.riot_api import RiotAPIClient
from api.config import Config
import discbot.commands.util as commands_util
import api.util as api_util
from ai.data import shape_predict_data

MAIN_CHANNEL_ID = 730744358751567902

CHANNEL_IDS = [ # List of channels that Int-Far will write to.
    MAIN_CHANNEL_ID,
    805218121610166272,
    808796236692848650
]

INTFAR_FLAVOR_TEXTS = api_util.load_flavor_texts("intfar")

NO_INTFAR_FLAVOR_TEXTS = api_util.load_flavor_texts("no_intfar")

MOST_DEATHS_FLAVORS = api_util.load_flavor_texts("most_deaths")

LOWEST_KDA_FLAVORS = api_util.load_flavor_texts("lowest_kda")

LOWEST_KP_FLAVORS = api_util.load_flavor_texts("lowest_kp")

LOWEST_VISION_FLAVORS = api_util.load_flavor_texts("lowest_vision")

HONORABLE_MENTIONS = [
    api_util.load_flavor_texts("mentions_no_vision_ward"),
    api_util.load_flavor_texts("mentions_low_damage"),
    api_util.load_flavor_texts("mentions_low_cs_min"),
    api_util.load_flavor_texts("mentions_no_epic_monsters")
]

COOL_STATS = [
    api_util.load_flavor_texts("stats_time_spent_dead"),
    api_util.load_flavor_texts("stats_objectives_stolen"),
    api_util.load_flavor_texts("stats_turrets_killed")
]

TIMELINE_EVENTS = [
    api_util.load_flavor_texts("timeline_comeback"),
    api_util.load_flavor_texts("timeline_throw"),
    api_util.load_flavor_texts("timeline_goldkeeper")
]

DOINKS_FLAVORS = [
    api_util.load_flavor_texts("doinks_kda"),
    api_util.load_flavor_texts("doinks_kills"),
    api_util.load_flavor_texts("doinks_damage"),
    api_util.load_flavor_texts("doinks_penta"),
    api_util.load_flavor_texts("doinks_vision_score"),
    api_util.load_flavor_texts("doinks_kp"),
    api_util.load_flavor_texts("doinks_jungle"),
    api_util.load_flavor_texts("doinks_cs")
]

INTFAR_STREAK_FLAVORS = api_util.load_flavor_texts("intfar_streak")

WIN_STREAK_FLAVORS = api_util.load_flavor_texts("win_streak")
LOSS_STREAK_FLAVORS = api_util.load_flavor_texts("loss_streak")

BROKEN_WIN_STREAK_FLAVORS = api_util.load_flavor_texts("broken_win_streak")
BROKEN_LOSS_STREAK_FLAVORS = api_util.load_flavor_texts("broken_loss_streak")

IFOTM_FLAVORS = api_util.load_flavor_texts("ifotm")

def get_intfar_flavor_text(nickname, reason):
    flavor_text = INTFAR_FLAVOR_TEXTS[random.randint(0, len(INTFAR_FLAVOR_TEXTS)-1)]

    return flavor_text.replace("{nickname}", nickname).replace("{reason}", reason)

def get_no_intfar_flavor_text():
    return NO_INTFAR_FLAVOR_TEXTS[random.randint(0, len(NO_INTFAR_FLAVOR_TEXTS)-1)]

def replace_value(flavor_text, value, keyword="value"):
    quantifier = "" if isinstance(value, int) and value == 1 else "s"

    return flavor_text.replace("{" + keyword + "}", f"**{value}**").replace("{quantifier}", quantifier)

def get_reason_flavor_text(value, reason):
    flavor_values = []
    if reason == "kda":
        flavor_values = LOWEST_KDA_FLAVORS
    elif reason == "deaths":
        flavor_values = MOST_DEATHS_FLAVORS
    elif reason == "kp":
        flavor_values = LOWEST_KP_FLAVORS
    elif reason == "visionScore":
        flavor_values = LOWEST_VISION_FLAVORS
    flavor_text = flavor_values[random.randint(0, len(flavor_values)-1)]

    return replace_value(flavor_text, value, reason)

def get_honorable_mentions_flavor_text(index, value):
    flavor_values = HONORABLE_MENTIONS[index]
    flavor_text = flavor_values[random.randint(0, len(flavor_values)-1)]

    return replace_value(flavor_text, value)

def get_cool_stat_flavor_text(index, value):
    flavor_values = COOL_STATS[index]
    flavor_text = flavor_values[random.randint(0, len(flavor_values)-1)]

    return replace_value(flavor_text, value)

def get_timeline_events_flavor_text(index, value):
    flavor_values = TIMELINE_EVENTS[index]
    flavor_text = flavor_values[random.randint(0, len(flavor_values)-1)]

    return replace_value(flavor_text, value)

def get_doinks_flavor_text(index, value):
    flavor_values = DOINKS_FLAVORS[index]

    flavor_text = flavor_values[random.randint(0, len(flavor_values)-1)]
    if value is None:
        return flavor_text

    return replace_value(flavor_text, value)

def get_game_streak_flavor_text(min_streak, nicknames, streak, win):
    streak_flavors = WIN_STREAK_FLAVORS if win else LOSS_STREAK_FLAVORS
    index = streak - min_streak if streak - min_streak < len(streak_flavors) else len(streak_flavors) - 1

    quantifier = "is" if len(nicknames) == 1 else "are"
    nicknames_str = ", ".join(nicknames)

    return streak_flavors[index].replace(
        "{nicknames}", nicknames_str
    ).replace(
        "{quantifier}", quantifier
    ).replace("{streak}", str(streak))

def get_broken_game_streak_flavor_text(nicknames, streak, win):
    streak_flavors = BROKEN_LOSS_STREAK_FLAVORS if win else BROKEN_WIN_STREAK_FLAVORS
    flavor_text = streak_flavors[random.randint(0, len(streak_flavors)-1)]

    nicknames_str = ", ".join(nicknames)

    return flavor_text.replace(
        "{nicknames}", nicknames_str
    ).replace("{streak}", str(streak))

def get_intfar_streak_flavor_text(nickname, streak):
    index = streak - 2 if streak - 2 < len(INTFAR_STREAK_FLAVORS) else len(INTFAR_STREAK_FLAVORS) - 1

    return INTFAR_STREAK_FLAVORS[index].replace("{nickname}", nickname).replace("{streak}", str(streak))

def get_ifotm_flavor_text(month):
    return IFOTM_FLAVORS[month - 1]

class DiscordClient(discord.Client):
    def __init__(
            self,
            config: Config,
            database: Database,
            betting_handler: BettingHandler,
            riot_api: RiotAPIClient,
            audio_handler: AudioHandler,
            shop_handler: ShopHandler,
            **kwargs
        ):
        """
        Initialize the Discord client. This class contains the logic for interacting
        with the Dicscord API, which includes sending messages, getting data about
        users, playing sounds, etc.

        :param config:          Config instance that holds all the configuration
                                options for Int-Far
        :param database:        SQLiteDatabase instance that handles the logic
                                of interacting with the sqlite database
        :param betting_handler: BettingHandler instance that handles the logic
                                of creating, resolving, and listing bets
        :param riot_api:        RiotAPIClient instance that handles the logic of
                                communicating with Riot Games' LoL API
        :param audio_handler:   AudioHandler instance that handles the logic of
                                listing and playing sounds through Discord
        :param shop_handler:    ShopHandler instance that handles the logic of
                                buying, selling, listing items for betting tokens
        :param **kwargs:        Various keyword arguments.
        """
        super().__init__(
            intents=discord.Intents(
                members=True,
                voice_states=True,
                guilds=True,
                emojis=True,
                reactions=True,
                guild_messages=True,
                message_content=True
            )
        )
        self.config = config
        self.database = database
        self.riot_api = riot_api
        self.betting_handler = betting_handler
        self.audio_handler = audio_handler
        self.shop_handler = shop_handler
        
        self.ai_conn = kwargs.get("ai_pipe")
        self.main_conn = kwargs.get("main_pipe")
        self.flask_conn = kwargs.get("flask_pipe")

        self.game_monitor = GameMonitor(
            self.config,
            self.database,
            self.riot_api,
            self.on_game_over
        )
        self.pagination_data = {}
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

    async def on_game_over(self, game_info: dict, guild_id: int, status_code: int):
        """
        Callback called by the game monitor when a game is finished.

        :param data:        Dictionary containing un-filtered data about a finished
                            game fetched from Riot League API
        :param guild_id:    ID of the Discord server where the game took place
        :param status_code: Integer that describes the status of the finished game
        """
        if status_code == self.game_monitor.POSTGAME_STATUS_ERROR:
            # Something went terribly wrong when handling the end of game logic
            # Send error message to Discord to indicate things went bad.
            await self.send_error_msg(guild_id)

        if status_code == self.game_monitor.POSTGAME_STATUS_MISSING:
            self.database.save_missed_game(game_info["gameId"], guild_id, int(time()))

            # Send message pinging me about the error.
            mention_me = self.get_mention_str(commands_util.ADMIN_DISC_ID, guild_id)
            message_str = (
                "Riot API is being a dickfish again, not much I can do :shrug:\n"
                f"{mention_me} will add the game manually later."
            )

            await self.send_message_unprompted(message_str, guild_id)

        elif status_code == self.game_monitor.POSTGAME_STATUS_SOLO:
            response = "Only one person in that game. "
            response += "no Int-Far will be crowned "
            response += "and no stats will be saved."
            await self.channels_to_write[guild_id].send(response)

        elif status_code == self.game_monitor.POSTGAME_STATUS_URF:
            # Gamemode was URF. Don't save stats then.
            response = "That was an URF game {emote_poggers} "
            response += "no Int-Far will be crowned "
            response += "and no stats will be saved."
            await self.channels_to_write[guild_id].send(self.insert_emotes(response))

        elif status_code == self.game_monitor.POSTGAME_STATUS_NOT_SR:
            # Game is not on summoners rift. Same deal.
            response = "That game was not on Summoner's Rift "
            response += "{emote_woahpikachu} no Int-Far will be crowned "
            response += "and no stats will be saved."
            await self.channels_to_write[guild_id].send(self.insert_emotes(response))
    
        elif status_code == self.game_monitor.POSTGAME_STATUS_REMAKE:
            # Game was too short, most likely a remake.
            response = (
                "That game lasted less than 5 minutes " +
                "{emote_zinking} assuming it was a remake. " +
                "No stats are saved."
            )
            await self.channels_to_write[guild_id].send(self.insert_emotes(response))
        
        elif status_code == self.game_monitor.POSTGAME_STATUS_OK:
            await self.handle_game_over(game_info, guild_id)

    async def handle_game_over(self, game_info: dict, guild_id: int):
        """
        Called when a game is over and is valid. Handles all the post-game mentions
        about the intfar, doinks, bets, etc. and handles inserting all the stats
        from the game into the database.

        :param data:        Dictionary containing un-filtered data about a finished
                            game fetched from Riot League API
        :param guild_id:    ID of the Discord server where the game took place
        """
        try: # Get formatted stats that are relevant for the players in the game.
            relevant_stats, users_in_game = game_stats.get_relevant_stats(
                self.database.summoners, self.game_monitor.users_in_game.get(guild_id), game_info
            )
            filtered_stats = game_stats.get_filtered_stats(relevant_stats)
        except ValueError as exc:
            # Game data was not formatted correctly for some reason (Rito pls).
            logger.bind(game_id=game_info["gameId"]).exception(
                "Game data is not well formed!"
            )

            # Send error message to Discord and re-raise exception.
            await self.send_error_msg(guild_id)
            raise exc

        self.game_monitor.users_in_game[guild_id] = users_in_game
        logger.debug(f"Users in game after: {users_in_game}")

        if self.riot_api.is_clash(self.game_monitor.active_game[guild_id]["queue_id"]):
            # Game was played as part of a clash tournament, so it awards more betting tokens.
            multiplier = self.config.clash_multiplier
            await self.channels_to_write[guild_id].send(
                "**>>>>> THAT WAS A CLASH GAME! REWARDS ARE WORTH " +
                f"{multiplier} TIMES AS MUCH!!! <<<<<**"
            )

        # Determine who was the Int-Far (if anyone was).
        intfar, intfar_reason, response = self.get_intfar_data(
            relevant_stats,
            filtered_stats,
            guild_id
        )

        # Determine who was awarded doinks.
        doinks, doinks_response = self.get_doinks_data(filtered_stats, guild_id)
        if doinks_response is not None:
            response += "\n" + self.insert_emotes(doinks_response)

        # Get data about win or loss streaks.
        game_streak_response = self.get_win_loss_streak_data(filtered_stats, guild_id)
        if game_streak_response is not None:
            response += "\n" + game_streak_response

        await self.channels_to_write[guild_id].send(response)

        await asyncio.sleep(1)
    
        # Resolve any active bets made on the game.
        response, max_tokens_id, new_max_tokens_id = self.resolve_bets(
            filtered_stats, intfar, intfar_reason, doinks, guild_id
        )

        if max_tokens_id != new_max_tokens_id: # Assign new 'goodest_boi' title.
            await self.assign_top_tokens_role(max_tokens_id, new_max_tokens_id)

        try:
            # Get timeline data events for the game.
            timeline_data = self.riot_api.get_game_timeline(game_info["gameId"])
            if timeline_data is not None:
                timeline_response = self.get_cool_timeline_data(
                    filtered_stats, timeline_data, guild_id
                )
                if timeline_response is not None:
                    response = timeline_response + "\n" + response
        except Exception:
            logger.exception("Exception when getting timeline data")

        # Get other cool stats about players.
        cool_stats_response = self.get_cool_stats_data(filtered_stats, guild_id)
        if cool_stats_response is not None:
            response = cool_stats_response + "\n" + response

        # Save data from the game to the database.
        best_records, worst_records = self.save_stats(
            filtered_stats, intfar, intfar_reason, doinks, guild_id
        )

        if best_records != [] or worst_records != []:
            records_response = self.get_beaten_records_msg(
                best_records, worst_records, guild_id
            )
            response = records_response + "\n" + response

        await self.channels_to_write[guild_id].send(response)

        await self.play_event_sounds(intfar, doinks, guild_id)

        if self.ai_conn is not None:
            logger.info("Training AI Model with new game data.")

            train_data = shape_predict_data(
                self.database, self.riot_api, self.config, users_in_game
            )

            # Send train request to AI process and recieve result
            self.ai_conn.send(
                ("train", [train_data, filtered_stats[0][1]["gameWon"]])
            )
            loss, probability = self.ai_conn.recv()

            pct_win = int(probability * 100)

            logger.debug(f"We had a {pct_win}% chance of winning.")
            logger.debug(f"Training Loss: {loss}.")

        if self.config.generate_predictions_img:
            predictions_img = None
            for disc_id, _, _, _ in users_in_game:
                if commands_util.ADMIN_DISC_ID == disc_id:
                    predictions_img = api_util.create_predictions_timeline_image()
                    break

            if predictions_img is not None:
                await self.send_predictions_timeline_image(predictions_img, guild_id)

    def user_is_registered(self, summ_name: str) -> bool:
        for _, names, _ in self.database.summoners:
            if summ_name in names:
                return True
        return False

    async def add_user(self, summ_name: str, discord_id: int, guild_id: int) -> str:
        if self.user_is_registered(summ_name):
            return "User with that summoner name is already registered."
        summ_id = self.riot_api.get_summoner_id(summ_name.replace(" ", "%20"))
        if summ_id is None:
            return f"Error: Invalid summoner name {self.get_emoji_by_name('PepeHands')}"
        success, status = self.database.add_user(summ_name, summ_id, discord_id)
        if success:
            users_in_voice = self.get_users_in_voice()
            for guild_id in users_in_voice:
                for disc_id, _, _ in users_in_voice[guild_id]:
                    if discord_id == disc_id: # User is already in voice channel.
                        await self.user_joined_voice(disc_id, guild_id)
                        break
        return status

    def get_game_start(self, guild_id):
        return self.game_monitor.game_start.get(guild_id)

    def get_active_game(self, guild_id):
        return self.game_monitor.active_game.get(guild_id)

    def get_users_in_game(self, guild_id):
        return self.game_monitor.users_in_game.get(guild_id)

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

        nicknames = []
        for disc_id, _, _ in self.database.summoners:
            member = self.get_member_safe(disc_id, guild_id)
            name = "Unnamed" if member is None else member.display_name
            nicknames.append(name)

        return nicknames

    async def get_discord_avatar(self, discord_id=None, size=64):
        default_avatar = "app/static/img/questionmark.png"
        users_to_search = ([x[0] for x in self.database.summoners]
                           if discord_id is None
                           else [discord_id])

        avatar_paths = []
        for disc_id in users_to_search:
            member = self.get_member_safe(disc_id)
            if member is None:
                avatar_paths.append(default_avatar)
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

            avatar_paths.append(path)

        return avatar_paths if discord_id is None else avatar_paths[0]

    def get_discord_id(self, nickname, guild_id=api_util.MAIN_GUILD_ID, exact_match=True):
        matches = []
        for guild in self.guilds:
            if guild.id == guild_id:
                for member in guild.members:
                    for attribute in (member.nick, member.display_name, member.name):
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

        guild_names = []
        for guild in guilds:
            if (guild.id in api_util.GUILD_IDS and
                    ((guild_id is None) or (guild.id == guild_id))
               ):
                guild_names.append(guild.name)

        if guild_names == []:
            logger.warning(f"get_guild_name: Could not find name of guild with ID '{guild_id}'")
            return None

        return guild_names if guild_id is None else guild_names[0]

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
        users_in_voice = {guild_id: [] for guild_id in api_util.GUILD_IDS}
        for guild in self.guilds:
            if guild.id in api_util.GUILD_IDS:
                for channel in guild.voice_channels:
                    members_in_voice = channel.members
                    for member in members_in_voice:
                        user_info = self.database.summoner_from_discord_id(member.id)
                        if user_info is not None:
                            users_in_voice[guild.id].append(user_info)

        return users_in_voice

    def get_ai_prediction(self, guild_id):
        if self.ai_conn is not None and guild_id in self.game_monitor.users_in_game:
            input_data = shape_predict_data(
                self.database, self.riot_api, self.config, self.game_monitor.users_in_game[guild_id]
            )
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

        user_data = self.database.discord_id_from_summoner(name, exact_match=False)
        if user_data is None: # Summoner name gave no result, try Discord name.
            return self.get_discord_id(name, guild_id, exact_match=False)

        return user_data[0]

    def insert_emotes(self, text):
        """
        Finds all occurences of '{emote_some_emote}' in the given string and replaces it with
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

    def resolve_bets(
        self,
        game_info: list[tuple],
        intfar: int,
        intfar_reason: str,
        doinks: list[int],
        guild_id: int
    ):
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
        game_won = game_info[0][1]["gameWon"]
        tokens_name = self.config.betting_tokens
        tokens_gained = (
            self.config.betting_tokens_for_win
            if game_won
            else self.config.betting_tokens_for_loss
        )

        clash_multiplier = 1

        # Check if we are playing clash. If so, points are worth more.
        if self.riot_api.is_clash(self.game_monitor.active_game[guild_id]["queue_id"]):
            clash_multiplier = self.config.clash_multiplier
            tokens_gained *= clash_multiplier

        game_desc = "Game won!" if game_won else "Game lost."
        response = (
            "=" * 38 +
            f"\n{game_desc} Everybody gains **{tokens_gained}** {tokens_name}."
        )
        response_bets = "**\n--- Results of bets made that game ---**\n"
        max_tokens_holder = self.database.get_max_tokens_details()[1]

        any_bets = False # Bool to indicate whether any bets were made.
        for disc_id, _, _ in self.database.summoners:
            user_in_game = False # See if the user corresponding to 'disc_id' was in-game.
            for user_data in self.game_monitor.users_in_game.get(guild_id, []):
                if disc_id == user_data[0]:
                    user_in_game = True
                    break

            gain_for_user = 0
            if user_in_game: # If current user was in-game, they gain tokens for playing.
                gain_for_user = tokens_gained
                if disc_id in doinks: # If user was awarded doinks, they get more tokens.
                    number_of_doinks = len(list(filter(lambda x: x == "1", doinks[disc_id])))
                    gain_for_user += (self.config.betting_tokens_for_doinks * number_of_doinks)
    
                self.betting_handler.award_tokens_for_playing(disc_id, gain_for_user)

            # Get list of active bets for the current user.
            bets_made = self.database.get_bets(True, disc_id, guild_id)
            balance_before = self.database.get_token_balance(disc_id)
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
                    bet_game_data = (
                        self.game_monitor.active_game[guild_id]["id"],
                        intfar,
                        intfar_reason,
                        doinks,
                        game_info,
                        clash_multiplier
                    ) 
                    bet_success, payout = self.betting_handler.resolve_bet(
                        disc_id,
                        bet_ids,
                        amounts,
                        bet_timestamp,
                        events,
                        targets,
                        bet_game_data
                    )

                    response_bets += " - "
                    total_cost = 0 # Track total cost of the current bet.
                    for index, (amount, event, target) in enumerate(zip(amounts, events, targets)):
                        person = None
                        if target is not None:
                            person = self.get_discord_nick(target, guild_id)

                        bet_desc = bets.get_dynamic_bet_desc(event, person)

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

        new_max_tokens_holder = self.database.get_max_tokens_details()[1]
        if new_max_tokens_holder != max_tokens_holder: # See if user now has most tokens after winning.
            max_tokens_name = self.get_discord_nick(new_max_tokens_holder, guild_id)

            # This person now has the most tokens of all users!
            response_bets += f"{max_tokens_name} now has the most {tokens_name} of everyone! "
            response_bets += "***HAIL TO THE KING, BABY!!!*** :crown:\n"

        if any_bets:
            response += response_bets

        return response, max_tokens_holder, new_max_tokens_holder

    async def play_event_sounds(self, intfar: int, doinks: list[int], guild_id: int):
        """
        Play potential Int-Far and Doinks sounds after a game has finished.

        :param intfar:      Discord ID of the person that is Int-Far (or None)
        :param doinks:      List of Discord IDs of people who got doinks
        :param guild_id:    ID of the Discord server where the game took place
        """
        users_in_voice = self.get_users_in_voice()
        voice_state = None

        # Check if any users from the game are in a voice channel.
        for user_data in self.game_monitor.users_in_game[guild_id]:
            for voice_user_data in users_in_voice[guild_id]:
                if user_data[0] == voice_user_data[0]:
                    # Get voice state for member in voice chat.
                    member = self.get_member_safe(user_data[0], guild_id)
                    if member is None:
                        continue

                    voice_state = member.voice
                    break

        if voice_state is not None:
            # One or more users from the game is in a voice channel.
            sounds_to_play = []

            # Add Int-Far sound to queue (if it exists).
            intfar_sound = self.database.get_event_sound(intfar, "intfar")
            if intfar_sound is not None:
                sounds_to_play.append(intfar_sound)

            # Add each doinks sound to queue (if any exist).
            for disc_id in doinks:
                doinks_sound = self.database.get_event_sound(disc_id, "doinks")
                if doinks_sound is not None:
                    sounds_to_play.append(doinks_sound)

            await self.audio_handler.play_sound(voice_state, sounds_to_play)

    def get_beaten_records_msg(
        self,
        best_records: list[tuple],
        worst_records: list[tuple],
        guild_id: int
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
                stat_index = api_util.STAT_COMMANDS.index(stat)
                stat_fmt = api_util.round_digits(value)
                stat_name_fmt = stat.replace('_', ' ')
                readable_stat = f"{api_util.STAT_QUANTITY_DESC[stat_index][index]} {stat_name_fmt}"
                name = self.get_mention_str(disc_id, guild_id)
                prev_name = self.get_discord_nick(prev_id, guild_id)
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

    def get_big_doinks_msg(self, doinks: dict[list[tuple]], guild_id: int):
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
                user_str = f"{prefix}{self.get_mention_str(disc_id, guild_id)} was insane that game! "
                user_str += f"He is awarded {len(doinks[disc_id])} " + "{emote_Doinks} for "
                any_mentions = True

            for (count, (stat_index, stat_value)) in enumerate(doinks[disc_id]):
                prefix = " *and* " if count > 0 else ""
                user_str += prefix + get_doinks_flavor_text(stat_index, stat_value)
            mentions_str += user_str

            multiplier = 1
            if self.riot_api.is_clash(self.game_monitor.active_game[guild_id]["queue_id"]):
                # Doinks are worth 5x more during clash
                multiplier = self.config.clash_multiplier

            points = self.config.betting_tokens_for_doinks * len(doinks[disc_id]) * multiplier
            tokens_name = self.config.betting_tokens
            mentions_str += f"\nHe is also given **{points}** bonus {tokens_name} "
            mentions_str += "for being great {emote_swell}"

        return None if not any_mentions else mentions_str

    def get_honorable_mentions_msg(self, mentions: dict[list[tuple]], guild_id: int):
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
        mentions_str = "Honorable mentions goes out to:\n"
        any_mentions = False

        for disc_id in mentions:
            user_str = ""

            if mentions[disc_id] != []:
                prefix = "\n" if any_mentions else ""
                user_str = f"{prefix}- {self.get_mention_str(disc_id, guild_id)} for "
                any_mentions = True

            for (count, (stat_index, stat_value)) in enumerate(mentions[disc_id]):
                prefix = " **and** " if count > 0 else ""
                user_str += prefix + get_honorable_mentions_flavor_text(stat_index, stat_value)

            mentions_str += user_str

        return None if not any_mentions else mentions_str

    def get_cool_stats_msg(self, cool_stats: dict[list[tuple]], guild_id: int):
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
                user_str = f"{prefix}{self.get_mention_str(disc_id, guild_id)} "
                any_stats = True

            for (count, (stat_index, stat_value)) in enumerate(cool_stats[disc_id]):
                prefix = " **and** " if count > 0 else ""
                user_str += prefix + get_cool_stat_flavor_text(stat_index, stat_value)

            stats_str += user_str

        return None if not any_stats else self.insert_emotes(stats_str)

    def get_cool_timeline_msg(self, timeline_mentions: list[tuple], guild_id: int):
        """
        Return a message describing interesting events that happened during the game
        that relate to the Riot timeline API. This includes whether the team came
        back from a large gold deficit or threw a huge gold lead.

        :param timeline_mentions:   List of info about interesting timeline related
                                    events that happened during the game
        :param guild_id:            ID of the Discord server where the game took place
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
                event_str += f"{self.get_mention_str(disc_id, guild_id)} "
            else: # Team-wide event.
                event_str += "We "

            event_str += get_timeline_events_flavor_text(event_index, value)

            timeline_str += event_str

        return None if timeline_mentions == [] else self.insert_emotes(timeline_str)

    def get_intfar_streak_msg(
        self,
        intfar_id: int,
        guild_id: int,
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
        current_nick = self.get_discord_nick(intfar_id, guild_id)
        current_mention = self.get_mention_str(intfar_id, guild_id)
        prev_mention = self.get_mention_str(prev_intfar, guild_id)

        if intfar_id is None:
            if intfar_streak > 1: # No one was Int-Far this game, but a streak was active.
                for user_data in self.game_monitor.users_in_game.get(guild_id, []):
                    if user_data[0] == prev_intfar:
                        return (
                            f"{prev_mention} has redeemed himself! " +
                            f"His Int-Far streak of {intfar_streak} has been broken. " +
                            "Well done, my son {emote_uwu}"
                        )
            return None

        if intfar_id == prev_intfar: # Current Int-Far was also previous Int-Far.
            return get_intfar_streak_flavor_text(current_mention, intfar_streak + 1)

        if intfar_streak > 1: # Previous Int-Far has broken his streak!
            return (f"Thanks to {current_nick}, the {intfar_streak} games Int-Far streak of " +
                    f"{prev_mention} is over " + "{emote_woahpikachu}")
    
        return None

    def get_ifotm_lead_msg(self, intfar_id: int, guild_id: int):
        """
        Return a message describing whether the person being Int-Far
        is now in the lead for Int-Far Of The Month (IFOTM)
        after acquring their new Int-Far award.

        :param intfar_id:   Discord ID of the person who is Int-Far
        :param guild_id:    ID of the Discord server where the game took place
        """
        mention_str = self.get_mention_str(intfar_id, guild_id)
        message = f"{mention_str} has now taken the lead for Int-Far of the Month " + "{emote_nazi}"
        intfar_details = self.database.get_intfars_of_the_month()
        monthly_games, monthly_intfars = self.database.get_intfar_stats(intfar_id, monthly=True)

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
        disc_id: int,
        guild_id: int,
        reason: str,
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
        mention_str = self.get_mention_str(disc_id, guild_id)
        if mention_str is None:
            logger.warning(f"Int-Far Discord nickname could not be found! Discord ID: {disc_id}")
            mention_str = f"Unknown (w/ discord ID '{disc_id}')"

        if reason is None:
            logger.warning("Int-Far reason was None!")
            reason = "being really, really bad" # Generic reason, if None was given

        message = ties_msg
        message += get_intfar_flavor_text(mention_str, reason)

        # Get message detailing whether current Int-Far is on an Int-Far streak,
        # or whether them getting Int-Far broken another persons streak
        streak_msg = self.get_intfar_streak_msg(disc_id, guild_id, intfar_streak, prev_intfar)
        if streak_msg is not None:
            message += "\n" + streak_msg

        # Get message describing whether current Int-Far is now Int-Far Of The Month
        ifotm_lead_msg = self.get_ifotm_lead_msg(disc_id, guild_id)
        if ifotm_lead_msg is not None:
            message += "\n" + ifotm_lead_msg

        return self.insert_emotes(message)

    def get_intfar_data(
        self,
        relevant_stats: list[tuple],
        filtered_stats: list[tuple],
        guild_id: int
    ):
        """
        Determines whether a person in a finished game should be crowned Int-Far.
        Returns who the Int-Far is (if any), what conditions they met, and a message
        describing why they got Int-Far.

        :param relevant_stats:  List containing a tuple of (discord_id, game_stats)
                                for each player on our team (registered or not)
        :param filtered_stats:  Same as 'relevant_stats', but filtered to remove
                                any players that are not registered with Int-Far
        :param guild_id:        ID of the Discord server where the game took place
        """
        reason_keys = ["kda", "deaths", "kp", "visionScore"]
        reason_ids = ["0", "0", "0", "0"]

        (
            final_intfar,
            final_intfar_data,
            ties,
            ties_msg
        ) = award_qualifiers.get_intfar(relevant_stats, filtered_stats, self.config)

        intfar_streak, prev_intfar = self.database.get_current_intfar_streak()

        if final_intfar is not None: # Send int-far message.
            reason = ""

            # Go through the criteria the chosen Int-Far met and list them in a readable format.
            for (count, (reason_index, stat_value)) in enumerate(final_intfar_data):
                key = reason_keys[reason_index]
                reason_text = get_reason_flavor_text(api_util.round_digits(stat_value), key)
                reason_ids[reason_index] = "1"

                if count > 0:
                    reason_text = " **AND** " + reason_text
                reason += reason_text

            full_ties_msg = ""
            if ties:
                logger.info("There are Int-Far ties.")
                logger.info(ties_msg)

                full_ties_msg = "There are Int-Far ties! " + ties_msg + "\n"

            response = self.get_intfar_message(
                final_intfar, guild_id, reason, full_ties_msg, intfar_streak, prev_intfar
            )

        else: # No one was bad enough to be Int-Far.
            logger.info("No Int-Far that game!")
            response = get_no_intfar_flavor_text()
            honorable_mentions = award_qualifiers.get_honorable_mentions(filtered_stats, self.config)
            honorable_mention_text = self.get_honorable_mentions_msg(honorable_mentions, guild_id)

            if honorable_mention_text is not None:
                response += "\n" + honorable_mention_text

            # Get info about a potential Int-Far streak the person is currently on.
            streak_msg = self.get_intfar_streak_msg(None, guild_id, intfar_streak, prev_intfar)
            if streak_msg is not None:
                response += "\n" + streak_msg

            response = self.insert_emotes(response)

        reasons_str = "".join(reason_ids)
        if reasons_str == "0000":
            reasons_str = None

        return final_intfar, reasons_str, response

    def get_doinks_data(self, filtered_stats: list[tuple[int, dict]], guild_id: int):
        """
        Gets data about the people who earned doinks in a game.
        Returns a message describing who (if any) got doinks and why.

        :param filtered_stats:  List containing a tuple of (discord_id, game_stats)
                                for each Int-Far registered player on our team
        :param guild_id:        ID of the Discord server where the game took place
        """
        doinks_mentions, doinks = award_qualifiers.get_big_doinks(filtered_stats)
        redeemed_text = self.get_big_doinks_msg(doinks_mentions, guild_id)

        return doinks, redeemed_text

    def get_cool_stats_data(self, filtered_stats: list[tuple[int, dict]], guild_id: int):
        stat_mentions = award_qualifiers.get_cool_stats(filtered_stats, self.config)
        cool_stats_msg = self.get_cool_stats_msg(stat_mentions, guild_id)

        return cool_stats_msg

    def get_cool_timeline_data(
        self,
        filtered_stats: list[tuple[int, dict]],
        timeline_data: dict,
        guild_id: int
    ):
        filtered_timeline = game_stats.get_filtered_timeline_stats(filtered_stats, timeline_data)
        timeline_mentions = award_qualifiers.get_cool_timeline_events(filtered_timeline, self.config)
        cool_events_msg = self.get_cool_timeline_msg(timeline_mentions, guild_id)

        return cool_events_msg

    def get_win_loss_streak_data(self, filtered_stats: list[tuple[int, dict]], guild_id: int):
        """
        Get message describing the win/loss streak of all players in game
        after it has concluded. Returns None if the streak is less than 3.

        :param filtered_stats:  List containing a tuple of (discord_id, game_stats)
                                for each Int-Far registered player on our team
        :param guild_id:        ID of the Discord server where the game took place
        """
        mentions_by_streak = {}
        broken_streaks = {}
        game_won = filtered_stats[0][1]["gameWon"]

        for disc_id, _ in filtered_stats:
            current_streak = self.database.get_current_win_or_loss_streak(disc_id, game_won)
            prev_streak = self.database.get_current_win_or_loss_streak(disc_id, not game_won) - 1

            if current_streak >= self.config.stats_min_win_loss_streak:
                # We are currently on a win/loss streak
                mention = self.get_mention_str(disc_id, guild_id)
                streak_list = mentions_by_streak.get(current_streak, [])
                streak_list.append(mention)
                mentions_by_streak[current_streak] = streak_list

                mentions_by_streak[current_streak] = streak_list
            elif prev_streak >= self.config.stats_min_win_loss_streak:
                # We broke a win/loss streak
                mention = self.get_mention_str(disc_id, guild_id)
                streak_list = broken_streaks.get(prev_streak, [])
                streak_list.append(mention)
                broken_streaks[prev_streak] = streak_list

        response = ""

        for streak in mentions_by_streak:
            mention_list = mentions_by_streak[streak]

            response += "\n" + get_game_streak_flavor_text(
                self.config.stats_min_win_loss_streak,
                mention_list,
                streak,
                game_won
            )

        for streak in broken_streaks:
            mention_list = broken_streaks[streak]

            response += "\n" + get_broken_game_streak_flavor_text(
                mention_list,
                streak,
                game_won
            )

        if response != "":
            response = "=" * 38 + response

        return self.insert_emotes(response) if response != "" else None

    def save_stats(
        self,
        filtered_stats: list[tuple[int, dict]],
        intfar_id: int,
        intfar_reason: str,
        doinks: dict[int, str],
        guild_id: int
    ):
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
            best_records, worst_records = self.database.record_stats(
                intfar_id, intfar_reason, doinks,
                self.game_monitor.active_game[guild_id]["id"], filtered_stats,
                self.game_monitor.users_in_game.get(guild_id), guild_id
            )

            # Create backup of database
            self.database.create_backup()
            logger.info("Game over! Stats were saved succesfully.")

            return best_records, worst_records

        except DBException as exception:
            # Log error along with relevant variables.
            game_id = self.game_monitor.active_game.get(guild_id, {}).get("id")
            logger.bind(
                game_id=game_id,
                intfar_id=intfar_id,
                intfar_reason=intfar_reason,
                doinks=doinks,
                guild_id=guild_id
            ).exception("Game stats could not be saved!")

            raise exception

    async def user_joined_voice(self, disc_id: int, guild_id: int, poll_immediately=False):
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
        summoner_info = self.database.summoner_from_discord_id(disc_id)

        if summoner_info is not None:
            users_in_voice = self.get_users_in_voice()[guild_id]
            self.game_monitor.set_users_in_voice_channels(users_in_voice, guild_id)
            logger.debug("Summoner joined voice: " + summoner_info[1][0])

            if self.game_monitor.should_poll(guild_id):
                logger.info("Polling is now active!")
                self.game_monitor.polling_active[guild_id] = True
                asyncio.create_task(
                    self.game_monitor.poll_for_game_start(guild_id, guild_name, poll_immediately)
                )

            logger.info(f"Active users in {guild_name}: {len(users_in_voice)}")

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
        self.game_monitor.set_users_in_voice_channels(users_in_voice, guild_id)
        if self.game_monitor.should_stop_polling(guild_id):
            self.game_monitor.stop_polling(guild_id)

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

    async def reset_monthly_intfar_roles(self, guild):
        """
        When a new year has started, we remove Int-Far of the Month roles
        from all users who got them the previous year.
        """
        for month in range(12):
            month_name = api_util.MONTH_NAMES[month]
            role_name = f"Int-Far of the Month - {month_name}"

            for role in guild.roles:
                if role.name == role_name:
                    for member in role.members:
                        logger.info(f"Removing {role.name} from {member.name}.")
                        await member.remove_roles(role)

    async def assign_monthly_intfar_role(self, month, winner_ids):
        nibs_guild = None
        for guild in self.guilds:
            if guild.id == api_util.MAIN_GUILD_ID:
                nibs_guild = guild
                break

        prev_month = month - 1 if month != 1 else 12

        if prev_month == 1: # Prev month was January, reset previous years IFOTM roles.
            await self.reset_monthly_intfar_roles(nibs_guild)

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
        role_name = f"Int-Far of the Month - {month_name}"

        role = None
        for guild_role in nibs_guild.roles:
            # Check if role already exists.
            if guild_role.name == role_name:
                role = guild_role
                break

        if role is None:
            role = await nibs_guild.create_role(name=role_name, colour=color)

        for intfar_id in winner_ids:
            member = nibs_guild.get_member(intfar_id)
            if member is not None:
                await member.add_roles(role)
            else:
                logger.bind(intfar_id=intfar_id).error("Int-Far to add badge to was None!")

    async def declare_monthly_intfar(self, monthly_monitor):
        month = monthly_monitor.time_at_announcement.month
        prev_month = month - 1 if month != 1 else 12
        month_name = api_util.MONTH_NAMES[prev_month-1]

        intfar_data = self.database.get_intfars_of_the_month()

        if intfar_data == []:
            # No one has played enough games to quality for IFOTM this month
            response = (
                f"No one has played a minimum of {self.config.ifotm_min_games} games "
                "this month, so no Int-Far of the Month will be crowned "
                f"for {month_name}. Dead game, I guess :("
            )
            await self.channels_to_write[api_util.MAIN_GUILD_ID].send(response)
            return

        intro_desc = get_ifotm_flavor_text(month) + "\n\n"
        intro_desc += f"Int-Far of the month for {month_name} is...\n"
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
        current_month = monthly_monitor.time_at_announcement.month
        winners = [tupl[0] for tupl in intfar_data[:num_winners]]

        await self.assign_monthly_intfar_role(current_month, winners)

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

        dt_now = datetime.now(ifotm_monitor.cph_timezone)
        duration = api_util.format_duration(dt_now, ifotm_monitor.time_at_announcement)
        logger.info(f"Time until then: {duration}")

        curr_day = dt_now.day

        time_to_sleep = 30
        while not ifotm_monitor.should_announce():
            new_day = datetime.now(ifotm_monitor.cph_timezone).day
            if new_day != curr_day:
                # Download latest information from Riot API.
                self.riot_api.get_latest_data()
                curr_day = new_day

            await asyncio.sleep(time_to_sleep)

        await self.declare_monthly_intfar(ifotm_monitor)

        await asyncio.sleep(3600) # Sleep for an hour before resetting.
        asyncio.create_task(self.polling_loop())

    async def send_error_msg(self, guild_id):
        """
        This method is called whenenver a critical error occurs.
        It causes the bot to post an error message to the channel, pinging me to fix it.
        """
        mention_me = self.get_mention_str(commands_util.ADMIN_DISC_ID, guild_id)
        message = "Oh frick, It appears I've crashed {emote_nat_really_fine} "
        message += f"{mention_me}, come and fix me!!! " + "{emote_angry_gual}"
        await self.channels_to_write[guild_id].send(self.insert_emotes(message))

    async def get_all_messages(self, guild_id):
        counter = 0
        with open("all_messages.txt", "w", encoding="utf-8") as fp:
            async for message in self.channels_to_write[guild_id].history(limit=None, oldest_first=True):
                if message.author.id == self.user.id:
                    fp.write(str(message.created_at.timestamp()) + " - " + message.content + "\n")
                    counter += 1
                    if counter % 100 == 0:
                        print(f"Saved {counter} messages.", flush=True)
        print("Done writing messages!", flush=True)

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
                        await self.user_joined_voice(member.id, guild.id, True)

                for text_channel in guild.text_channels:
                    # Find the channel to write in for each guild.
                    if text_channel.id in CHANNEL_IDS and self.config.env == "production":
                        self.channels_to_write[guild.id] = text_channel
                        break

            elif guild.id == api_util.MY_GUILD_ID and self.config.env == "dev":
                CHANNEL_IDS.append(guild.text_channels[0].id)
                self.channels_to_write[guild.id] = guild.text_channels[0]

        # Call any potential listeners on the 'onready' event
        for (callback, args) in self.event_listeners.get("onready", []):
            callback(*args)

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

    async def on_raw_reaction_add(self, react_info):
        seconds_max = 60 * 60 * 12
        messages_to_remove = []

        # Clean up old messages.
        for message_id in self.pagination_data:
            created_at = self.pagination_data[message_id]["message"].created_at
            if time() - created_at.timestamp() > seconds_max:
                messages_to_remove.append(message_id)

        for message_id in messages_to_remove:
            del self.pagination_data[message_id]

        message_id = react_info.message_id
        if (
            react_info.event_type == "REACTION_ADD"
            and react_info.member != self.user
            and message_id in self.pagination_data 
            and react_info.emoji.name in ("▶", "◀")
            and self.pagination_data[message_id]["message"].created_at
        ):
            message_data = self.pagination_data[message_id]
            reaction_next = react_info.emoji.name == "▶"
            new_chunk = message_data["chunk"] + 1 if reaction_next else message_data["chunk"] - 1
            await self.paginate(
                message_data["message"].channel, message_data["data"],
                new_chunk, message_data["lines"], message_data["header"],
                message_data["footer"], message_data["message"]
            )

    async def send_dm(self, text, disc_id):
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

def run_client(config, database, betting_handler, riot_api, audio_handler, shop_handler, ai_pipe, main_pipe, flask_pipe):
    client = DiscordClient(
        config, database, betting_handler, riot_api, audio_handler,
        shop_handler, ai_pipe=ai_pipe, main_pipe=main_pipe, flask_pipe=flask_pipe
    )
    client.run(config.discord_token)
