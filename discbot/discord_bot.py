import random
import asyncio
from io import BytesIO
from threading import Thread
from time import time
from math import ceil
from traceback import print_exc
from datetime import datetime

import requests
import discord
from discord.errors import NotFound, DiscordException, HTTPException, Forbidden

from discbot.montly_intfar import MonthlyIntfar
from discbot.app_listener import listen_for_request
from discbot import commands
from discbot.commands.meta import handle_usage_msg
from api import game_stats, bets, award_qualifiers
from api.database import DBException
import discbot.commands.util as commands_util
import api.util as api_util
from ai.data import shape_predict_data

MY_GUILD_ID = 512363920044982272
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

STREAK_FLAVORS = api_util.load_flavor_texts("streak")

def get_intfar_flavor_text(nickname, reason):
    flavor_text = INTFAR_FLAVOR_TEXTS[random.randint(0, len(INTFAR_FLAVOR_TEXTS)-1)]
    return flavor_text.replace("{nickname}", nickname).replace("{reason}", reason)

def get_no_intfar_flavor_text():
    return NO_INTFAR_FLAVOR_TEXTS[random.randint(0, len(NO_INTFAR_FLAVOR_TEXTS)-1)]

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
    return flavor_text.replace("{" + reason + "}", f"**{value}**")

def get_honorable_mentions_flavor_text(index, value):
    flavor_values = HONORABLE_MENTIONS[index]
    flavor_text = flavor_values[random.randint(0, len(flavor_values)-1)]
    return flavor_text.replace("{value}", f"**{value}**")

def get_cool_stat_flavor_text(index, value):
    flavor_values = COOL_STATS[index]
    flavor_text = flavor_values[random.randint(0, len(flavor_values)-1)]
    return flavor_text.replace("{value}", f"**{value}**")

def get_doinks_flavor_text(index, value):
    flavor_values = DOINKS_FLAVORS[index]

    flavor_text = flavor_values[random.randint(0, len(flavor_values)-1)]
    if value is None:
        return flavor_text
    return flavor_text.replace("{value}", f"**{value}**")

def get_streak_flavor_text(nickname, streak):
    index = streak - 2 if streak - 2 < len(STREAK_FLAVORS) else len(STREAK_FLAVORS) - 1
    return STREAK_FLAVORS[index].replace("{nickname}", nickname).replace("{streak}", str(streak))

class DiscordClient(discord.Client):
    def __init__(self, config, database, betting_handler, riot_api, audio_handler, shop_handler, **kwargs):
        super().__init__(
            intents=discord.Intents(
                members=True,
                voice_states=True,
                guilds=True,
                emojis=True,
                reactions=True,
                guild_messages=True
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
        self.pagination_data = {}
        self.cached_avatars = {}
        self.users_in_game = {}
        self.active_game = {}
        self.game_start = {}
        self.channels_to_write = {}
        self.polling_active = {}
        self.test_guild = None
        self.initialized = False
        self.last_message_time = {}
        self.last_command_time = {}
        self.command_timeout_lengths = {
            "play": 5
        }
        self.user_timeout_length = {}
        self.time_initialized = datetime.now()

    def send_game_update(self, endpoint, data):
        try:
            return requests.post(f"http://mhooge.com:5000/intfar/{endpoint}", data=data)
        except requests.exceptions.RequestException as e:
            self.config.log("Error ignored in online_monitor: " + str(e))

    async def send_predictions_timeline_image(self, image, guild_id):
        channel = self.channels_to_write[guild_id]
        with BytesIO() as b_io:
            image.save(b_io, format="PNG")
            b_io.seek(0)
            file = discord.File(b_io, filename="predictions.png")
            await channel.send("Odds of winning throughout the game:", file=file)

    async def poll_for_game_end(self, guild_id):
        """
        This method is called periodically when a game is active.
        When this method detects that the game is no longer active,
        it calls the 'game_over' method, which determines who is the Int-Far,
        who to give doinks to, etc.
        """
        self.config.log("Polling for game end...")
        time_slept = 0
        sleep_per_loop = 0.2
        try:
            while time_slept < self.config.status_interval_ingame:
                await asyncio.sleep(sleep_per_loop)
                time_slept += sleep_per_loop
        except KeyboardInterrupt:
            return

        game_status = self.check_game_status(guild_id)
        if game_status == 2: # Game is over.
            try:
                self.config.log("GAME OVER!!")
                self.config.log(f"Active game: {self.active_game[guild_id]['id']}")
                game_info = self.riot_api.get_game_details(
                    self.active_game[guild_id]["id"], tries=2
                )

                retry = 0
                retries = 4
                time_to_sleep = 15
                while game_info is None and retry < retries:
                    self.config.log(
                        f"Game info is None! Retrying in {time_to_sleep} secs...",
                        self.config.log_warning
                    )
                    await asyncio.sleep(time_to_sleep)
                    game_info = self.riot_api.get_game_details(
                        self.active_game[guild_id]["id"]
                    )
                    retry += 1

                if game_info is None: # Game info is still None after 3 retries.
                    self.config.log(
                        "Game info is STILL None after 3 retries!", self.config.log_error
                    )
                    raise ValueError("Game info is None!")

                if self.database.game_exists(game_info["gameId"]):
                    self.config.log(
                        "We triggered end of game stuff again... Strange!",
                        self.config.log_warning
                    )

                elif len(self.users_in_game[guild_id]) == 1:
                    response = "Only one person in that game. "
                    response += "no Int-Far will be crowned "
                    response += "and no stats will be saved."
                    await self.channels_to_write[guild_id].send(response)
                # Gamemode was URF. Don't save stats then.
                elif self.riot_api.is_urf(game_info["gameMode"]):
                    response = "That was an URF game {emote_poggers} "
                    response += "no Int-Far will be crowned "
                    response += "and no stats will be saved."
                    await self.channels_to_write[guild_id].send(self.insert_emotes(response))
                # Game is not on summoners rift. Same deal.
                elif not self.riot_api.map_is_sr(game_info["mapId"]):
                    response = "That game was not on Summoner's Rift "
                    response += "{emote_woahpikachu} no Int-Far will be crowned "
                    response += "and no stats will be saved."
                    await self.channels_to_write[guild_id].send(self.insert_emotes(response))

                # Game was too short to count. Probably a remake.
                elif game_info["gameDuration"] < self.config.min_game_minutes * 60:
                    response = (
                        "That game lasted less than 5 minutes " +
                        "{emote_zinking} assuming it was a remake. " +
                        "No stats are saved."
                    )
                    await self.channels_to_write[guild_id].send(self.insert_emotes(response))

                else:
                    await self.game_over(game_info, guild_id)

                req_data = {
                    "secret": self.config.discord_token,
                    "guild_id": guild_id, "game_id": self.active_game[guild_id]["id"]
                }
                self.send_game_update("game_ended", req_data)

                self.active_game[guild_id] = None
                self.game_start[guild_id] = None
                del self.users_in_game[guild_id] # Reset the list of users who are in a game.
                asyncio.create_task(self.poll_for_game_start(guild_id))
            except Exception as e:
                self.config.log("Exception after game was over!!!", self.config.log_error)
                await self.send_error_msg(guild_id)
                with open("errorlog.txt", "a", encoding="UTF-8") as fp:
                    print_exc(file=fp)
                raise e
        elif game_status == 0:
            await self.poll_for_game_end(guild_id)

    async def game_over(self, game_info, guild_id):
        # Print who was in the game, for sanity checks.
        self.config.log(f"Users in game before: {self.users_in_game.get(guild_id)}")
        try: # Get formatted stats that are relevant for the players in the game.
            filtered_stats, users_in_game = game_stats.get_filtered_stats(
                self.database.summoners, self.users_in_game.get(guild_id), game_info
            )
        except ValueError as exc:
            # Game data was not formatted correctly for some reason (Rito pls).
            self.config.log(
                "Game data is not well formed! Exception: " + str(exc),
                self.config.log_error
            )
            await self.send_error_msg(guild_id)
            with open("errorlog.txt", "a", encoding="utf-8") as fp:
                print_exc(file=fp)
            raise exc

        self.users_in_game[guild_id] = users_in_game
        self.config.log(f"Users in game after: {users_in_game}")

        self.active_game[guild_id]["queue_id"] = game_info["queueId"]

        if self.riot_api.is_clash(self.active_game[guild_id]["queue_id"]):
            multiplier = self.config.clash_multiplier
            await self.channels_to_write[guild_id].send(
                "**>>>>> THAT WAS A CLASH GAME! REWARDS ARE WORTH " +
                f"{multiplier} TIMES AS MUCH!!! <<<<<**"
            )

        intfar, intfar_reason, response = self.get_intfar_data(filtered_stats, guild_id)
        doinks, doinks_response = self.get_doinks_data(filtered_stats, guild_id)

        if doinks_response is not None:
            response += "\n" + self.insert_emotes(doinks_response)

        await self.channels_to_write[guild_id].send(response)

        await asyncio.sleep(1)
        response, max_tokens_id, new_max_tokens_id = self.resolve_bets(
            filtered_stats, intfar, intfar_reason, doinks, guild_id
        )

        if max_tokens_id != new_max_tokens_id:
            await self.assign_top_tokens_role(max_tokens_id, new_max_tokens_id)

        cool_stats_response = self.get_cool_stats_data(filtered_stats, guild_id)
        if cool_stats_response is not None:
            response = cool_stats_response + "\n" + response

        best_records, worst_records = self.save_stats(
            filtered_stats, intfar, intfar_reason, doinks, guild_id
        )

        if best_records != [] or worst_records != []:
            records_response = self.get_beaten_records_msg(
                best_records, worst_records, guild_id
            )
            response = records_response + "\n" + response

        await self.channels_to_write[guild_id].send(response)

        await self.play_event_sounds(guild_id, intfar, doinks)

        if self.ai_conn is not None:
            self.config.log("Training AI Model with new game data.")
            train_data = shape_predict_data(
                self.database, self.riot_api, self.config, users_in_game
            )
            self.ai_conn.send(
                ("train", [train_data, filtered_stats[0][1]["gameWon"]])
            )
            loss, probability = self.ai_conn.recv()
            pct_win = int(probability * 100)
            self.config.log(f"We had a {pct_win}% chance of winning.")
            self.config.log(f"Training Loss: {loss}.")

        if self.config.generate_predictions_img:
            predictions_img = None
            for disc_id, _, _, _ in users_in_game:
                if commands_util.ADMIN_DISC_ID == disc_id:
                    predictions_img = api_util.create_predictions_timeline_image()
                    break

            if predictions_img is not None:
                await self.send_predictions_timeline_image(predictions_img, guild_id)

    async def poll_for_game_start(self, guild_id, immediately=False):
        guild_name = self.get_guild_name(guild_id)
        self.polling_active[guild_id] = True
        time_slept = 0
        sleep_per_loop = 0.2
        self.config.log(f"People are active in {guild_name}! Polling for games...")
        if not immediately:
            try:
                while time_slept < self.config.status_interval_dormant:
                    if not self.polling_is_active(guild_id): # Stop if people leave voice channels.
                        self.polling_active[guild_id] = False
                        self.config.log(f"Polling is no longer active in {guild_name}.")
                        return
                    await asyncio.sleep(sleep_per_loop)
                    time_slept += sleep_per_loop
            except KeyboardInterrupt:
                self.polling_active[guild_id] = False
                return

        game_status = self.check_game_status(guild_id)

        if game_status == 1: # Game has started.
            req_data = {
                "secret": self.config.discord_token,
                "guild_id": guild_id
            }
            req_data.update(self.active_game[guild_id])
            self.send_game_update("game_started", req_data)
            self.config.log(f"Game is now active in {guild_name}, polling for game end...")
            await self.poll_for_game_end(guild_id)
        elif game_status == 0: # Sleep for a bit and check game status again.
            await self.poll_for_game_start(guild_id)

    def user_is_registered(self, summ_name):
        for _, names, _ in self.database.summoners:
            if summ_name in names:
                return True
        return False

    async def add_user(self, summ_name, discord_id, guild_id):
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

    def polling_is_active(self, guild_id):
        # We only check game statuses if there are two or more active users in a guild.
        return len(self.get_users_in_voice()[guild_id]) > 1

    def check_game_status(self, guild_id):
        active_game = None
        active_game_start = None
        game_ids = set()
        # First check if users are in the same game (or all are in no games).
        user_list = (
            self.get_users_in_voice()[guild_id]
            if self.users_in_game.get(guild_id) is None
            else self.users_in_game[guild_id]
        )
        users_in_current_game = []
        for user_data in user_list:
            disc_id = user_data[0]
            summ_names = user_data[1]
            summ_ids = user_data[2]
            game_for_summoner = None
            active_name = None
            active_id = None
            champ_id = None
            # Check if any of the summ_names/summ_ids for a given player is in a game.
            for summ_name, summ_id in zip(summ_names, summ_ids):
                game_data = self.riot_api.get_active_game(summ_id)
                if game_data is not None:
                    game_start = int(game_data["gameStartTime"]) / 1000
                    active_game_start = game_start
                    game_for_summoner = game_data
                    active_name = summ_name
                    active_id = summ_id
                    break
            if game_for_summoner is not None:
                game_ids.add(game_for_summoner["gameId"])
                champ_id = game_stats.get_player_stats(game_for_summoner, summ_ids)["championId"]
                users_in_current_game.append((disc_id, [active_name], [active_id], champ_id))
                active_game = game_for_summoner

        if len(game_ids) > 1: # People are in different games.
            return 0

        if active_game is not None and self.active_game.get(guild_id) is None:
            self.config.log(active_game_start)
            if active_game_start == 0:
                active_game_start = int(time())

            self.active_game[guild_id] = {
                "id": active_game["gameId"],
                "start": active_game_start,
                "map_id": active_game["mapId"],
                "map_name": self.riot_api.get_map_name(active_game["mapId"]),
                "game_mode": active_game["gameMode"],
                "game_guild_name": self.get_guild_name(guild_id)
            }

            self.game_start[guild_id] = active_game_start
            self.config.log(f"Game start: {datetime.fromtimestamp(self.game_start[guild_id])}")
            self.users_in_game[guild_id] = users_in_current_game
            return 1 # Game is now active.
        if active_game is None and self.active_game.get(guild_id) is not None:
            return 2 # Game is over.
        return 0

    def get_game_start(self, guild_id):
        return self.game_start.get(guild_id)

    def get_active_game(self, guild_id):
        return self.active_game.get(guild_id)

    def get_mention_str(self, disc_id, guild_id=api_util.MAIN_GUILD_ID):
        """
        Return a string that allows for @mention of the given user.
        """
        for guild in self.guilds:
            if guild.id == guild_id:
                for member in guild.members:
                    if member.id == disc_id:
                        return member.mention
        return None

    def get_member_safe(self, disc_id, guild_id=api_util.MAIN_GUILD_ID):
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

            key = f"{member.id}_{size}"

            caching_time = self.cached_avatars.get(key, 0)
            time_now = time()
            # We cache avatars for an hour.
            path = f"app/static/img/avatars/{member.id}_{size}.png"
            if time_now - caching_time > 3600:
                try:
                    await member.avatar_url_as(format="png", size=size).save(path)
                    self.cached_avatars[key] = time_now
                except (DiscordException, HTTPException, NotFound) as exc:
                    print(exc)
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
                return [emoji.url for emoji in guild.emojis]
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

    def try_get_user_data(self, name, guild_id):
        if name.startswith("<@"):
            start_index = 3 if name[2] == "!" else 2
            return int(name[start_index:-1])
        user_data = self.database.discord_id_from_summoner(name, exact_match=False)
        if user_data is None: # Summoner name gave no result, try Discord name.
            return self.get_discord_id(name, guild_id, exact_match=False)
        return user_data[0]

    def insert_emotes(self, text):
        """
        Finds all occurences of {emote_some_emote} in the given string and replaces it with
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
            emoji = self.get_emoji_by_name(emote)
            if emoji is None:
                emoji = "" # Replace with empty string if emoji could not be found.
            replaced = replaced.replace("{emote_" + emote + "}", emoji)
            emote_index = replaced.find("{emote_")
        return replaced

    async def assign_top_tokens_role(self, old_holder, new_holder):
        role_id = 750111830529146980
        nibs_guild = None
        for guild in self.guilds:
            if guild.id == api_util.MAIN_GUILD_ID:
                nibs_guild = guild
                break

        role = nibs_guild.get_role(role_id)

        old_head_honcho = nibs_guild.get_member(old_holder)
        await old_head_honcho.remove_roles(role)

        new_head_honcho = nibs_guild.get_member(new_holder)
        await new_head_honcho.add_roles(role)

    def resolve_bets(self, game_info, intfar, intfar_reason, doinks, guild_id):
        game_won = game_info[0][1]["gameWon"]
        tokens_name = self.config.betting_tokens
        tokens_gained = (self.config.betting_tokens_for_win
                         if game_won
                         else self.config.betting_tokens_for_loss)

        clash_multiplier = 1

        if self.riot_api.is_clash(self.active_game[guild_id]["queue_id"]):
            clash_multiplier = self.config.clash_multiplier
            tokens_gained *= clash_multiplier

        game_desc = "Game won!" if game_won else "Game lost."
        response = (
            "======================================" +
            f"\n{game_desc} Everybody gains **{tokens_gained}** {tokens_name}."
        )
        response_bets = "**\n--- Results of bets made that game ---**\n"
        max_tokens_holder = self.database.get_max_tokens_details()[1]

        any_bets = False # Bool to indicate whether any bets were made.
        for disc_id, _, _ in self.database.summoners:
            user_in_game = False # See if the user corresponding to 'disc_id' was in-game.
            for user_data in self.users_in_game.get(guild_id, []):
                if disc_id == user_data[0]:
                    user_in_game = True
                    break

            gain_for_user = 0
            if user_in_game: # If current user was in-game, he gains tokens for playing.
                gain_for_user = tokens_gained
                if disc_id in doinks: # If user was awarded doinks, he gets more tokens.
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
                    # Resolve current bet which the user made, marks it as won/lost in DB.
                    bet_success, payout = self.betting_handler.resolve_bet(
                        disc_id, bet_ids, amounts, events, bet_timestamp, targets,
                        (
                            self.active_game[guild_id]["id"], intfar,
                            intfar_reason, doinks, game_info, clash_multiplier
                        )
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
                if tokens_lost >= balance_before / 2: # Betting tokens was (at least) halved.
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
        if new_max_tokens_holder != max_tokens_holder:
            max_tokens_name = self.get_discord_nick(new_max_tokens_holder, guild_id)
            # This person now has the most tokens of all users!
            response_bets += f"{max_tokens_name} now has the most {tokens_name} of everyone! "
            response_bets += "***HAIL TO THE KING!!!***\n"

        if any_bets:
            response += response_bets

        return response, max_tokens_holder, new_max_tokens_holder

    async def play_event_sounds(self, guild_id, intfar, doinks):
        users_in_voice = self.get_users_in_voice()
        voice_state = None
        # Check if any users from the game are in a voice channel.
        for user_data in self.users_in_game[guild_id]:
            for voice_user_data in users_in_voice[guild_id]:
                if user_data[0] == voice_user_data[0]:
                    # Get voice state for member in voice chat.
                    member = self.get_member_safe(user_data[0], guild_id)
                    if member is None:
                        continue

                    voice_state = member.voice
                    break

        if voice_state is not None:
            sounds_to_play = []

            # Add Int-Far sound first (if it exists).
            intfar_sound = self.database.get_event_sound(intfar, "intfar")
            if intfar_sound is not None:
                sounds_to_play.append(intfar_sound)

            # Add each doinks sound if any exist.
            for disc_id in doinks:
                doinks_sound = self.database.get_event_sound(disc_id, "doinks")
                if doinks_sound is not None:
                    sounds_to_play.append(doinks_sound)

            await self.audio_handler.play_sound(voice_state, sounds_to_play)

    def get_beaten_records_msg(self, best_records, worst_records, guild_id):
        response = "======================================"
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

    def get_big_doinks_msg(self, doinks, guild_id):
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
            if self.riot_api.is_clash(self.active_game[guild_id]["queue_id"]):
                multiplier = self.config.clash_multiplier
            points = self.config.betting_tokens_for_doinks * len(doinks[disc_id]) * multiplier
            tokens_name = self.config.betting_tokens
            mentions_str += f"\nHe is also given **{points}** bonus {tokens_name} "
            mentions_str += "for being great {emote_swell}"

        return None if not any_mentions else mentions_str

    def get_honorable_mentions_msg(self, mentions, guild_id):
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

    def get_cool_stats_msg(self, cool_stats, guild_id):
        stats_str = "======================================\n"
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

    def get_streak_msg(self, intfar_id, guild_id, intfar_streak, prev_intfar):
        """
        Return a message describing the current Int-Far streak.
        This happens if someone ends his Int-Far streak, either by playing well,
        or by someone else getting Int-Far.
        It also describes whether someone is currently on an Int-Far streak.
        """
        current_nick = self.get_discord_nick(intfar_id, guild_id)
        current_mention = self.get_mention_str(intfar_id, guild_id)
        prev_mention = self.get_mention_str(prev_intfar, guild_id)
        if intfar_id is None:
            if intfar_streak > 1: # No one was Int-Far this game, but a streak was active.
                for user_data in self.users_in_game.get(guild_id, []):
                    if user_data[0] == prev_intfar:
                        return (f"{prev_mention} has redeemed himself! " +
                                f"His Int-Far streak of {intfar_streak} has been broken. " +
                                "Well done, my son {emote_uwu}")
            return None
        if intfar_id == prev_intfar: # Current Int-Far was also previous Int-Far.
            return get_streak_flavor_text(current_mention, intfar_streak + 1)
        if intfar_streak > 1: # Previous Int-Far has broken his streak!
            return (f"Thanks to {current_nick}, the {intfar_streak} games Int-Far streak of " +
                    f"{prev_mention} is over " + "{emote_woahpikachu}")
        return None

    def get_ifotm_lead_msg(self, intfar_id, guild_id):
        """
        Return a message describing whether the person being Int-Far is now
        in the lead for Int-Far Of The Month (IFOTM) after acquring their new Int-Far award.
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

    def get_intfar_message(self, disc_id, guild_id, reason, ties_msg, intfar_streak, prev_intfar):
        """
        Send Int-Far message to the appropriate Discord channel.
        """
        mention_str = self.get_mention_str(disc_id, guild_id)
        if mention_str is None:
            self.config.log(f"Int-Far Discord nickname could not be found! Discord ID: {disc_id}",
                            self.config.log_warning)
            mention_str = f"Unknown (w/ discord ID '{disc_id}')"

        if reason is None:
            self.config.log("Int-Far reason was None!", self.config.log_warning)
            reason = "being really, really bad"

        message = ties_msg
        message += get_intfar_flavor_text(mention_str, reason)

        streak_msg = self.get_streak_msg(disc_id, guild_id, intfar_streak, prev_intfar)
        if streak_msg is not None:
            message += "\n" + streak_msg

        ifotm_lead_msg = self.get_ifotm_lead_msg(disc_id, guild_id)
        if ifotm_lead_msg is not None:
            message += "\n" + ifotm_lead_msg

        return self.insert_emotes(message)

    def get_intfar_data(self, filtered_stats, guild_id):
        """
        Called when the currently active game is over.
        Determines if an Int-Far should be crowned and for what,
        and sends out a status message about the potential Int-Far (if there was one).
        Also saves worst/best stats for the current game.
        """
        reason_keys = ["kda", "deaths", "kp", "visionScore"]
        reason_ids = ["0", "0", "0", "0"]

        (final_intfar,
         final_intfar_data,
         ties, ties_msg) = award_qualifiers.get_intfar(filtered_stats, self.config)
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
                self.config.log("There are Int-Far ties.")
                self.config.log(ties_msg)
                full_ties_msg = "There are Int-Far ties! " + ties_msg + "\n"

            response = self.get_intfar_message(
                final_intfar, guild_id, reason, full_ties_msg, intfar_streak, prev_intfar
            )
        else: # No one was bad enough to be Int-Far.
            self.config.log("No Int-Far that game!")
            response = get_no_intfar_flavor_text()
            honorable_mentions = award_qualifiers.get_honorable_mentions(filtered_stats, self.config)
            honorable_mention_text = self.get_honorable_mentions_msg(honorable_mentions, guild_id)
            if honorable_mention_text is not None:
                response += "\n" + honorable_mention_text

            streak_msg = self.get_streak_msg(None, guild_id, intfar_streak, prev_intfar)
            if streak_msg is not None:
                response += "\n" + streak_msg

            response = self.insert_emotes(response)

        reasons_str = "".join(reason_ids)
        if reasons_str == "0000":
            reasons_str = None

        return final_intfar, reasons_str, response

    def get_doinks_data(self, filtered_stats, guild_id):
        doinks_mentions, doinks = award_qualifiers.get_big_doinks(filtered_stats)
        redeemed_text = self.get_big_doinks_msg(doinks_mentions, guild_id)

        return doinks, redeemed_text

    def get_cool_stats_data(self, filtered_stats, guild_id):
        stat_mentions = award_qualifiers.get_cool_stats(filtered_stats, self.config)
        redeemed_text = self.get_cool_stats_msg(stat_mentions, guild_id)

        return redeemed_text

    def save_stats(self, filtered_stats, intfar_id, intfar_reason, doinks, guild_id):
        if not self.config.testing:
            try: # Save stats.
                best_records, worst_records = self.database.record_stats(
                    intfar_id, intfar_reason, doinks,
                    self.active_game[guild_id]["id"], filtered_stats,
                    self.users_in_game.get(guild_id), guild_id
                )
                self.database.create_backup()
                self.config.log("Game over! Stats were saved succesfully.")
                return best_records, worst_records
            except DBException as exception:
                self.config.log("Game stats could not be saved!", self.config.log_error)
                self.config.log(exception)
                raise exception

    async def user_joined_voice(self, disc_id, guild_id, poll_immediately=False):
        guild_name = self.get_guild_name(guild_id)
        self.config.log(f"User joined voice in {guild_name}: {disc_id}")
        summoner_info = self.database.summoner_from_discord_id(disc_id)
        if summoner_info is not None:
            users_in_voice = self.get_users_in_voice()[guild_id]
            self.config.log("Summoner joined voice: " + summoner_info[1][0])
            if len(users_in_voice) > 1 and not self.polling_active.get(guild_id, False):
                self.config.log("Polling is now active!")
                self.polling_active[guild_id] = True
                asyncio.create_task(self.poll_for_game_start(guild_id, poll_immediately))
            self.config.log(f"Active users in {guild_name}: {len(users_in_voice)}")

    async def user_left_voice(self, disc_id, guild_id):
        guild_name = self.get_guild_name(guild_id)
        self.config.log(f"User left voice in {guild_name}: {disc_id}")
        users_in_voice = self.get_users_in_voice()[guild_id]
        if len(users_in_voice) < 2 and self.polling_active.get(guild_id, False):
            self.polling_active[guild_id] = False

    async def remove_intfar_role(self, intfar_id, role_id):
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
                        self.config.log(f"Removing {role.name} from {member.name}.")
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
                self.config.log("Int-Far to add badge to was None!", self.config.log_error)

    async def declare_monthly_intfar(self, monthly_monitor):
        month = monthly_monitor.time_at_announcement.month
        prev_month = month - 1 if month != 1 else 12
        month_name = api_util.MONTH_NAMES[prev_month-1]

        intfar_data = self.database.get_intfars_of_the_month()
        intfar_details = [(self.get_mention_str(disc_id), games, intfars, ratio)
                          for (disc_id, games, intfars, ratio) in intfar_data]
        intro_desc = f"THE RESULTS ARE IN!!! Int-Far of the month for {month_name} is...\n"
        intro_desc += "***DRUM ROLL***\n"
        desc, num_winners = monthly_monitor.get_description_and_winners(intfar_details)
        desc += ":clap: :clap: :clap: :clap: :clap: \n"
        desc += "{emote_uwu} {emote_sadbuttrue} {emote_smol_dave} "
        desc += "{emote_extra_creme} {emote_happy_nono} {emote_hairy_retard}"
        final_msg = intro_desc + self.insert_emotes(desc)
        await self.channels_to_write[api_util.MAIN_GUILD_ID].send(final_msg)

        # Assign Int-Far of the Month 'badge' (role) to the top Int-Far.
        current_month = monthly_monitor.time_at_announcement.month
        winners = [tupl[0] for tupl in intfar_data[:num_winners]]
        await self.assign_monthly_intfar_role(current_month, winners)

    async def sleep_until_monthly_infar(self):
        """
        Sleeps until the first of the next month (run in seperate thread).
        When the next month rolls around,
        this method announces the Int-Far of the previous month.
        """
        monitor = MonthlyIntfar(self.config.hour_of_ifotm_announce)
        self.config.log("Starting Int-Far-of-the-month monitor... ")
        format_time = monitor.time_at_announcement.strftime("%Y-%m-%d %H:%M:%S")
        self.config.log(f"Monthly Int-Far will be crowned at {format_time} UTC+1")
        dt_now = datetime.now(monitor.cph_timezone)
        duration = api_util.format_duration(dt_now, monitor.time_at_announcement)
        self.config.log(f"Time until then: {duration}")

        time_to_sleep = 30
        while not monitor.should_announce():
            await asyncio.sleep(time_to_sleep)

        await self.declare_monthly_intfar(monitor)

        await asyncio.sleep(3600) # Sleep for an hour before resetting.
        asyncio.create_task(self.sleep_until_monthly_infar())

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
            else self.channels_to_write[MY_GUILD_ID]
        )

    async def on_connect(self):
        self.config.log("Client connected")

    async def on_disconnect(self):
        self.config.log("Client disconnected...")

    async def on_ready(self):
        if self.initialized:
            self.config.log("Ready was called, but bot was already initialized... Weird stuff.")
            return

        await self.change_presence( # Change Discord activity.
            activity=discord.Activity(name="you inting in league",
                                      type=discord.ActivityType.watching)
        )
        self.config.log('Logged on as {0}!'.format(self.user))
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
            elif guild.id == MY_GUILD_ID and self.config.env == "dev":
                CHANNEL_IDS.append(guild.text_channels[0].id)
                self.channels_to_write[guild.id] = guild.text_channels[0]

        asyncio.create_task(self.sleep_until_monthly_infar())

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
        # Clean up old messages.
        for message_id in self.pagination_data:
            created_at = self.pagination_data[message_id]["message"].created_at
            if time() - created_at.timestamp() > seconds_max:
                del self.pagination_data[message_id]

        message_id = react_info.message_id
        if (react_info.event_type == "REACTION_ADD"
                and react_info.member != self.user
                and message_id in self.pagination_data 
                and react_info.emoji.name in ("▶", "◀")
                and self.pagination_data[message_id]["message"].created_at):
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
        if message.author == self.user: # Ignore message since it was sent by us (the bot).
            return

        if ((self.config.env == "dev" and message.guild.id != MY_GUILD_ID)
                or (self.config.env == "production" and message.guild.id not in api_util.GUILD_IDS)):
            return

        msg = message.content.strip()
        if msg.startswith("!"):
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
        await self.channels_to_write[int(guild_id)].send(message)

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
