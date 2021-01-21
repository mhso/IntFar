import random
import asyncio
from threading import Thread
from time import time
from traceback import print_exc
from datetime import datetime
import requests
import discord
from discord.errors import InvalidArgument, NotFound, DiscordException, HTTPException, Forbidden
from discbot.montly_intfar import MonthlyIntfar
from discbot.app_listener import listen_for_request
from api import game_stats, bets, award_qualifiers
from api.database import DBException
import api.util as api_util

DISCORD_SERVER_ID = 619073595561213953
MY_SERVER_ID = 512363920044982272
CHANNEL_ID = 730744358751567902
MY_DISC_ID = 267401734513491969

def load_flavor_texts(filename):
    path = f"flavor_texts/{filename}.txt"
    with open(path, "r", encoding="UTF-8") as f:
        return [x.replace("\n", "") for x in f.readlines()]

INTFAR_FLAVOR_TEXTS = load_flavor_texts("intfar")

NO_INTFAR_FLAVOR_TEXTS = load_flavor_texts("no_intfar")

MOST_DEATHS_FLAVORS = load_flavor_texts("most_deaths")

LOWEST_KDA_FLAVORS = load_flavor_texts("lowest_kda")

LOWEST_KP_FLAVORS = load_flavor_texts("lowest_kp")

LOWEST_VISION_FLAVORS = load_flavor_texts("lowest_vision")

MENTIONS_NO_PINKWARDS = load_flavor_texts("mentions_no_vision_ward")

MENTIONS_LOW_DAMAGE = load_flavor_texts("mentions_low_damage")

MENTIONS_LOW_CS_MIN = load_flavor_texts("mentions_low_cs_min")

MENTIONS_NO_EPIC_MONSTERS = load_flavor_texts("mentions_no_epic_monsters")

DOINKS_FLAVORS = load_flavor_texts("doinks")

STREAK_FLAVORS = load_flavor_texts("streak")

FLIRT_MESSAGES = {
    "english": [
        "Hey there... I'm a bot, why don't you get on top? {emote_hairy_retard}",
        "You like that, you fucking retard? {emote_cummies}",
        "You're goddamn right. I am your robot daddy :robot:",
        "You look so pretty when you get dicked in league {emote_kapepe}",
        "You might have heard of AI, but have you heard of DP? :first_quarter_moon_with_face:",
        "I'm not just nuts and screws... I can still screw and nut in you :nut_and_bolt:",
        "Even though you are inting so hard, it's not the hardest thing around... :joystick:",
        "How about I get over there and put my 1 in your 0? {emote_peberno}"
    ],
    "spanish": [
        "Hola ... Soy un bot, ¿por qué no te subes? {emote_hairy_retard}",
        "¿Te gusta eso, retrasado? {emote_cummies}",
        "Estás jodidamente en lo cierto. Soy tu robot papi :robot:",
        "Te ves tan bonita cuando te follan en la league {emote_kapepe}",
        "Es posible que haya oído hablar de la IA, pero ¿ha oído hablar de DP? :first_quarter_moon_with_face:",
        "No soy solo tuercas y tornillos ... todavía puedo atornillarte y atornillarte :nut_and_bolt:",
        "A pesar de que estás entrando con tanta fuerza, no es lo más difícil que hay .. :joystick:",
        "¿Qué tal si llego allí y pongo mi 1 en tu 0? {emote_peberno}"
    ]
}

VALID_COMMANDS = {
    "register": (
        "[summoner_name]",
        ("Sign up for the Int-Far™ Tracker™ " +
         "by providing your summoner name (fx. '!register imaqtpie').")
    ),
    "users": (None, "List all users who are currently signed up for the Int-Far™ Tracker™."),
    "help": (None, "Show the helper text."),
    "commands": (None, "Show this list of commands."),
    "stats": (None, "Show a list of available stat keywords to check"),
    "intfar": (
        "(person)",
        ("Show how many times you (if no summoner name is included), " +
         "or someone else, has been the Int-Far. '!intfar all' lists Int-Far stats for all users.")
    ),
    "intfar_relations": ("(person)", "Show who you (or someone else) int the most games with."),
    "intfar_criteria": (
        "[criteria]",
        ("List the things that need to happen for a person to get " +
         "Int-Far because of a specific criteria. Fx. '!intfar_criteria kda'.")
    ),
    "doinks": (
        "(person)",
        ("Show big doinks plays you (or someone else) did! " +
         "'!doinks all' lists all doinks stats for all users.")
    ),
    "doinks_relations": ("(person)", "Show who you (or someone else) get Big Doinks the most with."),
    "doinks_criteria": (None, "Show the different criterias needed for acquiring a doink."),
    "best": (
        "[stat] (person)",
        ("Show how many times you (or someone else) " +
         "were the best in the specific stat. " +
         "Fx. '!best kda' shows how many times you had the best KDA in a game." +
         "'!best [stat] all' shows what the best ever was for that stat, and who got it.")
    ),
    "worst": (
        "[stat] (person)",
        ("Show how many times you (or someone else) " +
         "were the worst at the specific stat." +
         "'!worst [stat] all' shows what the worst ever was for that stat, and who got it.")
    ),
    "uptime": (None, "Show for how long the bot has been up and running."),
    "status": (
        None,
        ("Show overall stats about how many games have been played, " +
         "how many people were Int-Far, etc.")
    ),
    "game": (
        "[person]", "See details about the league match the given person is in, if any."
    ),
    "bet": (
        "[event] [amount] (person)",
        ("Bet a specific amount of credits on one or more events happening " +
         "in the current or next game. Fx. '!bet game_win 100', '!bet intfar all slurp' " +
         "or '!bet game_win 20 & no_intfar 30' (bet on game win *AND* no Int-Far).")
    ),
    "cancel_bet": (
        "[event/ticket] (person)",
        ("Cancel a previously placed bet with the given parameters. " +
         "To cancel a multi-bet, provide the ticket generated for that bet. " +
         "A bet can not be cancelled when the game has started.")
    ),
    "give_tokens": (
        "[amount] [person]",
        "Give good-boi points to someone."
    ),
    "betting": (None, "Show information about betting, as well as list of possible events to bet on."),
    "active_bets": ("(person)", "See a list of your (or someone else's) active bets."),
    "bets": ("(person)", "See a list of all your (or someone else's) lifetime bets."),
    "betting_tokens" : ("(person)", "See how many betting tokens you (or someone else) has."),
    "bet_return": (
        "[event] (person)",
        "See the return award of a specific betting event (targetting 'person', if given)."
    ),
    "website": (None, "See information about the Int-Far website."),
    "website_profile": ("(person)", "Get a link to your (or someone else's) Int-Far profile."),
    "website_verify": (
        None,
        "Running this command will cause the bot to send you a secret link. " +
        "Opening this link verifies you on the Int-Far homepage and logs you in permanently."
    ),
    "report": ("[person]", "Report someone, f.x. if they are being a poon."),
    "reports": ("(person)", "See how many times someone (or yourself) has been reported.")
}

ALIASES = {
    "give_tokens": ["give"],
    "betting_tokens": ["gbp"]
}

CUTE_COMMANDS = {
    "intdaddy": "Flirt with the Int-Far.",
    "intpapi": "Flirt with the Int-Far in spanish."
}

ADMIN_COMMANDS = [
    "restart"
]

def cmd_equals(text, cmd):
    return text == cmd or (cmd in ALIASES and text in ALIASES[cmd])

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
    return flavor_text.replace("{" + reason + "}", value)

def get_honorable_mentions_flavor_text(index, value):
    flavor_values = []
    if index == 0:
        flavor_values = MENTIONS_NO_PINKWARDS
    elif index == 1:
        flavor_values = MENTIONS_LOW_DAMAGE
    elif index == 2:
        flavor_values = MENTIONS_LOW_CS_MIN
    elif index == 3:
        flavor_values = MENTIONS_NO_EPIC_MONSTERS
    flavor_text = flavor_values[random.randint(0, len(flavor_values)-1)]
    return flavor_text.replace("{value}", str(value))

def get_redeeming_flavor_text(index, value):
    flavor_text = DOINKS_FLAVORS[index]
    if value is None:
        return flavor_text
    return flavor_text.replace("{value}", str(value))

def get_streak_flavor_text(nickname, streak):
    index = streak - 2 if streak - 2 < len(STREAK_FLAVORS) else len(STREAK_FLAVORS) - 1
    return STREAK_FLAVORS[index].replace("{nickname}", nickname).replace("{streak}", str(streak))

class DiscordClient(discord.Client):
    def __init__(self, config, database, betting_handler, riot_api, **kwargs):
        super().__init__(
            intents=discord.Intents(members=True,
                                    voice_states=True,
                                    guilds=True,
                                    emojis=True,
                                    guild_messages=True)
        )
        self.config = config
        self.database = database
        self.riot_api = riot_api
        self.betting_handler = betting_handler
        self.main_conn = kwargs.get("main_pipe")
        self.flask_conn = kwargs.get("flask_pipe")
        self.cached_avatars = {}
        self.users_in_game = None
        self.active_game = None
        self.game_start = None
        self.channel_to_write = None
        self.test_guild = None
        self.initialized = False
        self.polling_active = False
        self.last_message_time = {}
        self.timeout_length = {}
        self.time_initialized = datetime.now()

    def send_game_update(self, endpoint, data):
        try:
            requests.post(f"http://mhooge.com:5000/intfar/{endpoint}", data=data)
        except requests.exceptions.RequestException as e:
            self.config.log("Error ignored in online_monitor: " + str(e))

    async def poll_for_game_end(self):
        """
        This method is called periodically when a game is active.
        When this method detects that the game is no longer active,
        it calls the 'declare_intfar' method, which determines who is the Int-Far.
        """
        self.config.log("Game is underway, polling for game end...")
        time_slept = 0
        sleep_per_loop = 0.5
        try:
            while time_slept < self.config.status_interval_ingame:
                await asyncio.sleep(sleep_per_loop)
                time_slept += sleep_per_loop
        except KeyboardInterrupt:
            return

        game_status = self.check_game_status()
        if game_status == 2: # Game is over.
            try:
                self.config.log("GAME OVER!!")
                self.config.log(f"Active game: {self.active_game['id']}")
                game_info = self.riot_api.get_game_details(self.active_game["id"], tries=2)

                if game_info is None:
                    self.config.log("Game info is None! Weird stuff.", self.config.log_error)
                    raise ValueError("Game info is None!")
                if self.database.game_exists(game_info["gameId"]):
                    self.config.log("We are triggered end of game stuff again... Strange!")
                    return
                if not self.riot_api.is_good_map(game_info["mapId"]):
                    response = "That game was not on Summoner's Rift "
                    response += "{emote_woahpikachu} no Int-Far will be crowned "
                    response += "and no stats will be saved."
                    await self.channel_to_write.send(self.insert_emotes(response))
                elif game_info["gameDuration"] < 5 * 60: # Game was less than 5 mins long.
                    response = (
                        "That game lasted less than 5 minutes " +
                        "{emote_zinking} assuming it was a remake."
                    )
                    await self.channel_to_write.send(self.insert_emotes(response))
                else:
                    self.config.log(f"Users in game before: {self.users_in_game}")
                    filtered_stats, self.users_in_game = game_stats.get_filtered_stats(
                        self.database, self.users_in_game, game_info
                    )
                    self.config.log(f"Users in game after: {self.users_in_game}")

                    self.active_game["queue_id"] = game_info["queueId"]

                    if self.riot_api.is_clash(self.active_game["queue_id"]):
                        multiplier = self.config.clash_multiplier
                        await self.channel_to_write.send(
                            "**>>>>> THAT WAS A CLASH GAME! REWARDS ARE WORTH " +
                            f"{multiplier} TIMES AS MUCH!!! <<<<<"
                        )

                    betting_data = await self.declare_intfar(filtered_stats)

                    if betting_data is not None:
                        intfar, intfar_reason, doinks = betting_data
                        await asyncio.sleep(1)
                        await self.resolve_bets(filtered_stats, intfar, intfar_reason, doinks)
                        await self.save_stats(filtered_stats, intfar, intfar_reason, doinks)

                self.active_game = None
                self.game_start = None
                self.users_in_game = None # Reset the list of users who are in a game.
                req_data = {
                    "secret": self.config.discord_token
                }
                self.send_game_update("game_ended", req_data)

                asyncio.create_task(self.poll_for_game_start())
            except Exception as e:
                self.config.log("Exception after game was over!!!", self.config.log_error)
                await self.send_error_msg()
                with open("errorlog.txt", "a", encoding="UTF-8") as fp:
                    print_exc(file=fp)
                raise e
        elif game_status == 0:
            await self.poll_for_game_end()

    async def poll_for_game_start(self, immediately=False):
        self.polling_active = True
        time_slept = 0
        sleep_per_loop = 0.5
        self.config.log("People are active in voice channels! Polling for games...")
        if not immediately:
            try:
                while time_slept < self.config.status_interval_dormant:
                    if not self.polling_is_active(): # Stop if people leave voice channels.
                        self.polling_active = False
                        self.config.log("Polling is no longer active.")
                        return
                    await asyncio.sleep(sleep_per_loop)
                    time_slept += sleep_per_loop
            except KeyboardInterrupt:
                self.polling_active = False
                return

        game_status = self.check_game_status()

        if game_status == 1: # Game has started.
            req_data = {
                "secret": self.config.discord_token
            }
            req_data.update(self.active_game)
            self.send_game_update("game_started", req_data)
            await self.poll_for_game_end()
        elif game_status == 0: # Sleep for 10 minutes and check game status again.
            await self.poll_for_game_start()

    def user_is_registered(self, summ_name):
        for _, names, _ in self.database.summoners:
            if summ_name in names:
                return True
        return False

    def add_user(self, summ_name, discord_id):
        if self.user_is_registered(summ_name):
            return "User with that summoner name is already registered."
        summ_id = self.riot_api.get_summoner_id(summ_name.replace(" ", "%20"))
        if summ_id is None:
            return f"Error: Invalid summoner name {self.get_emoji_by_name('PepeHands')}"
        success, status = self.database.add_user(summ_name, summ_id, discord_id)
        if success:
            users_in_voice = self.get_users_in_voice()
            for disc_id, _, _ in users_in_voice:
                if discord_id == disc_id: # User is already in voice channel.
                    self.user_joined_voice(disc_id)
                    break
        return status

    def polling_is_active(self): # We only check game statuses if there are two or more active users.
        return len(self.get_users_in_voice()) > 1

    def check_game_status(self):
        active_game = None
        active_game_start = None
        game_ids = set()
        # First check if users are in the same game (or all are in no games).
        user_list = self.get_users_in_voice() if self.users_in_game is None else self.users_in_game
        users_in_current_game = []
        for disc_id, summ_names, summ_ids in user_list:
            game_for_summoner = None
            active_name = None
            active_id = None
            # Check if any of the summ_names/summ_ids for a given player is in a game.
            for summ_name, summ_id in zip(summ_names, summ_ids):
                game_data = self.riot_api.get_active_game(summ_id)
                if game_data is not None:
                    game_start = int(game_data["gameStartTime"] / 1000)
                    active_game_start = game_start
                    game_for_summoner = game_data
                    active_name = summ_name
                    active_id = summ_id
                    break
            if game_for_summoner is not None:
                game_ids.add(game_for_summoner["gameId"])
                users_in_current_game.append((disc_id, [active_name], [active_id]))
                active_game = game_for_summoner

        if len(game_ids) > 1: # People are in different games.
            return 0

        if active_game is not None and self.active_game is None:
            self.config.log(active_game_start)
            if active_game_start == 0:
                active_game_start = int(time())

            self.active_game = {
                "id": active_game["gameId"],
                "start": active_game_start,
                "map_id": active_game["mapId"],
                "game_mode": active_game["gameMode"]
            }

            self.game_start = active_game_start
            self.config.log(f"Game start: {datetime.fromtimestamp(self.game_start)}")
            self.users_in_game = users_in_current_game
            return 1 # Game is now active.
        if active_game is None and self.active_game is not None: # The current game is over.
            return 2 # Game is over.
        return 0

    def get_game_start(self):
        return self.game_start

    def get_active_game(self):
        data = self.active_game
        if data is not None:
            data["map_name"] = self.riot_api.get_map_name(data["map_id"])

        return data

    def get_mention_str(self, disc_id):
        """
        Return a string that allows for @mention of the given user.
        """
        for guild in self.guilds:
            if guild.id == DISCORD_SERVER_ID:
                for member in guild.members:
                    if member.id == disc_id:
                        return member.mention
        return None

    def get_member_safe(self, disc_id):
        if isinstance(disc_id, str):
            disc_id = int(disc_id)

        server = self.get_guild(DISCORD_SERVER_ID)
        for member in server.members:
            if member.id == disc_id:
                return member
        return None

    def get_discord_nick(self, discord_id=None):
        """
        Return Discord nickname matching the given Discord ID.
        If 'discord_id' is None, returns all nicknames.
        """
        if discord_id is not None:
            member = self.get_member_safe(discord_id)
            return None if member is None else member.display_name

        nicknames = []
        for disc_id, _, _ in self.database.summoners:
            member = self.get_member_safe(disc_id)
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
                return default_avatar

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
                    return default_avatar

            avatar_paths.append(path)
        return avatar_paths if discord_id is None else avatar_paths[0]

    def get_discord_id(self, nickname):
        for guild in self.guilds:
            if guild.id == DISCORD_SERVER_ID:
                for member in guild.members:
                    if member.nick is not None and member.nick.lower() == nickname:
                        return member.id
                    if member.display_name is not None and member.display_name.lower() == nickname:
                        return member.id
                    if member.name is not None and member.name.lower() == nickname:
                        return member.id
        return None

    def get_all_emojis(self):
        for guild in self.guilds:
            if guild.id == DISCORD_SERVER_ID:
                return [emoji.url for emoji in guild.emojis]
        return None

    def get_emoji_by_name(self, emoji_name):
        """
        Return the ID of the emoji matching the given name.
        """
        for guild in self.guilds:
            if guild.id == DISCORD_SERVER_ID:
                for emoji in guild.emojis:
                    if emoji.name == emoji_name:
                        return str(emoji)
        return None

    def get_users_in_voice(self):
        users_in_voice = []
        for guild in self.guilds:
            if guild.id == DISCORD_SERVER_ID:
                for channel in guild.voice_channels:
                    members_in_voice = channel.members
                    for member in members_in_voice:
                        user_info = self.database.summoner_from_discord_id(member.id)
                        if user_info is not None:
                            users_in_voice.append(user_info)
        return users_in_voice

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
            if guild.id == DISCORD_SERVER_ID:
                nibs_guild = guild
                break

        role = nibs_guild.get_role(role_id)

        old_head_honcho = nibs_guild.get_member(old_holder)
        await old_head_honcho.remove_roles(role)

        new_head_honcho = nibs_guild.get_member(new_holder)
        await new_head_honcho.add_roles(role)

    async def resolve_bets(self, game_info, intfar, intfar_reason, doinks):
        game_won = game_info[0][1]["gameWon"]
        tokens_name = self.config.betting_tokens
        tokens_gained = (self.config.betting_tokens_for_win
                         if game_won
                         else self.config.betting_tokens_for_loss)

        clash_multiplier = 1

        if self.riot_api.is_clash(self.active_game["queue_id"]):
            clash_multiplier = self.config.clash_multiplier
            tokens_gained *= clash_multiplier

        game_desc = "Game won!" if game_won else "Game lost."
        response = f"\n{game_desc} Everybody gains {tokens_gained} {tokens_name}."
        response_bets = "\n**--- Results of bets made that game ---**\n"
        max_tokens_holder = self.database.get_max_tokens_details()[1]

        any_bets = False # Bool to indicate whether any bets were made.
        for disc_id, _, _ in self.database.summoners:
            user_in_game = False # See if the user corresponding to 'disc_id' was in-game.
            for in_game_id, _, _ in self.users_in_game:
                if disc_id == in_game_id:
                    user_in_game = True
                    break

            gain_for_user = 0
            if user_in_game: # If current user was in-game, he gains tokens for playing.
                gain_for_user = tokens_gained
                if disc_id in doinks: # If user was awarded doinks, he gets more tokens.
                    gain_for_user += self.config.betting_tokens_for_doinks
                self.betting_handler.award_tokens_for_playing(disc_id, gain_for_user)

            # Get list of active bets for the current user.
            bets_made = self.database.get_bets(True, disc_id)
            balance_before = self.database.get_token_balance(disc_id)
            tokens_earned = gain_for_user # Variable for tracking tokens gained for the user.
            tokens_lost = -1 # Variable for tracking tokens lost for the user.
            disc_name = self.get_discord_nick(disc_id)

            if bets_made is not None: # There are active bets for the current user.
                mention = self.get_mention_str(disc_id)
                if any_bets:
                    response_bets += "-----------------------------\n"
                response_bets += f"Result of bets {mention} made:\n"

                for bet_ids, _, amounts, events, targets, bet_timestamp, _, _ in bets_made:
                    any_bets = True
                    # Resolve current bet which the user made, marks it as won/lost in DB.
                    bet_success, payout = self.betting_handler.resolve_bet(
                        disc_id, bet_ids, amounts, events, bet_timestamp, targets,
                        (intfar, intfar_reason, doinks, game_info)
                    )

                    payout *= clash_multiplier

                    response_bets += " - "
                    total_cost = 0 # Track total cost of the current bet.
                    for index, (amount, event, target) in enumerate(zip(amounts, events, targets)):
                        person = None
                        if target is not None:
                            person = self.get_discord_nick(target)

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
            max_tokens_name = self.get_discord_nick(new_max_tokens_holder)
            # This person now has the most tokens of all users!
            response_bets += f"{max_tokens_name} now has the most {tokens_name} of everyone! "
            response_bets += "***HAIL TO THE KING!!!***\n"
            await self.assign_top_tokens_role(max_tokens_holder, new_max_tokens_holder)

        if any_bets:
            response += response_bets

        await self.channel_to_write.send(response)

    def get_big_doinks_msg(self, doinks):
        mentions_str = ""
        any_mentions = False
        for disc_id in doinks:
            user_str = ""
            if doinks[disc_id] != []:
                prefix = "\n" if any_mentions else ""
                user_str = f"{prefix} {self.get_mention_str(disc_id)} was insane that game! "
                intfars_removed = len(doinks[disc_id])
                user_str += f"He is awarded {intfars_removed} " + "{emote_Doinks} for "
                any_mentions = True

            for (count, (stat_index, stat_value)) in enumerate(doinks[disc_id]):
                prefix = " *and* " if count > 0 else ""
                user_str += prefix + get_redeeming_flavor_text(stat_index, stat_value)
            mentions_str += user_str

            multiplier = 1
            if self.riot_api.is_clash(self.active_game["queue_id"]):
                multiplier = self.config.clash_multiplier
            points = self.config.betting_tokens_for_doinks * multiplier
            tokens_name = self.config.betting_tokens
            mentions_str += f"\nHe is also given {points} bonus {tokens_name} "
            mentions_str += "for being great {emote_swell}"

        return None if not any_mentions else mentions_str

    def get_honorable_mentions_msg(self, mentions):
        mentions_str = "Honorable mentions goes out to:\n"
        any_mentions = False
        for disc_id in mentions:
            user_str = ""
            if mentions[disc_id] != []:
                prefix = "\n" if any_mentions else ""
                user_str = f"{prefix}- {self.get_mention_str(disc_id)} for "
                any_mentions = True

            for (count, (stat_index, stat_value)) in enumerate(mentions[disc_id]):
                prefix = " **and** " if count > 0 else ""
                user_str += prefix + get_honorable_mentions_flavor_text(stat_index, stat_value)
            mentions_str += user_str

        return None if not any_mentions else mentions_str

    def get_streak_msg(self, intfar_id, intfar_streak, prev_intfar):
        """
        Return a message describing the current Int-Far streak.
        This happens if someone ends his Int-Far streak, either by playing well,
        or by someone else getting Int-Far.
        It also describes whether someone is currently on an Int-Far streak.
        """
        current_nick = self.get_discord_nick(intfar_id)
        current_mention = self.get_mention_str(intfar_id)
        prev_mention = self.get_mention_str(prev_intfar)
        if intfar_id is None:
            if intfar_streak > 1: # No one was Int-Far this game, but a streak was active.
                for disc_id, _, _ in self.users_in_game:
                    if disc_id == prev_intfar:
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

    def get_ifotm_lead_msg(self, intfar_id):
        """
        Return a message describing whether the person being Int-Far is now
        in the lead for Int-Far Of The Month (IFOTM) after acquring their new Int-Far award.
        """
        mention_str = self.get_mention_str(intfar_id)
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

        new_pct = int((curr_intfars / curr_num_games) * 100)

        if new_pct > highest_intfar[3]:
            return message
        return None

    async def send_intfar_message(self, disc_id, reason, intfar_streak, prev_intfar):
        """
        Send Int-Far message to the #int-far-spam Discord channel.
        """
        mention_str = self.get_mention_str(disc_id)
        if mention_str is None:
            self.config.log(f"Int-Far Discord nickname could not be found! Discord ID: {disc_id}",
                            self.config.log_warning)
            mention_str = f"Unknown (w/ discord ID '{disc_id}')"
        if reason is None:
            self.config.log("Int-Far reason was None!", self.config.log_warning)
            reason = "being really, really bad"
        message = get_intfar_flavor_text(mention_str, reason)
        streak_msg = self.get_streak_msg(disc_id, intfar_streak, prev_intfar)
        if streak_msg is not None:
            message += "\n" + streak_msg
        ifotm_lead_msg = self.get_ifotm_lead_msg(disc_id)
        if ifotm_lead_msg is not None:
            message += "\n" + ifotm_lead_msg

        message += "\n==============================================="

        message = self.insert_emotes(message)
        await self.channel_to_write.send(message)

    async def declare_intfar(self, filtered_stats):
        """
        Called when the currently active game is over.
        Determines if an Int-Far should be crowned and for what,
        and sends out a status message about the potential Int-Far (if there was one).
        Also saves worst/best stats for the current game.
        """
        reason_keys = ["kda", "deaths", "kp", "visionScore"]
        reason_ids = ["0", "0", "0", "0"]

        doinks_mentions, doinks = award_qualifiers.get_big_doinks(filtered_stats)
        redeemed_text = self.get_big_doinks_msg(doinks_mentions)

        final_intfar, final_intfar_data = award_qualifiers.get_intfar(filtered_stats, self.config)
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

            if redeemed_text is not None:
                reason += "\n" + redeemed_text

            await self.send_intfar_message(final_intfar, reason, intfar_streak, prev_intfar)
        else: # No one was bad enough to be Int-Far.
            self.config.log("No Int-Far that game!")
            response = get_no_intfar_flavor_text()
            honorable_mentions = award_qualifiers.get_honorable_mentions(filtered_stats)
            honorable_mention_text = self.get_honorable_mentions_msg(honorable_mentions)
            if honorable_mention_text is not None:
                response += "\n" + honorable_mention_text
            if redeemed_text is not None:
                response += "\n" + redeemed_text

            streak_msg = self.get_streak_msg(None, intfar_streak, prev_intfar)
            if streak_msg is not None:
                response += "\n" + streak_msg

            response += "\n==============================================="
            await self.channel_to_write.send(self.insert_emotes(response))

        reasons_str = "".join(reason_ids)
        if reasons_str == "0000":
            reasons_str = None

        return final_intfar, reasons_str, doinks

    async def save_stats(self, filtered_stats, intfar_id, intfar_reason, doinks):
        if not self.config.testing:
            try: # Save stats.
                self.database.record_stats(intfar_id, intfar_reason, doinks,
                                           self.active_game["id"], filtered_stats,
                                           self.users_in_game)
                self.database.create_backup()
            except DBException as exception:
                self.config.log("Game stats could not be saved!", self.config.log_error)
                self.config.log(exception)
                raise exception

            self.config.log("Game over! Stats were saved succesfully.")

    async def user_joined_voice(self, disc_id, poll_immediately=False):
        self.config.log("User joined voice: " + str(disc_id))
        summoner_info = self.database.summoner_from_discord_id(disc_id)
        if summoner_info is not None:
            users_in_voice = self.get_users_in_voice()
            self.config.log("Summoner joined voice: " + summoner_info[1][0])
            if len(users_in_voice) > 1 and not self.polling_active:
                self.config.log("Polling is now active!")
                self.polling_active = True
                asyncio.create_task(self.poll_for_game_start(poll_immediately))
            self.config.log(f"Active users: {len(users_in_voice)}")

    async def user_left_voice(self, disc_id):
        self.config.log("User left voice: " + str(disc_id))
        users_in_voice = self.get_users_in_voice()
        if len(users_in_voice) < 2 and self.polling_active:
            self.polling_active = False

    async def remove_intfar_role(self, intfar_id, role_id):
        nibs_guild = None
        for guild in self.guilds: # Add all users currently in voice channels as active users.
            if guild.id == DISCORD_SERVER_ID:
                nibs_guild = guild
                break

        member = nibs_guild.get_member(intfar_id)
        role = nibs_guild.get_role(role_id)
        await member.remove_roles(role)

    async def assign_monthly_intfar_role(self, month, winner_ids):
        prev_month = month - 1 if month != 1 else 12

        # Colors:
        # Light blue, dark blue, cyan, mint,
        # light green, dark green, red, pink,
        # gold, yellow, orange, purple
        colors = [
            (0, 102, 204), (0, 0, 204), (0, 255, 255), (51, 255, 153),
            (0, 204, 0), (0, 51, 0), (255, 0, 0), (255, 102, 255),
            (153, 153, 0), (255, 255, 51), (255, 128, 0), (127, 0, 255)
        ]

        nibs_guild = None
        for guild in self.guilds: # Add all users currently in voice channels as active users.
            if guild.id == DISCORD_SERVER_ID:
                nibs_guild = guild
                break

        month_name = api_util.MONTH_NAMES[prev_month-1]
        color = discord.Color.from_rgb(*colors[prev_month-1])
        role_name = f"Int-Far of the Month - {month_name}"

        role = await nibs_guild.create_role(name=role_name, colour=color)

        for intfar_id in winner_ids:
            member = nibs_guild.get_member(intfar_id)
            if member is not None:
                await member.add_roles(role)
            else:
                self.config.log("Int-Far to add badge to was None!", self.config.log_error)

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

        time_to_sleep = 60
        while not monitor.should_announce():
            await asyncio.sleep(time_to_sleep)

        month = monitor.time_at_announcement.month
        prev_month = month - 1 if month != 1 else 12
        month_name = api_util.MONTH_NAMES[prev_month-1]

        intfar_data = self.database.get_intfars_of_the_month()
        intfar_details = [(self.get_mention_str(disc_id), games, intfars, ratio)
                          for (disc_id, games, intfars, ratio) in intfar_data]
        intro_desc = f"THE RESULTS ARE IN!!! Int-Far of the month for {month_name} is...\n"
        intro_desc += "***DRUM ROLL***\n"
        desc, num_winners = monitor.get_description_and_winners(intfar_details)
        desc += ":clap: :clap: :clap: :clap: :clap: \n"
        desc += "{emote_uwu} {emote_sadbuttrue} {emote_smol_dave} "
        desc += "{emote_extra_creme} {emote_happy_nono} {emote_hairy_retard}"
        final_msg = intro_desc + self.insert_emotes(desc)
        await self.channel_to_write.send(final_msg)

        # Assign Int-Far of the Month 'badge' (role) to the top Int-Far.
        current_month = monitor.time_at_announcement.month
        winners = [tupl[0] for tupl in intfar_data[:num_winners]]
        await self.assign_monthly_intfar_role(current_month, winners)

        await asyncio.sleep(3600) # Sleep for an hour before resetting.
        asyncio.create_task(self.sleep_until_monthly_infar())

    async def send_error_msg(self):
        """
        This method is called whenenver a critical error occurs.
        It causes the bot to post an error message to the channel, pinging me to fix it.
        """
        mention_me = self.get_mention_str(MY_DISC_ID)
        message = "Oh frick, It appears I've crashed {emote_nat_really_fine} "
        message += f"{mention_me}, come and fix me!!! " + "{emote_angry_gual}"
        await self.channel_to_write.send(self.insert_emotes(message))

    async def get_all_messages(self):
        counter = 0
        with open("all_messages.txt", "w", encoding="utf-8") as fp:
            async for message in self.channel_to_write.history(limit=None, oldest_first=True):
                if message.author.id == self.user.id:
                    fp.write(str(message.created_at.timestamp()) + " - " + message.content + "\n")
                    counter += 1
                    if counter % 100 == 0:
                        print(f"Saved {counter} messages.", flush=True)
        print("Done writing messages!", flush=True)

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
        for guild in self.guilds: # Add all users currently in voice channels as active users.
            if guild.id == DISCORD_SERVER_ID:
                await guild.chunk()
                for voice_channel in guild.voice_channels:
                    members_in_voice = voice_channel.members
                    for member in members_in_voice:
                        # Start polling for an active game
                        # if more than one user is active in voice.
                        await self.user_joined_voice(member.id, True)
                for text_channel in guild.text_channels:
                    # Find the 'int-far-spam' channel.
                    if text_channel.id == CHANNEL_ID and self.config.env == "production":
                        self.channel_to_write = text_channel
                        asyncio.create_task(self.sleep_until_monthly_infar())
                        break
            elif guild.id == MY_SERVER_ID and self.config.env == "dev":
                self.channel_to_write = guild.text_channels[0]
                await guild.chunk()

        if self.flask_conn is not None: # Listen for external commands from web page.
            event_loop = asyncio.get_event_loop()
            Thread(target=listen_for_request, args=(self, event_loop)).start()

    async def handle_helper_msg(self, message):
        """
        Write the helper message to Discord.
        """
        response = "I gotchu fam {emote_nazi}\n"
        response += "The Int-Far™ Tracker™ is a highly sophisticated bot "
        response += "that watches when people in this server plays League, "
        response += "and judges them harshly if they int too hard {emote_simp_but_closeup}\n"
        response += "- Write `!commands` to see a list of available commands, and their usages\n"
        response += "- Write `!stats` to see a list of available stats to check\n"
        response += "- Write `!betting` to see a list of events to bet on and how to do so"

        await message.channel.send(self.insert_emotes(response))

    async def handle_commands_msg(self, message):
        response = "**--- Valid commands, and their usages, are listed below ---**\n"
        commands = []
        for cmd, desc_tupl in VALID_COMMANDS.items():
            cmd_str = cmd
            for alias in ALIASES.get(cmd, []):
                cmd_str += f"/!{alias}"
            params, desc = desc_tupl
            params_str = "`-" if params is None else f"{params}` -"
            commands.append(f"`!{cmd_str} {params_str} {desc}")

        message_1 = response + "\n".join(commands[:14]) + "\n"
        message_2 = "\n".join(commands[14:])

        await message.channel.send(message_1)
        await asyncio.sleep(0.5)
        await message.channel.send(message_2)

    async def handle_stats_msg(self, message):
        valid_stats = ", ".join("'" + cmd + "'" for cmd in api_util.STAT_COMMANDS)
        response = "**--- Valid stats ---**\n```"
        response += valid_stats
        response += "\n```"

        await message.channel.send(response)

    async def handle_betting_msg(self, message):
        max_mins = bets.MAX_BETTING_THRESHOLD
        tokens_name = self.config.betting_tokens
        response = "Betting usage: `!bet [amount] [event] (person)`\n"
        response += "This places a bet on the next (or current) match.\n"
        response += f"`!bet all [event] (person)` bets **all** your {tokens_name} on an event!\n"
        response += f"You can place a bet during a game, but it has to be done before {max_mins} "
        response += "minutes. Betting during a game returns a lower reward, based on "
        response += "how much time has passed in the game.\n"
        response += "**--- List of available events to bet on ---**\n"
        for event_name, event_id in bets.BETTING_IDS.items():
            event_desc = bets.BETTING_DESC[event_id]
            response += f"`{event_name}` - Bet on {event_desc}\n"

        await message.channel.send(response)

    def get_uptime(self, dt_init):
        dt_now = datetime.now()
        return api_util.format_duration(dt_init, dt_now)

    async def handle_uptime_msg(self, message):
        uptime_formatted = self.get_uptime(self.time_initialized)
        await message.channel.send(f"Int-Far™ Tracker™ has been online for {uptime_formatted}")

    async def handle_status_msg(self, message):
        """
        Gather meta stats about this bot and write them to Discord.
        """
        response = f"**Uptime:** {self.get_uptime(self.time_initialized)}\n"

        (games, earliest_game, users, intfars,
         doinks, games_ratios, intfar_ratios,
         intfar_multi_ratios) = self.database.get_meta_stats()

        pct_intfar = int((intfars / games) * 100)
        pct_doinks = int((doinks / games) * 100)
        earliest_time = datetime.fromtimestamp(earliest_game).strftime("%Y-%m-%d")
        doinks_emote = self.insert_emotes("{emote_Doinks}")
        all_bets = self.database.get_bets(False)

        tokens_name = self.config.betting_tokens
        bets_won = 0
        total_amount = 0
        total_payout = 0
        highest_payout = 0
        highest_payout_user = None

        for disc_id in all_bets:
            bet_data = all_bets[disc_id]
            for _, _, amounts, events, targets, _, result, payout in bet_data:
                for amount, _, _ in zip(amounts, events, targets):
                    total_amount += amount

                if payout is not None:
                    if payout > highest_payout:
                        highest_payout = payout
                        highest_payout_user = disc_id

                    total_payout += payout

                if result == 1:
                    bets_won += 1

        pct_won = int((bets_won / len(all_bets)) * 100)
        highest_payout_name = self.get_discord_nick(highest_payout_user)

        response += f"--- Since {earliest_time} ---\n"
        response += f"- **{games}** games have been played\n"
        response += f"- **{users}** users have signed up\n"
        response += f"- **{intfars}** Int-Far awards have been given\n"
        response += f"- **{doinks}** {doinks_emote} have been earned\n"
        response += f"- **{len(all_bets)}** bets have been made (**{pct_won}%** was won)\n"
        response += f"- **{total_amount}** {tokens_name} have been spent on bets\n"
        response += f"- **{total_payout}** {tokens_name} have been won from bets\n"
        response += f"- **{highest_payout}** {tokens_name} was the biggest single win, by {highest_payout_name}\n"
        response += "--- Of all games played ---\n"
        response += f"- **{pct_intfar}%** resulted in someone being Int-Far\n"
        response += f"- **{pct_doinks}%** resulted in {doinks_emote} being handed out\n"
        response += f"- **{games_ratios[0]}%** were as a duo\n"
        response += f"- **{games_ratios[1]}%** were as a three-man\n"
        response += f"- **{games_ratios[2]}%** were as a four-man\n"
        response += f"- **{games_ratios[3]}%** were as a five-man stack\n"
        response += "--- When Int-Fars were earned ---\n"
        response += f"- **{intfar_ratios[0]}%** were for dying a ton\n"
        response += f"- **{intfar_ratios[1]}%** were for having an awful KDA\n"
        response += f"- **{intfar_ratios[2]}%** were for having a low KP\n"
        response += f"- **{intfar_ratios[3]}%** were for having a low vision score\n"
        response += f"- **{intfar_multi_ratios[0]}%** of Int-Fars met just one criteria\n"
        response += f"- **{intfar_multi_ratios[1]}%** of Int-Fars met two criterias\n"
        response += f"- **{intfar_multi_ratios[2]}%** of Int-Fars met three criterias\n"
        response += f"- **{intfar_multi_ratios[3]}%** of Int-Fars swept and met all four criterias"

        await message.channel.send(response)

    def try_get_user_data(self, name):
        if name.startswith("<@!"):
            return int(name[3:-1])
        user_data = self.database.discord_id_from_summoner(name)
        if user_data is None: # Summoner name gave no result, try Discord name.
            return self.get_discord_id(name)
        return user_data[0]

    async def handle_intfar_msg(self, message, target_id):
        current_month = api_util.current_month()

        def format_for_all(disc_id, monthly=False):
            person_to_check = self.get_discord_nick(disc_id)
            games_played, intfar_reason_ids = self.database.get_intfar_stats(disc_id, monthly)
            games_played, intfars, _, pct_intfar = api_util.organize_intfar_stats(games_played, intfar_reason_ids)
            msg = f"{person_to_check}: Int-Far **{intfars}** times "
            msg += f"**({pct_intfar}%** of {games_played} games) "
            msg = self.insert_emotes(msg)
            return msg, intfars, pct_intfar

        def format_for_single(disc_id):
            person_to_check = self.get_discord_nick(disc_id)
            games_played, intfar_reason_ids = self.database.get_intfar_stats(disc_id, False)
            games_played, intfars, intfar_counts, pct_intfar = api_util.organize_intfar_stats(games_played, intfar_reason_ids)
            intfars_of_the_month = self.database.get_intfars_of_the_month()
            user_is_ifotm = intfars_of_the_month != [] and intfars_of_the_month[0][0] == disc_id

            msg = f"{person_to_check} has been Int-Far **{intfars}** times "
            msg += "{emote_unlimited_chins}"
            if intfars > 0:
                monthly_games, monthly_infar_ids = self.database.get_intfar_stats(disc_id, True)
                monthly_games, monthly_intfars, _, pct_monthly = api_util.organize_intfar_stats(monthly_games, monthly_infar_ids)

                ratio_desc = "\n" + f"In total, he was Int-Far in **{pct_intfar}%** of his "
                ratio_desc += f"{games_played} games played.\n"
                ratio_desc += f"In {current_month}, he was Int-Far in **{monthly_intfars}** "
                ratio_desc += f"of his {monthly_games} games played (**{pct_monthly}%**)\n"

                reason_desc = "Int-Fars awarded so far:\n"
                for reason_id, reason in enumerate(api_util.INTFAR_REASONS):
                    reason_desc += f" - {reason}: **{intfar_counts[reason_id]}**\n"

                longest_streak = self.database.get_longest_intfar_streak(disc_id)
                streak_desc = f"His longest Int-Far streak was **{longest_streak}** "
                streak_desc += "games in a row " + "{emote_suk_a_hotdok}\n"

                longest_non_streak = self.database.get_longest_no_intfar_streak(disc_id)
                no_streak_desc = "His longest streak of *not* being Int-Far was "
                no_streak_desc += f"**{longest_non_streak}** games in a row " + "{emote_pog}\n"

                relations_data = self.get_intfar_relation_stats(disc_id)[0]
                most_intfars_nick = self.get_discord_nick(relations_data[0])
                relations_desc = f"He has inted the most when playing with {most_intfars_nick} "
                relations_desc += f"where he inted {relations_data[2]} games ({relations_data[3]}% "
                relations_desc += f"of {relations_data[1]} games)"
                relations_desc += "{emote_smol_gual}"

                msg += ratio_desc + reason_desc + streak_desc + no_streak_desc + relations_desc
                if user_is_ifotm:
                    msg += f"\n**{person_to_check} currently stands to be Int-Far of the Month "
                    msg += f"of {current_month}!**"
            msg = self.insert_emotes(msg)
            return msg

        response = ""
        if target_id is None: # Check intfar stats for everyone.
            messages_all_time = []
            messages_monthly = []
            for disc_id, _, _ in self.database.summoners:
                resp_str_all_time, intfars, pct_all_time = format_for_all(disc_id)
                resp_str_month, intfars_month, pct_month = format_for_all(disc_id, monthly=True)

                messages_all_time.append((resp_str_all_time, intfars, pct_all_time))
                messages_monthly.append((resp_str_month, intfars_month, pct_month))

            messages_all_time.sort(key=lambda x: (x[1], x[2]), reverse=True)
            messages_monthly.sort(key=lambda x: (x[1], x[2]), reverse=True)

            response = "**--- All time stats ---**\n"
            for data in messages_all_time:
                response += f"- {data[0]}\n"
            response += f"**--- Stats for {current_month} ---**\n"
            for data in messages_monthly:
                response += f"- {data[0]}\n"
        else: # Check intfar stats for a specific person.
            response = format_for_single(target_id)

        await message.channel.send(response)

    def get_intfar_relation_stats(self, target_id):
        data = []
        total_intfars = len(self.database.get_intfar_stats(target_id)[1])
        games_relations, intfars_relations = self.database.get_intfar_relations(target_id)
        for disc_id, total_games in games_relations.items():
            intfars = intfars_relations.get(disc_id, 0)
            data.append(
                (
                    disc_id, total_games, intfars, int((intfars / total_intfars) * 100),
                    int((intfars / total_games) * 100)
                )
            )

        return sorted(data, key=lambda x: x[2], reverse=True)

    async def handle_intfar_relations_msg(self, message, target_id):
        data = self.get_intfar_relation_stats(target_id)

        response = f"Breakdown of players {self.get_discord_nick(target_id)} has inted with:\n"
        for disc_id, total_games, intfars, intfar_ratio, games_ratio in data:
            nick = self.get_discord_nick(disc_id)
            response += f"- {nick}: **{intfars}** times (**{intfar_ratio}%**) "
            response += f"(**{games_ratio}%** of **{total_games}** games)\n"

        await message.channel.send(response)

    async def handle_doinks_msg(self, message, target_id):
        def get_doinks_stats(disc_id, expanded=True):
            person_to_check = self.get_discord_nick(disc_id)
            doinks_reason_ids = self.database.get_doinks_stats(disc_id)
            doinks_counts = api_util.organize_doinks_stats(doinks_reason_ids)
            msg = f"{person_to_check} has earned {len(doinks_reason_ids)} "
            msg += self.insert_emotes("{emote_Doinks}")
            if expanded and len(doinks_reason_ids) > 0:
                reason_desc = "\n" + "Big doinks awarded so far:"
                for reason_id, reason in enumerate(api_util.DOINKS_REASONS):
                    reason_desc += f"\n - {reason}: **{doinks_counts[reason_id]}**"

                msg += reason_desc

            return msg, len(doinks_reason_ids)

        response = ""
        if target_id is None: # Check doinks for everyone.
            messages = []
            for disc_id, _, _ in self.database.summoners:
                resp_str, intfars = get_doinks_stats(disc_id, expanded=False)
                messages.append((resp_str, intfars))
            messages.sort(key=lambda x: x[1], reverse=True)
            for resp_str, _ in messages:
                response += "- " + resp_str + "\n"
        else: # Check doinks for a specific person.
            response = get_doinks_stats(target_id)[0]

        await message.channel.send(response)

    def get_doinks_relation_stats(self, target_id):
        data = []
        games_relations, doinks_relations = self.database.get_doinks_relations(target_id)
        total_doinks = len(self.database.get_doinks_stats(target_id))
        for disc_id, total_games in games_relations.items():
            doinks = doinks_relations.get(disc_id, 0)
            data.append(
                (
                    disc_id, total_games, doinks, int((doinks / total_doinks) * 100),
                    int((doinks / total_games) * 100)
                )
            )

        return sorted(data, key=lambda x: x[2], reverse=True)

    async def handle_doinks_relations_msg(self, message, target_id):
        data = self.get_doinks_relation_stats(target_id)

        response = f"Breakdown of who {self.get_discord_nick(target_id)} has gotten Big Doinks with:\n"
        for disc_id, total_games, doinks, doinks_ratio, games_ratio in data:
            nick = self.get_discord_nick(disc_id)
            response += f"- {nick}: **{doinks}** times (**{doinks_ratio}%**) "
            response += f"(**{games_ratio}%** of **{total_games}** games)\n"

        await message.channel.send(response)

    async def handle_stat_msg(self, message, first_cmd, second_cmd, target_id):
        """
        Get the value of the requested stat for the requested player.
        F.x. '!best damage dumbledonger'.
        """
        if second_cmd in api_util.STAT_COMMANDS: # Check if the requested stat is a valid stat.
            stat = second_cmd
            stat_index = api_util.STAT_COMMANDS.index(stat)
            self.config.log(f"Stat requested: {first_cmd} {stat}")
            best = first_cmd == "best"
            quantity_type = 0 if best else 1
            # Check whether to find the max or min of some value, when returning
            # 'his most/lowest [stat] ever was ... Usually highest is best,
            # lowest is worse, except with deaths, where the opposite is the case.
            maximize = not ((stat != "deaths") ^ best)
            # Get a readable description, such as 'most deaths' or 'lowest kp'.
            readable_stat = api_util.STAT_QUANTITY_DESC[stat_index][quantity_type] + " " + stat

            response = ""
            check_all = target_id is None

            if check_all: # Get best/worst ever stat of everyone.
                (target_id,
                 min_or_max_value,
                 game_id) = self.database.get_most_extreme_stat(stat, best, maximize)
                recepient = self.get_discord_nick(target_id)
            else:
                (stat_count, # <- How many times the stat has occured.
                 min_or_max_value, # <- Highest/lowest occurance of the stat value.
                 game_id) = self.database.get_stat(stat + "_id", stat, best, target_id, maximize)
                recepient = self.get_discord_nick(target_id)

            game_summary = None
            if min_or_max_value is not None:
                min_or_max_value = api_util.round_digits(min_or_max_value)
                game_info = self.riot_api.get_game_details(game_id)
                summ_ids = self.database.summoner_from_discord_id(target_id)[2]
                game_summary = game_stats.get_finished_game_summary(game_info, summ_ids, self.riot_api)

            emote_to_use = "{emote_pog}" if best else "{emote_peberno}"

            if check_all:
                response = f"The {readable_stat} ever in a game was {min_or_max_value} "
                response += f"by {recepient} " + self.insert_emotes(emote_to_use) + "\n"
                response += f"He got this as {game_summary}"
            else:
                response = (f"{recepient} has gotten {readable_stat} in a game " +
                            f"{stat_count} times " + self.insert_emotes(emote_to_use) + "\n")
                if min_or_max_value is not None:
                    # The target user has gotten most/fewest of 'stat' in at least one game.
                    response += f"His {readable_stat} ever was "
                    response += f"{min_or_max_value} as {game_summary}"

            await message.channel.send(response)
        else:
            response = f"Not a valid stat: '{second_cmd}' "
            response += self.insert_emotes("{emote_carole_fucking_baskin}")
            await message.channel.send(response)

    async def handle_game_msg(self, message, target_id):
        summoner_ids = None
        target_name = self.get_discord_nick(target_id)

        for disc_id, _, summ_ids in self.database.summoners:
            if disc_id == target_id:
                summoner_ids = summ_ids
                break

        response = ""
        game_data = None
        active_summoner = None
        for summ_id in summoner_ids:
            game_data = self.riot_api.get_active_game(summ_id)
            if game_data is not None:
                active_summoner = summ_id
                break
            await asyncio.sleep(1)

        if game_data is not None:
            response = f"{target_name} is "
            response += game_stats.get_active_game_summary(game_data, active_summoner,
                                                           self.database.summoners, self.riot_api)
        else:
            response = f"{target_name} is not in a game at the moment "
            response += self.insert_emotes("{emote_simp_but_closeup}")

        await message.channel.send(response)

    async def handle_make_bet_msg(self, message, events, amounts, targets):
        if None in amounts or None in events:
            msg = "Usage: `!bet [event] [amount] (person)`"
            await message.channel.send(msg)
            return

        target_ids = []
        target_names = []
        for target_name in targets:
            target_id = None
            discord_name = None
            if target_name is not None: # Bet on a specific person doing a thing.
                if target_name == "me":
                    target_id = message.author.id
                else:
                    target_name = target_name.lower()
                    target_id = self.try_get_user_data(target_name.strip())
                    if target_id is None:
                        msg = "Error: Invalid summoner or Discord name "
                        msg += f"{self.get_emoji_by_name('PepeHands')}"
                        await message.channel.send(msg)
                        return
                discord_name = self.get_discord_nick(target_id)
            target_ids.append(target_id)
            target_names.append(discord_name)

        self.database.start_persistent_connection()
        response = self.betting_handler.place_bet(message.author.id, amounts,
                                                  self.game_start, events,
                                                  target_ids, target_names)[1]
        self.database.close_persistent_connection()

        await message.channel.send(response)

    async def handle_cancel_bet_msg(self, message, betting_event, target_id=None):
        target_name = None if target_id is None else self.get_discord_nick(target_id)

        response = self.betting_handler.cancel_bet(message.author.id, betting_event,
                                                   self.game_start, target_id, target_name)[1]
        await message.channel.send(response)

    async def handle_bet_return_msg(self, message, betting_event, target_id=None):
        target_name = None if target_id is None else self.get_discord_nick(target_id)

        response = self.betting_handler.get_bet_return_desc(betting_event, target_id, target_name)
        await message.channel.send(response)

    async def handle_give_tokens_msg(self, message, amount, target_id):
        target_name = self.get_discord_nick(target_id)

        max_tokens_before, max_tokens_holder = self.database.get_max_tokens_details()

        response = self.betting_handler.give_tokens(message.author.id, amount,
                                                    target_id, target_name)[1]

        balance_after = self.database.get_token_balance(target_id)

        if balance_after > max_tokens_before and target_id != max_tokens_holder:
            # This person now has the most tokens of all users!
            tokens_name = self.config.betting_tokens
            response += f"\n{target_name} now has the most {tokens_name} of everyone! "
            await self.assign_top_tokens_role(max_tokens_holder, target_id)

        await message.channel.send(response)

    async def handle_active_bets_msg(self, message, target_id):
        def get_bet_description(disc_id, single_person=True):
            active_bets = self.database.get_bets(True, disc_id)
            recepient = self.get_discord_nick(disc_id)

            response = ""
            if active_bets is None:
                if single_person:
                    response = f"{recepient} has no active bets."
                else:
                    response = None
            else:
                tokens_name = self.config.betting_tokens
                response = f"{recepient} has the following active bets:"
                for _, _, amounts, events, targets, _, ticket, _ in active_bets:
                    bets_str = "\n - "
                    total_cost = 0
                    if len(amounts) > 1:
                        bets_str += f"Multi-bet (ticket = {ticket}): "
                    for index, (amount, event, target) in enumerate(zip(amounts, events, targets)):
                        person = None
                        if target is not None:
                            person = self.get_discord_nick(target)

                        bet_desc = bets.get_dynamic_bet_desc(event, person)
                        bets_str += f"`{bet_desc}`"
                        if index != len(amounts) - 1:
                            bets_str += " & "

                        total_cost += amount

                    bets_str += f" for {total_cost} {tokens_name}"

                    response += bets_str

            return response

        response = ""

        if target_id is None:
            any_bet = False
            for disc_id, _, _ in self.database.summoners:
                bets_for_person = get_bet_description(disc_id, False)
                if bets_for_person is not None:
                    if any_bet:
                        bets_for_person = "\n" + bets_for_person
                    response += bets_for_person
                    any_bet = True
            if not any_bet:
                response = "No one has any active bets."
        else:
            response = get_bet_description(target_id)

        await message.channel.send(response)

    async def handle_all_bets_msg(self, message, target_id):
        all_bets = self.database.get_bets(False, target_id)
        tokens_name = self.config.betting_tokens
        bets_won = 0
        had_target = 0
        during_game = 0
        spent = 0
        most_often_event = 0
        max_event_count = 0
        winnings = 0
        event_counts = {x: 0 for x in bets.BETTING_DESC}

        for _, _, amounts, events, targets, game_time, result, payout in all_bets:
            for amount, event_id, target in zip(amounts, events, targets):
                spent += amount
                event_counts[event_id] += 1
                if event_counts[event_id] > max_event_count:
                    max_event_count = event_counts[event_id]
                    most_often_event = event_id
                if target is not None:
                    had_target += 1
            if result == 1:
                bets_won += 1
                winnings += payout if payout is not None else 0
            if game_time > 0:
                during_game += 1

        average_amount = int(spent / len(all_bets))
        pct_won = int((bets_won / len(all_bets)) * 100)
        pct_target = int((had_target / len(all_bets)) * 100)
        pct_during = int((during_game / len(all_bets)) * 100)
        event_desc = bets.BETTING_DESC[most_often_event]

        target_name = self.get_discord_nick(target_id)
        response = f"{target_name} has made a total of **{len(all_bets)}** bets.\n"
        response += f"- Bets won: **{bets_won} ({pct_won}%)**\n"
        response += f"- Average amount of {tokens_name} wagered: **{average_amount}**\n"
        response += f"- Total {tokens_name} wagered: **{spent}**\n"
        response += f"- Total {tokens_name} won: **{winnings}**\n"
        response += f"- Bet made the most often: `{event_desc}` (made **{max_event_count}** times)\n"
        response += f"- Bets that targeted a person: **{had_target} ({pct_target}%)**\n"
        response += f"- Bets made during a game: **{during_game} ({pct_during}%)**"

        await message.channel.send(response)

    async def handle_token_balance_msg(self, message, target_id):
        def get_token_balance(disc_id):
            name = self.get_discord_nick(disc_id)
            balance = self.database.get_token_balance(disc_id)
            return balance, name

        tokens_name = self.config.betting_tokens

        response = ""
        if target_id is None: # Get betting balance for all.
            balances = []
            for disc_id, _, _ in self.database.summoners:
                balance, name = get_token_balance(disc_id)
                balances.append((balance, name))

            balances.sort(key=lambda x: x[0], reverse=True)

            for balance, name in balances:
                response += f"\n{name} has **{api_util.format_tokens_amount(balance)}** {tokens_name}"
        else:
            balance, name = get_token_balance(target_id)
            response = f"\n{name} has **{api_util.format_tokens_amount(balance)}** {tokens_name}"

        await message.channel.send(response)

    async def handle_verify_msg(self, message):
        client_secret = self.database.get_client_secret(message.author.id)
        url = f"https://mhooge.com/intfar/verify/{client_secret}"
        response_dm = "Go to this link to verify yourself (totally not a virus):\n"
        response_dm += url + "\n"
        response_dm += "This will enable you to interact with the Int-Far bot from "
        response_dm += "the website, fx. to see stats or place bets.\n"
        response_dm += "To log in to a new device (phone fx.), simply use the above link again.\n"
        response_dm += "Don't show this link to anyone, or they will be able to log in as you!"

        mention = self.get_mention_str(message.author.id)
        response_server = (
            f"Psst, {mention}, I sent you a DM with a secret link, "
            "where you can sign up for the website {emote_peberno}"
        )

        await message.channel.send(self.insert_emotes(response_server))

        return response_dm

    async def handle_website_msg(self, message):
        response = (
            "Check out the amazing Int-Far website:\n" +
            "https://mhooge.com/intfar\n" +
            "Write `!website_verify` to sign in to the website, " +
            "allowing you to create bets and see stats."
        )

        await message.channel.send(response)

    async def handle_profile_msg(self, message, target_id):
        target_name = self.get_discord_nick(target_id)

        response = f"URL to {target_name}'s Int-Far profile:\n"
        response += f"http://mhooge.com/intfar/user/{target_id}"

        await message.channel.send(response)

    async def handle_report_msg(self, message, target_id):
        target_name = self.get_discord_nick(target_id)
        mention = self.get_mention_str(target_id)

        reports = self.database.report_user(target_id)

        response = f"{message.author.name} reported {mention} " + "{emote_woahpikachu}\n"
        response += f"{target_name} has been reported {reports} time"
        if reports > 1:
            response += "s"
        response += "."

        await message.channel.send(self.insert_emotes(response))

    async def handle_see_reports_msg(self, message, target_id):
        report_data = self.database.get_reports(target_id)
        response = ""
        for disc_id, reports in report_data:
            name = self.get_discord_nick(disc_id)
            response += f"{name} has been reported {reports} times.\n"

        await message.channel.send(response)

    async def handle_flirtation_msg(self, message, language):
        messages = FLIRT_MESSAGES[language]
        flirt_msg = self.insert_emotes(messages[random.randint(0, len(messages)-1)])
        mention = self.get_mention_str(message.author.id)
        await message.channel.send(f"{mention} {flirt_msg}", tts=True)

    async def handle_doinks_criteria_msg(self, message):
        response = "Criteria for being awarded {emote_Doinks}:"
        for reason in api_util.DOINKS_REASONS:
            response += f"\n - {reason}"
        await message.channel.send(self.insert_emotes(response))

    async def handle_intfar_criteria_msg(self, message, criteria):
        response = ""
        if criteria is None:
            response = "You must specify a criteria. This can be one of:\n"
            response += "'kda', 'deaths', 'kp', 'vision'"
        elif criteria == "kda":
            crit_1 = self.config.kda_lower_threshold
            crit_2 = self.config.kda_death_criteria
            response = ("Criteria for being Int-Far by low KDA:\n" +
                        " - Having the lowest KDA of the people playing\n" +
                        f" - Having a KDA of less than {crit_1}\n" +
                        f" - Having more than {crit_2} deaths")
        elif criteria == "deaths":
            crit_1 = self.config.death_lower_threshold
            crit_2 = self.config.death_kda_criteria
            response = ("Criteria for being Int-Far by many deaths:\n" +
                        " - Having the most deaths of the people playing\n" +
                        f" - Having more than {crit_1} deaths\n"
                        f" - Having less than {crit_2} KDA")
        elif criteria == "kp":
            crit_1 = self.config.kp_lower_threshold
            crit_2 = self.config.kp_takedowns_criteria
            crit_3 = self.config.kp_structures_criteria
            response = ("Criteria for being Int-Far by low KP:\n" +
                        " - Having the lowest KP of the people playing\n" +
                        f" - Having a KP of less than {crit_1}%\n" +
                        f" - Having less than {crit_2} kills + assists\n" +
                        f" - Having less than {crit_3} structures destroyed")
        elif criteria == "vision":
            crit_1 = self.config.vision_score_lower_threshold
            crit_2 = self.config.vision_kda_criteria
            response = ("Criteria for being Int-Far by low vision score:\n" +
                        " - Having the lowest vision score of the people playing\n" +
                        f" - Having less than {crit_1} vision score\n"
                        f" - Having less than {crit_2} KDA")

        await message.channel.send(response)

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

    def extract_target_name(self, split, start_index, end_index=None, default="me"):
        end_index = len(split) if end_index is None else end_index
        if len(split) > start_index:
            return " ".join(split[start_index:end_index])
        return default

    def get_target_id(self, author_id, target_name, all_allowed):
        if target_name == "me": # Target ourselves.
            return author_id

        # Target someone else.
        target_name = target_name.lower().strip()
        if target_name in ("all", "ever"):
            if all_allowed:
                return None
            else:
                raise InvalidArgument("'All' target is not valid for this command.")

        target_id = self.try_get_user_data(target_name)

        if target_id is None:
            msg = f"Error: Invalid summoner or Discord name {self.get_emoji_by_name('PepeHands')}"
            raise InvalidArgument(msg)

        return target_id

    def get_bet_params(self, split):
        amounts = []
        events = []
        targets = []
        index = 1
        while index < len(split):
            event = split[index]
            amount = split[index+1]
            if "&" in (event, amount):
                raise ValueError("Multi-bet input is formatted incorrectly!")
            target = None
            if index + 2 < len(split) and split[index+2] != "&":
                try:
                    end_index = split.index("&", index)
                except ValueError:
                    end_index = len(split)
                target = self.extract_target_name(split, index+2, end_index)
                index = end_index + 1
            else:
                index += 3
            amounts.append(amount)
            events.append(event)
            targets.append(target)
        return amounts, events, targets

    async def get_data_and_respond(self, handler, message, target_name=None, target_all=True, args=None):
        try:
            handler_args = [message]
            if args is not None:
                handler_args.extend(args)

            if target_name is not None:
                target_id = self.get_target_id(message.author.id, target_name, target_all)
                handler_args.append(target_id)
            await handler(*handler_args)
        except InvalidArgument as arg_exception:
            await message.channel.send(arg_exception.args[0])
            self.config.log(arg_exception, self.config.log_error)
        except DBException as db_exception:
            response = "Something went wrong when querying the database! "
            response += self.insert_emotes("{emote_fu}")
            await message.channel.send(response)
            self.config.log(db_exception, self.config.log_error)

    async def valid_command(self, message, cmd, args):
        if cmd in ADMIN_COMMANDS:
            return message.author.id == MY_DISC_ID

        if cmd in CUTE_COMMANDS:
            return True

        is_main_cmd = cmd in VALID_COMMANDS
        valid_cmd = None
        if is_main_cmd:
            valid_cmd = cmd

        for alias in ALIASES:
            if cmd in ALIASES[alias]:
                valid_cmd = alias
                break

        if valid_cmd is None:
            return False

        params_def = VALID_COMMANDS[valid_cmd][0]
        if params_def is None:
            return True

        params_split = params_def.split(" ")
        for index, param in enumerate(params_split):
            if param is None or (param[0] == "(" and param[-1] == ")"):
                return True
            elif param[0] == "[" and param[-1] == "]":
                if len(args) <= index:
                    await message.channel.send(f"Usage: `!{cmd} {params_def}`")
                    return False

        return True

    async def on_message(self, message):
        if message.author == self.user: # Ignore message since it was sent by us (the bot).
            return

        if ((self.config.env == "dev" and message.guild.id != MY_SERVER_ID)
                or (self.config.env == "production" and message.guild.id != DISCORD_SERVER_ID)):
            return

        msg = message.content.strip()
        if msg.startswith("!"):
            split = msg.split(" ")
            first_command = split[0][1:].lower()

            if not await self.valid_command(message, first_command, split[1:]):
                return

            # The following lines are spam protection.
            time_from_last_msg = time() - self.last_message_time.get(message.author.id, 0)
            self.last_message_time[message.author.id] = time()
            curr_timeout = self.timeout_length.get(message.author.id, 0)
            if time_from_last_msg < curr_timeout: # User has already received a penalty for spam.
                if curr_timeout < 10:
                    curr_timeout *= 2 # Increase penalty...
                    if curr_timeout > 10: # ... Up to 10 secs. max.
                        curr_timeout = 10
                    self.timeout_length[message.author.id] = curr_timeout
                return
            if time_from_last_msg < self.config.message_timeout:
                # Some guy is sending messages too fast!
                self.timeout_length[message.author.id] = self.config.message_timeout
                await message.channel.send("Slow down cowboy! You are sending messages real sped-like!")
                return

            self.timeout_length[message.author.id] = 0 # Reset timeout length.

            second_command = None if len(split) < 2 else split[1].lower()
            if cmd_equals(first_command, "register"): # Register the user who sent the command.
                if len(split) > 1:
                    summ_name = " ".join(split[1:])
                    status = self.add_user(summ_name, message.author.id)
                    await message.channel.send(status)
                else:
                    response = "You must supply a summoner name {emote_angry_gual}"
                    await message.channel.send(self.insert_emotes(response))
            elif cmd_equals(first_command, "users"): # List all registered users.
                response = ""
                for disc_id, summ_name, _ in self.database.summoners:
                    summ_names = self.database.summoner_from_discord_id(disc_id)[1]
                    formatted_names = ", ".join(summ_names)
                    nickname = self.get_discord_nick(disc_id)
                    response += f"- {nickname} ({formatted_names})\n"
                if response == "":
                    response = "No lads are currently signed up {emote_nat_really_fine} but you can change this!!"
                else:
                    response = "**--- Registered bois ---**\n" + response
                await message.channel.send(self.insert_emotes(response))
            elif cmd_equals(first_command, "intfar"): # Lookup how many intfar 'awards' the given user has.
                target_name = self.extract_target_name(split, 1)
                await self.get_data_and_respond(
                    self.handle_intfar_msg, message, target_name
                )
            elif cmd_equals(first_command, "intfar_relations"):
                target_name = self.extract_target_name(split, 1)
                await self.get_data_and_respond(
                    self.handle_intfar_relations_msg, message, target_name, target_all=False
                )
            elif cmd_equals(first_command, "doinks"):
                target_name = self.extract_target_name(split, 1)
                await self.get_data_and_respond(self.handle_doinks_msg, message, target_name)
            elif cmd_equals(first_command, "doinks_relations"):
                target_name = self.extract_target_name(split, 1)
                await self.get_data_and_respond(
                    self.handle_doinks_relations_msg, message, target_name, target_all=False
                )
            elif cmd_equals(first_command, "doinks_criteria"):
                await self.handle_doinks_criteria_msg(message)
            elif cmd_equals(first_command, "help"):
                await self.handle_helper_msg(message)
            elif cmd_equals(first_command, "commands"):
                await self.handle_commands_msg(message)
            elif cmd_equals(first_command, "stats"):
                await self.handle_stats_msg(message)
            elif cmd_equals(first_command, "betting"):
                await self.handle_betting_msg(message)
            elif cmd_equals(first_command, "status"):
                await self.handle_status_msg(message)
            elif cmd_equals(first_command, "uptime"):
                await self.handle_uptime_msg(message)
            elif (cmd_equals(first_command, "worst") or cmd_equals(first_command, "best")
                  and len(split) > 1): # Get game stats.
                target_name = self.extract_target_name(split, 2)
                await self.get_data_and_respond(
                    self.handle_stat_msg, message, target_name,
                    args=(first_command, second_command)
                )
            elif cmd_equals(first_command, "intfar_criteria"):
                criteria = self.extract_target_name(split, 1)
                await self.handle_intfar_criteria_msg(message, criteria)
            elif cmd_equals(first_command, "game"):
                target_name = self.extract_target_name(split, 1)
                await self.handle_game_msg(message, target_name)
            elif cmd_equals(first_command, "bet"):
                try:
                    amounts, events, targets = self.get_bet_params(split)
                    await self.handle_make_bet_msg(message, events, amounts, targets)
                except (ValueError, DBException) as exc:
                    await message.channel.send(str(exc))
            elif cmd_equals(first_command, "cancel_bet"):
                target_name = self.extract_target_name(split, 2, default=None)
                await self.get_data_and_respond(
                    self.handle_cancel_bet_msg, message, target_name,
                    target_all=False, args=(second_command,)
                )
            elif cmd_equals(first_command, "give_tokens"):
                target_name = self.extract_target_name(split, 2)
                await self.get_data_and_respond(
                    self.handle_give_tokens_msg, message, target_name,
                    target_all=False, args=(second_command,)
                )
            elif cmd_equals(first_command, "active_bets"):
                target_name = self.extract_target_name(split, 1)
                await self.get_data_and_respond(self.handle_active_bets_msg, message, target_name)
            elif cmd_equals(first_command, "bets"):
                target_name = self.extract_target_name(split, 1)
                await self.get_data_and_respond(self.handle_all_bets_msg, message, target_name, target_all=False)
            elif cmd_equals(first_command, "bet_return") and len(split) > 1:
                target_name = self.extract_target_name(split, 2, default=None)
                await self.get_data_and_respond(
                    self.handle_bet_return_msg, message, target_name,
                    target_all=False, args=(second_command,)
                )
            elif cmd_equals(first_command, "betting_tokens"):
                target_name = self.extract_target_name(split, 1)
                await self.get_data_and_respond(self.handle_token_balance_msg, message, target_name)
            elif cmd_equals(first_command, "website"):
                await self.get_data_and_respond(self.handle_website_msg, message)
            elif cmd_equals(first_command, "website_profile"):
                target_name = self.extract_target_name(split, 1)
                await self.get_data_and_respond(self.handle_profile_msg, message, target_name, target_all=False)
            elif cmd_equals(first_command, "website_verify"):
                response = await self.handle_verify_msg(message)
                dm_sent = await self.send_dm(response, message.author.id)
                if not dm_sent:
                    await message.channel.send(
                        "Error: DM Message could not be sent for some reason ;( Try again!"
                    )
            elif cmd_equals(first_command, "report"):
                target_name = self.extract_target_name(split, 1)
                await self.get_data_and_respond(self.handle_report_msg, message, target_name, target_all=False)
            elif cmd_equals(first_command, "reports"):
                target_name = self.extract_target_name(split, 1)
                await self.get_data_and_respond(self.handle_see_reports_msg, message, target_name)
            elif cmd_equals(first_command, "intdaddy"):
                await self.handle_flirtation_msg(message, "english")
            elif cmd_equals(first_command, "intpapi"):
                await self.handle_flirtation_msg(message, "spanish")
            elif cmd_equals(first_command, "restart"):
                response = self.insert_emotes("I will kill myself and come back stronger! {emote_nazi}")
                await message.channel.send(response)
                self.main_conn.send("We restarting!")
                exit(0)

    async def send_message_unprompted(self, message):
        await self.channel_to_write.send(message)

    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None: # User joined.
            await self.user_joined_voice(member.id)
        elif before.channel is not None and after.channel is None: # User left.
            await self.user_left_voice(member.id)

def run_client(config, database, betting_handler, riot_api, main_pipe, flask_pipe):
    client = DiscordClient(
        config, database, betting_handler, riot_api,
        main_pipe=main_pipe, flask_pipe=flask_pipe
    )
    client.run(config.discord_token)
