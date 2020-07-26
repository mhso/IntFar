import random
from time import time
from datetime import datetime
from sqlite3 import DatabaseError, OperationalError
import asyncio
import discord
import riot_api
import game_stats
from montly_intfar import MonthlyIntfar

DISCORD_SERVER_ID = 619073595561213953
CHANNEL_ID = 730744358751567902
MY_DISC_ID = 267401734513491969

def load_flavor_texts(filename):
    path = f"flavor_texts/{filename}.txt"
    with open(path, "r", encoding="UTF-8") as f:
        return [x.replace("\n", "") for x in f.readlines()]

INTFAR_FLAVOR_TEXTS = load_flavor_texts("intfar")

NO_INTFAR_FLAVOR_TEXTS = load_flavor_texts("no_intfar")

INTFAR_REASONS = ["Low KDA", "Many deaths", "Low KP", "Low Vision Score"]

DOINKS_REASONS = [
    "KDA larger than 10", "More than 30 kills", "More damage than rest of the team",
    "Getting a pentakill", "Vision score larger than 100", "Kill participation larger than 90"
]

MOST_DEATHS_FLAVORS = load_flavor_texts("most_deaths")

LOWEST_KDA_FLAVORS = load_flavor_texts("lowest_kda")

LOWEST_KP_FLAVORS = load_flavor_texts("lowest_kp")

LOWEST_VISION_FLAVORS = load_flavor_texts("lowest_vision")

MENTIONS_NO_PINKWARDS = load_flavor_texts("mentions_no_vision_ward")

MENTIONS_LOW_DAMAGE = load_flavor_texts("mentions_low_damage")

MENTIONS_LOW_CS_MIN = load_flavor_texts("mentions_low_cs_min")

MENTIONS_NO_EPIC_MONSTERS = load_flavor_texts("mentions_no_epic_monsters")

REDEEMING_ACTIONS_FLAVORS = load_flavor_texts("redeeming_actions")

STREAK_FLAVORS = load_flavor_texts("streak")

VALID_COMMANDS = {
    "register": (
        "[summoner_name] - Sign up for the Int-Far™ Tracker™ " +
        "by providing your summoner name (fx. '!register imaqtpie')."
    ),
    "users": "List all users who are currently signed up for the Int-Far™ Tracker™.",
    "help": "Show this helper text.",
    "commands": "Show this helper text.",
    "intfar": (
        "(summoner_name) - Show how many times you (if no summoner name is included), " +
        "or someone else, has been the Int-Far. '!intfar all' lists Int-Far stats for all users."
    ),
    "intfar_relations": "(summoner_name) - Show who you (or someone else) int the most games with.",
    "doinks": "(summoner_name) - Show big doinks plays you (or someone else) did!",
    "best": (
        "[stat] (summoner_name) - Show how many times you (or someone else) " +
        "were the best in the specific stat. " +
        "Fx. '!best kda' shows how many times you had the best KDA in a game."
    ),
    "worst": (
        "[stat] (summoner_name) - Show how many times you (or someone else) " +
        "were the worst at the specific stat."
    ),
    "uptime": "Show for how long the bot has been up and running.",
    "status": (
        "Show overall stats about how many games have been played, " +
        "how many people were Int-Far, etc."
    )
}

CUTE_COMMANDS = {
    "intdaddy": "Flirt with the Int-Far.",
    "intpapi": "Flirt with the Int-Far in spanish."
}

STAT_COMMANDS = [
    "kills", "deaths", "kda", "damage",
    "cs", "gold", "kp", "vision_wards", "vision_score"
]

QUANTITY_DESC = [
    ("most", "fewest"), ("fewest", "most"), ("highest", "lowest"), ("most", "least"),
    ("most", "least"), ("most", "least"), ("highest", "lowest"), ("most", "fewest"),
    ("highest", "lowest")
]

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
    flavor_text = REDEEMING_ACTIONS_FLAVORS[index]
    if value is None:
        return flavor_text
    return flavor_text.replace("{value}", str(value))

def get_streak_flavor_text(nickname, streak):
    index = streak - 2 if streak - 2 < len(STREAK_FLAVORS) else len(STREAK_FLAVORS) - 1
    return STREAK_FLAVORS[index].replace("{nickname}", nickname).replace("{streak}", str(streak))

def zero_pad(number):
    if number < 10:
        return "0" + str(number)
    return str(number)

def round_digits(number):
    if type(number) == float:
        return f"{number:.2f}"
    return str(number)

class DiscordClient(discord.Client):
    def __init__(self, config, database):
        super().__init__()
        self.riot_api = riot_api.APIClient(config)
        self.config = config
        self.database = database
        self.active_users = []
        self.users_in_game = None
        self.active_game = None
        self.channel_to_write = None
        self.initialized = False
        self.last_message_time = {}
        self.time_initialized = datetime.now()

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
            while time_slept < self.config.status_interval:
                await asyncio.sleep(sleep_per_loop)
                time_slept += sleep_per_loop
        except KeyboardInterrupt:
            return

        game_status = self.check_game_status()
        if game_status == 2: # Game is over.
            try:
                self.config.log("GAME OVER!!")
                await self.declare_intfar()
                self.active_game = None
                self.users_in_game = None # Reset the list of users who are in a game.
                asyncio.create_task(self.poll_for_game_start())
            except Exception as e:
                self.config.log("Exception after game was over!!!", self.config.log_error)
                await self.send_error_msg()
                raise e
        elif game_status == 0:
            await self.poll_for_game_end()

    async def poll_for_game_start(self):
        time_slept = 0
        sleep_per_loop = 0.5
        self.config.log("People are active in voice channels! Polling for games...")
        try:
            while time_slept < self.config.status_interval:
                if not self.polling_is_active(): # Stop if people leave voice channels.
                    self.config.log("Polling is no longer active.")
                    return
                await asyncio.sleep(sleep_per_loop)
                time_slept += sleep_per_loop
        except KeyboardInterrupt:
            return

        game_status = self.check_game_status()
        if game_status == 1: # Game has started.
            self.users_in_game = [x for x in self.active_users]
            await self.poll_for_game_end()
        elif game_status == 0:
            await self.poll_for_game_start()

    def user_is_registered(self, summ_name):
        for _, name, _ in self.database.summoners:
            if name == summ_name:
                return True
        return False

    def add_user(self, summ_name, discord_id):
        if self.user_is_registered(summ_name):
            return "User is already registered."
        summ_id = self.riot_api.get_summoner_id(summ_name.replace(" ", "%20"))
        if summ_id is None:
            return f"Error: Invalid summoner name {self.get_emoji_by_name('PepeHands')}"
        self.database.add_user(summ_name, summ_id, discord_id)
        return f"User '{summ_name}' with summoner ID '{summ_id}' succesfully added!"

    def polling_is_active(self): # We only check game statuses if there are two or more active users.
        return len(self.active_users) > 1

    def check_game_status(self):
        active_game = None
        game_ids = set()
        # First check if users are in the same game (or all are in no games).
        user_list = self.active_users if self.users_in_game is None else self.users_in_game
        for _, _, summ_id in user_list:
            game_id = self.riot_api.get_active_game(summ_id)
            if game_id is not None:
                game_ids.add(game_id)
                active_game = game_id

        if len(game_ids) > 1: # People are in different games.
            return 0

        if active_game is not None and self.active_game is None:
            self.active_game = active_game
            self.config.status_interval = 30 # Check status every 30 seconds.
            return 1 # Game is now active.
        if active_game is None and self.active_game is not None: # The current game is over.
            self.config.status_interval = 60*10
            return 2 # Game is over.
        return 0

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

    def get_discord_nick(self, disc_id):
        """
        Return Discord nickname matching the given Discord ID.
        """
        for guild in self.guilds:
            if guild.id == DISCORD_SERVER_ID:
                for member in guild.members:
                    if member.id == disc_id:
                        return member.display_name
        return None

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

    def get_big_doinks(self, data):
        """
        Returns a string describing people who have been redeemed by playing
        exceptionally well.
        Criteria for being redeemed:
            - Having a KDA of 10+
            - Doing more damage than the rest of the team combined
            - Getting a penta-kill
            - Having a vision score of 100+
            - Having a kill-participation of 90%+
        """
        mentions = {} # List of mentioned users for the different criteria.
        for disc_id, stats in data:
            mention_list = []
            kda = game_stats.calc_kda(stats)
            if kda > 10.0:
                mention_list.append((0, round_digits(kda)))
            if stats["kills"] > 30:
                mention_list.append((1, stats["kills"]))
            damage_dealt = stats["totalDamageDealtToChampions"]
            if damage_dealt > stats["damage_by_team"]:
                mention_list.append((2, damage_dealt))
            if stats["pentaKills"] > 0:
                mention_list.append((3, None))
            if stats["visionScore"] > 100:
                mention_list.append((4, stats["visionScore"]))
            kp = game_stats.calc_kill_participation(stats, stats["kills_by_team"])
            if kp > 90:
                mention_list.append((5, kp))
            if mention_list != []:
                mentions[disc_id] = mention_list

        mentions_str = ""
        any_mentions = False
        mentions_by_reason = {d_id: ["0" for _ in DOINKS_REASONS] for d_id in mentions}
        for disc_id in mentions:
            user_str = ""
            if mentions[disc_id] != []:
                prefix = "\n" if any_mentions else ""
                user_str = f"{prefix} {self.get_mention_str(disc_id)} was insane that game! "
                intfars_removed = len(mentions[disc_id])
                user_str += f"He is awarded {intfars_removed} " + "{emote_Doinks} for "
                any_mentions = True

            for (count, (stat_index, stat_value)) in enumerate(mentions[disc_id]):
                prefix = " *and* " if count > 0 else ""
                mentions_by_reason[disc_id][stat_index] = "1"
                user_str += prefix + get_redeeming_flavor_text(stat_index, stat_value)
            mentions_str += user_str

        formatted_mentions = {d_id: "".join(mentions_by_reason[d_id])
                              for d_id in mentions_by_reason}

        return (None, {}) if not any_mentions else (mentions_str, formatted_mentions)

    def get_honorable_mentions(self, data):
        """
        Returns a string describing honorable mentions (questionable stats),
        that wasn't quite bad enough to be named Int-Far for.
        Honorable mentions are given for:
            - Having 0 control wards purchased.
            - Being adc/mid/top/jungle and doing less than 8000 damage.
            - Being adc/mid/top and having less than 4 cs/min.
            - Being jungle and securing no epic monsters.
        """
        mentions = {} # List of mentioned users for the different criteria.
        for disc_id, stats in data:
            mentions[disc_id] = []
            if stats["visionWardsBoughtInGame"] == 0:
                mentions[disc_id].append((0, stats["visionWardsBoughtInGame"]))
            damage_dealt = stats["totalDamageDealtToChampions"]
            if stats["role"] != "DUO_SUPPORT" and damage_dealt < 8000:
                mentions[disc_id].append((1, damage_dealt))
            cs_per_min = (stats["creepsPerMinDeltas"]["0-10"] + stats["creepsPerMinDeltas"]["10-20"]) / 2.0
            if stats["role"] != "DUO_SUPPORT" and stats["lane"] != "JUNGLE" and cs_per_min < 4.0:
                mentions[disc_id].append((2, round_digits(cs_per_min)))
            epic_monsters_secured = stats["baronKills"] + stats["dragonKills"]
            if stats["lane"] == "JUNGLE" and epic_monsters_secured == 0:
                mentions[disc_id].append((3, epic_monsters_secured))

        mentions_str = "Honorable mentions goes out to:\n"
        any_mentions = False
        for disc_id in mentions:
            user_str = ""
            if mentions[disc_id] != []:
                prefix = "\n" if any_mentions else ""
                user_str = f"{prefix}- {self.get_mention_str(disc_id)} for "
                any_mentions = True

            for (count, (stat_index, stat_value)) in enumerate(mentions[disc_id]):
                prefix = " *and* " if count > 0 else ""
                user_str += prefix + get_honorable_mentions_flavor_text(stat_index, stat_value)
            mentions_str += user_str

        return None if not any_mentions else mentions_str

    def intfar_by_kda(self, data):
        """
        Returns the info of the Int-Far, if this person has a truly terrible KDA.
        This is determined by:
            - KDA being the lowest of the group
            - KDA being less than 1.3
            - Number of deaths being more than 2.
        Returns None if none of these criteria matches a person.
        """
        intfar, stats = game_stats.get_outlier(data, "kda")
        lowest_kda = game_stats.calc_kda(stats)
        deaths = stats["deaths"]
        if lowest_kda < self.config.kda_lower_threshold and deaths > 2:
            return (intfar, lowest_kda)
        return (None, None)

    def intfar_by_deaths(self, data):
        """
        Returns the info of the Int-Far, if this person has hecking many deaths.
        This is determined by:
            - Having the max number of deaths in the group
            - Number of deaths being more than 9.
            - KDA being less than 2.1
        Returns None if none of these criteria matches a person.
        """
        intfar, stats = game_stats.get_outlier(data, "deaths", asc=False)
        highest_deaths = stats["deaths"]
        kda = game_stats.calc_kda(stats)
        if highest_deaths > self.config.highest_death_threshold and kda < 2.1:
            return (intfar, highest_deaths)
        return (None, None)

    def intfar_by_kp(self, data):
        """
        Returns the info of the Int-Far, if this person has very low kill participation.
        This is determined by:
            - Having the lowest KP in the group
            - KP being less than 25
            - Number of kills + assists being less than 10
            - Turrets + Inhibitors destroyed < 3
        Returns None if none of these criteria matches a person.
        """
        team_kills = data[0][1]["kills_by_team"]
        intfar, stats = game_stats.get_outlier(data, "kp", total_kills=team_kills)
        lowest_kp = game_stats.calc_kill_participation(stats, team_kills)
        kills = stats["kills"]
        assists = stats["assists"]
        structures_destroyed = stats["turretKills"] + stats["inhibitorKills"]
        if (lowest_kp < self.config.kp_lower_threshold and kills + assists < 10
                and structures_destroyed < 3):
            return (intfar, lowest_kp)
        return (None, None)

    def intfar_by_vision_score(self, data):
        """
        Returns the info of the Int-Far, if this person has very low kill vision score.
        This is determined by:
            - Having the lowest vision score in the group
            - Vision score being less than 9
            - KDA being less than 3
        Returns None if none of these criteria matches a person.
        """
        intfar, stats = game_stats.get_outlier(data, "visionScore")
        lowest_score = stats["visionScore"]
        kda = game_stats.calc_kda(stats)
        if lowest_score < self.config.vision_score_lower_threshold and kda < 3.0:
            return (intfar, lowest_score)
        return (None, None)

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

        message = self.insert_emotes(message)
        await self.channel_to_write.send(message)

    def get_intfar_details(self, stats):
        intfar_kda_id, kda = self.intfar_by_kda(stats)
        if intfar_kda_id is not None:
            self.config.log("Int-Far because of KDA.")

        intfar_deaths_id, deaths = self.intfar_by_deaths(stats)
        if intfar_deaths_id is not None:
            self.config.log("Int-Far because of deaths.")

        intfar_kp_id, kp = self.intfar_by_kp(stats)
        if intfar_kp_id is not None:
            self.config.log("Int-Far because of kill participation.")

        intfar_vision_id, vision_score = self.intfar_by_vision_score(stats)
        if intfar_vision_id is not None:
            self.config.log("Int-Far because of vision score.")

        return [
            (intfar_kda_id, kda), (intfar_deaths_id, deaths),
            (intfar_kp_id, kp), (intfar_vision_id, vision_score)
        ]

    def get_filtered_stats(self, game_info):
        """
        Get relevant stats from the given game data and filter the data
        that is relevant for the Discord users that participated in the game.
        """
        kills_per_team = {100: 0, 200: 0}
        damage_per_team = {100: 0, 200: 0}
        our_team = 100
        filtered_stats = []
        for part_info in game_info["participantIdentities"]:
            for participant in game_info["participants"]:
                if part_info["participantId"] == participant["participantId"]:
                    kills_per_team[participant["teamId"]] += participant["stats"]["kills"]
                    damage_per_team[participant["teamId"]] += participant["stats"]["totalDamageDealtToChampions"]
                    # We loop through the static 'self.users_in_game' list and not the dynamic
                    # 'self.active_players' for safety.
                    for disc_id, _, summ_id in self.users_in_game:
                        if summ_id == part_info["player"]["summonerId"]:
                            our_team = participant["teamId"]
                            combined_stats = participant["stats"]
                            combined_stats["timestamp"] = game_info["gameCreation"]
                            combined_stats.update(participant["timeline"])
                            filtered_stats.append((disc_id, combined_stats))

        for _, stats in filtered_stats:
            stats["kills_by_team"] = kills_per_team[our_team]
            stats["damage_by_team"] = damage_per_team[our_team]
            for team in game_info["teams"]:
                if team["teamId"] == our_team:
                    stats["baronKills"] = team["baronKills"]
                    stats["dragonKills"] = team["dragonKills"]

        return filtered_stats

    async def declare_intfar(self):
        """
        Called when the currently active game is over.
        Determines if an Int-Far should be crowned and for what,
        and sends out a status message about the potential Int-Far (if there was one).
        Also saves worst/best stats for the current game.
        """
        game_info = self.riot_api.get_game_details(self.active_game, tries=2)

        if not self.riot_api.is_summoners_rift(game_info["mapId"]):
            response = "That game was not on Summoner's Rift "
            response += "{emote_woahpikachu} no Int-Far will be crowned "
            response += "and no stats will be saved."
            await self.channel_to_write.send(self.insert_emotes(response))
            return

        filtered_stats = self.get_filtered_stats(game_info)

        intfar_details = self.get_intfar_details(filtered_stats)
        reason_keys = ["kda", "deaths", "kp", "visionScore"]
        intfar_counts = {}
        max_intfar_count = 0
        max_count_intfar = None
        intfar_data = {}

        # Look through details for the people qualifying for Int-Far.
        # The one with most criteria met gets chosen.
        for (index, (intfar_disc_id, stat_value)) in enumerate(intfar_details):
            if intfar_disc_id is not None:
                if intfar_disc_id not in intfar_counts:
                    intfar_counts[intfar_disc_id] = 0
                    intfar_data[intfar_disc_id] = []
                current_intfar_count = intfar_counts[intfar_disc_id] + 1
                intfar_counts[intfar_disc_id] = current_intfar_count
                if current_intfar_count > max_intfar_count:
                    max_intfar_count = current_intfar_count
                    max_count_intfar = intfar_disc_id
                intfar_data[intfar_disc_id].append((index, stat_value))

        reason_ids = ["0", "0", "0", "0"]
        doinks = {}
        intfar_streak, prev_intfar = self.database.get_current_intfar_streak()
        if max_count_intfar is not None: # Save data for the current game and send int-far message.
            reason = ""
            # Go through the criteria the chosen int-far met and list them in a readable format.
            for (count, (reason_index, stat_value)) in enumerate(intfar_data[max_count_intfar]):
                key = reason_keys[reason_index]
                reason_text = get_reason_flavor_text(round_digits(stat_value), key)
                reason_ids[reason_index] = "1"
                if count > 0:
                    reason_text = " **AND** " + reason_text
                reason += reason_text

            await self.send_intfar_message(max_count_intfar, reason, intfar_streak, prev_intfar)
        else: # No one was bad enough to be Int-Far.
            self.config.log("No Int-Far that game!")
            response = get_no_intfar_flavor_text()
            honorable_mention_text = self.get_honorable_mentions(filtered_stats)
            if honorable_mention_text is not None:
                response += "\n" + honorable_mention_text
            redeemed_text, doinks = self.get_big_doinks(filtered_stats)
            if redeemed_text is not None:
                response += "\n" + redeemed_text
            streak_msg = self.get_streak_msg(None, intfar_streak, prev_intfar)
            if streak_msg is not None:
                response += "\n" + streak_msg

            await self.channel_to_write.send(self.insert_emotes(response))

        if not self.config.testing:
            try: # Save stats.
                reasons_str = "".join(reason_ids)
                if reasons_str == "0000":
                    reasons_str = None
                self.database.record_stats(max_count_intfar, reasons_str, doinks,
                                           self.active_game, filtered_stats, self.users_in_game)
            except (DatabaseError, OperationalError) as exception:
                self.config.log("Game stats could not be saved!", self.config.log_error)
                self.config.log(exception)
                raise exception

            self.config.log("Game over! Stats were saved succesfully.")

    async def user_joined_voice(self, member, start_polling=True):
        self.config.log("User joined voice: " + str(member.id))
        summoner_info = self.database.summoner_from_discord_id(member.id)
        if summoner_info is not None:
            self.config.log("Summoner joined voice: " + summoner_info[1])
            if not self.polling_is_active() and start_polling:
                self.config.log("Polling is now active!")
                asyncio.create_task(self.poll_for_game_start())
            self.active_users.append(summoner_info)
            self.config.log(f"Active users: {len(self.active_users)}")

    async def user_left_voice(self, member):
        self.config.log("User left voice: " + str(member.id))
        summoner_info = self.database.summoner_from_discord_id(member.id)
        if summoner_info is not None and summoner_info in self.active_users:
            self.active_users.remove(summoner_info)
            self.config.log("Summoner left voice: " + summoner_info[1])
            self.config.log(f"Active users: {len(self.active_users)}")

    async def remove_intfar_role(self, intfar_id, role_id):
        nibs_guild = None
        for guild in self.guilds: # Add all users currently in voice channels as active users.
            if guild.id == DISCORD_SERVER_ID:
                nibs_guild = guild
                break

        member = nibs_guild.get_member(intfar_id)
        role = nibs_guild.get_role(role_id)
        await member.remove_roles(role)

    async def assign_monthly_intfar_role(self, month, intfar_id):
        prev_month = month - 1 if month != 1 else 12

        months = [
            "January", "February", "March", "April", "May", "June", "July",
            "August", "September", "October", "November", "December"
        ]
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

        month_name = months[prev_month-1]
        color = discord.Color.from_rgb(*colors[prev_month-1])
        role_name = f"Int-Far of the Month - {month_name}"

        role = await nibs_guild.create_role(name=role_name, colour=color)
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
        monitor = MonthlyIntfar()
        self.config.log("Starting Int-Far-of-the-month monitor... ")
        format_time = monitor.time_at_announcement.strftime("%Y-%m-%d %H:%M:%S")
        self.config.log(f"Monthly Int-Far will be crowned at {format_time} UTC+1")

        time_to_sleep = 60
        while monitor.get_seconds_left() > 0:
            await asyncio.sleep(time_to_sleep)

        intfar_data = self.database.get_intfars_of_the_month()
        intfar_data.sort(key=lambda x: (x[3], x[2]), reverse=True) # Sort by pct of games being Int-Far.
        intfar_details = [(self.get_mention_str(disc_id), games, intfars, ratio)
                          for (disc_id, games, intfars, ratio) in intfar_data]
        intro_desc = "THE RESULTS ARE IN!!! Int-Far of the month is...\n"
        intro_desc += "*DRUM ROLL*\n"
        message = monitor.get_description(intfar_details)
        message += "{emote_uwu} {emote_sadbuttrue} {emote_smol_dave} "
        message += "{emote_extra_creme} {emote_happy_nono} {emote_hairy_retard}"
        final_msg = intro_desc + self.insert_emotes(message)
        await self.channel_to_write.send(final_msg)

        # Assign Int-Far of the Month 'badge' (role) to the top Int-Far.
        current_month = monitor.time_at_announcement.month
        await self.assign_monthly_intfar_role(current_month, intfar_data[0][0])

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
                for voice_channel in guild.voice_channels:
                    members_in_voice = voice_channel.members
                    count = 0
                    for member in members_in_voice:
                        # Start polling for an active game
                        # if more than one user is active in voice.
                        start_polling = count == 1
                        await self.user_joined_voice(member, start_polling)
                        count += 1
                for text_channel in guild.text_channels:
                    if text_channel.id == CHANNEL_ID: # Find the 'int-far-spam' channel.
                        self.channel_to_write = text_channel
                        asyncio.create_task(self.sleep_until_monthly_infar())
                        return

    async def handle_helper_msg(self, message):
        """
        Write the helper/commands message to Discord.
        """
        valid_stats = ", ".join("'" + cmd + "'" for cmd in STAT_COMMANDS)
        response = "I gotchu fam {emote_nazi}\n"
        response += "The Int-Far™ Tracker™ is a highly sophisticated bot "
        response += "that watches when people in this server plays League, "
        response += "and judges them harshly if they int too hard {emote_simp_but_closeup}\n"

        response += "**--- Valid commands, and their usages, are listed below ---**\n```"
        for cmd, desc in VALID_COMMANDS.items():
            response += f"!{cmd} - {desc}\n\n"

        response += "**--- Valid stats ---**\n```"
        response += valid_stats
        response += "\n```"
        await message.channel.send(self.insert_emotes(response))

    def get_uptime(self, dt_init):
        dt_now = datetime.now()
        normed_dt = dt_now.replace(year=dt_init.year, month=dt_init.month)
        month_normed = dt_now.month if dt_now.month >= dt_init.month else dt_now.month + 12
        months = month_normed - dt_init.month
        if normed_dt < dt_init:
            months -= 1
        years = dt_now.year - dt_init.year
        if dt_now.month < dt_init.month:
            years -= 1
        td = normed_dt - dt_init
        days = td.days
        seconds = td.seconds
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        response = f"{zero_pad(hours)}h {zero_pad(minutes)}m {zero_pad(seconds)}s"
        if minutes == 0:
            response = f"{seconds} seconds"
        else:
            response = f"{zero_pad(minutes)} minutes & {zero_pad(seconds)} seconds"
        if hours > 0:
            response = f"{zero_pad(hours)}h {zero_pad(minutes)}m {zero_pad(seconds)}s "
        if days > 0:
            response = f"{days} days, " + response
        if months > 0:
            response = f"{months} months, " + response
        if years > 0:
            response = f"{years} years, " + response
        return response

    async def handle_uptime_msg(self, message):
        uptime_formatted = self.get_uptime(self.time_initialized)
        await message.channel.send(f"Int-Far™ Tracker™ has been online for {uptime_formatted}")

    async def handle_status_msg(self, message):
        """
        Gather meta stats about this bot and write them to Discord.
        """
        response = f"**Uptime:** {self.get_uptime(self.time_initialized)}\n"

        (games, earliest_game, users, intfars,
         doinks, twos, threes, fours, fives) = self.database.get_meta_stats()

        earliest_time = datetime.fromtimestamp(earliest_game).strftime("%Y-%m-%d")
        response += f"Since {earliest_time}:\n"
        response += f"- **{games}** games have been played\n"
        response += f"- **{users}** users have signed up\n"
        response += f"- **{intfars}** Int-Far awards have been given\n"
        response += f"- **{doinks}** " + self.insert_emotes("{emote_Doinks} has been earned\n")
        response += "Of all games played:\n"
        pct_intfar = int((intfars / games) * 100)
        response += f"- **{pct_intfar}%** resulted in someone being Int-Far\n"
        response += f"- **{twos}%** were as a duo\n"
        response += f"- **{threes}%** were as a three-man\n"
        response += f"- **{fours}%** were as a four-man\n"
        response += f"- **{fives}%** were as a five-man stack"

        await message.channel.send(response)

    def try_get_user_data(self, name):
        user_data = self.database.discord_id_from_summoner(name)
        if user_data is None: # Summoner name gave no result, try Discord name.
            return self.get_discord_id(name)
        return user_data[0]

    def get_intfar_relation_stats(self, target_id):
        data = []
        games_relations, intfars_relations = self.database.get_intfar_relations(target_id)
        for disc_id, total_games in games_relations.items():
            intfars = intfars_relations.get(disc_id, 0)
            data.append((disc_id, total_games, intfars, int((intfars / total_games) * 100)))

        return sorted(data, key=lambda x: x[2], reverse=True)

    async def handle_intfar_relations_msg(self, message, target_name):
        target_id = None
        if target_name is not None: # Check intfar stats for someone else.
            target_name = target_name.lower()
            target_id = self.try_get_user_data(target_name.strip())
            if target_id is None:
                msg = "Error: Invalid summoner or Discord name "
                msg += f"{self.get_emoji_by_name('PepeHands')}"
                await message.channel.send(msg)
                return
        else: # Check intfar stats for the person sending the message.
            target_id = message.author.id

        data = self.get_intfar_relation_stats(target_id)

        response = f"Breakdown of players {self.get_discord_nick(target_id)} has inted with:\n"
        for disc_id, total_games, intfars, ratio in data:
            nick = self.get_discord_nick(disc_id)
            response += f"- {nick}: **{intfars}** times "
            response += f"(**{ratio}%** of **{total_games}** games)\n"

        await message.channel.send(response)

    async def handle_intfar_msg(self, message, target_name):
        def get_intfar_stats(disc_id, expanded=True):
            person_to_check = self.get_discord_nick(disc_id)
            total_games, intfar_reason_ids = self.database.get_intfar_stats(disc_id)
            intfar_counts = {x: 0 for x in range(len(INTFAR_REASONS))}
            for reason_id in intfar_reason_ids:
                intfar_ids = [int(x) for x in reason_id[0]]
                for index, intfar_id in enumerate(intfar_ids):
                    if intfar_id == 1:
                        intfar_counts[index] += 1
            msg = f"{person_to_check} has been an Int-Far {len(intfar_reason_ids)} times "
            msg += self.insert_emotes("{emote_unlimited_chins}")
            if expanded and len(intfar_reason_ids) > 0:
                pct_intfar = (0 if total_games == 0
                                else int(len(intfar_reason_ids) / total_games * 100))
                ratio_desc = "\n" + f"He was Int-Far in **{pct_intfar}%** of his {total_games} total games played"
                reason_desc = "\n" + "Int-Fars awarded so far:\n"
                for reason_id, reason in enumerate(INTFAR_REASONS):
                    reason_desc += f" - {reason}: **{intfar_counts[reason_id]}**\n"

                longest_streak = self.database.get_longest_intfar_streak(disc_id)
                streak_desc = f"His longest Int-Far streak was **{longest_streak}** "
                streak_desc += "games in a row " + "{emote_suk_a_hotdok}"
                streak_desc = self.insert_emotes(streak_desc) + "\n"

                relations_data = self.get_intfar_relation_stats(disc_id)[0]
                most_intfars_nick = self.get_discord_nick(relations_data[0])
                relations_desc = f"He has inted the most when playing with {most_intfars_nick} "
                relations_desc += f"where he inted {relations_data[2]} games ({relations_data[3]}% "
                relations_desc += f"of {relations_data[1]} games)"
                relations_desc += self.insert_emotes("{emote_smol_gual}")

                msg += ratio_desc + reason_desc + streak_desc + relations_desc

            return msg, len(intfar_reason_ids)

        response = ""
        if target_name is not None: # Check intfar stats for someone else.
            target_name = target_name.lower()
            if target_name == "all":
                messages = []
                for disc_id, _, _ in self.database.summoners:
                    resp_str, intfars = get_intfar_stats(disc_id, expanded=False)
                    messages.append((resp_str, intfars))
                messages.sort(key=lambda x: x[1], reverse=True)
                for resp_str, _ in messages:
                    response += "- " + resp_str + "\n"
            else:
                target_id = self.try_get_user_data(target_name.strip())
                if target_id is None:
                    msg = "Error: Invalid summoner or Discord name "
                    msg += f"{self.get_emoji_by_name('PepeHands')}"
                    await message.channel.send(msg)
                    return
                response = get_intfar_stats(target_id)[0]
        else: # Check intfar stats for the person sending the message.
            response = get_intfar_stats(message.author.id)[0]

        await message.channel.send(response)

    async def handle_doinks_msg(self, message, target_name):
        def get_doinks_stats(disc_id, expanded=True):
            person_to_check = self.get_discord_nick(disc_id)
            doink_reason_ids = self.database.get_doinks_stats(disc_id)
            intfar_counts = {x: 0 for x in range(len(DOINKS_REASONS))}
            for reason_id in doink_reason_ids:
                intfar_ids = [int(x) for x in reason_id[0]]
                for index, intfar_id in enumerate(intfar_ids):
                    if intfar_id == 1:
                        intfar_counts[index] += 1
            msg = f"{person_to_check} has earned {len(doink_reason_ids)} "
            msg += self.insert_emotes("{emote_Doinks}")
            if expanded and len(doink_reason_ids) > 0:
                reason_desc = "\n" + "Big doinks awarded so far:"
                for reason_id, reason in enumerate(DOINKS_REASONS):
                    reason_desc += f"\n - {reason}: **{intfar_counts[reason_id]}**"

                msg += reason_desc

            return msg, len(doink_reason_ids)

        response = ""
        if target_name is not None: # Check intfar stats for someone else.
            target_name = target_name.lower()
            if target_name == "all":
                messages = []
                for disc_id, _, _ in self.database.summoners:
                    resp_str, intfars = get_doinks_stats(disc_id, expanded=False)
                    messages.append((resp_str, intfars))
                messages.sort(key=lambda x: x[1], reverse=True)
                for resp_str, _ in messages:
                    response += "- " + resp_str + "\n"
            else:
                target_id = self.try_get_user_data(target_name.strip())
                if target_id is None:
                    msg = "Error: Invalid summoner or Discord name "
                    msg += f"{self.get_emoji_by_name('PepeHands')}"
                    await message.channel.send(msg)
                    return
                response = get_doinks_stats(target_id)[0]
        else: # Check intfar stats for the person sending the message.
            response = get_doinks_stats(message.author.id)[0]

        await message.channel.send(response)

    async def handle_stat_msg(self, message, first_cmd, second_cmd, target_name):
        """
        Get the value of the requested stat for the requested player.
        F.x. '!best damage dumbledonger'.
        """
        if second_cmd in STAT_COMMANDS: # Check if the requested stat is a valid stat.
            stat = second_cmd
            stat_index = STAT_COMMANDS.index(stat)
            self.config.log(f"Stat requested: {first_cmd} {stat}")
            best = first_cmd == "best"
            quantity_type = 0 if best else 1
            # Check whether to find the max or min of some value, when returning
            # 'his most/lowest [stat] ever was ... Usually highest is best,
            # lowest is worse, except with deaths, where the opposite is the case.
            maximize = not ((stat != "deaths") ^ best)
            target_id = message.author.id
            recepient = message.author.name

            if target_name is not None: # Get someone else's stat information.
                target_name = target_name.lower()
                target_id = self.try_get_user_data(target_name.strip())
                if target_id is None:
                    msg = "Error: Invalid summoner or Discord name "
                    msg += f"{self.get_emoji_by_name('PepeHands')}"
                    await message.channel.send(msg)
                    return
                recepient = self.get_discord_nick(target_id)

            (stat_count, # <- How many times the stat has occured.
             min_or_max_value, # <- Highest/lowest occurance of the stat value.
             game_id) = self.database.get_stat(stat + "_id", stat, best, target_id, maximize)

            # Get a readable description, such as 'most deaths' or 'lowest kp'.
            readable_stat = QUANTITY_DESC[stat_index][quantity_type] + " " + stat
            response = (f"{recepient} has gotten {readable_stat} in a game " +
                        f"{stat_count} times " + self.insert_emotes("{emote_pog}") + "\n")
            if min_or_max_value is not None:
                # The target user has gotten most/fewest of 'stat' in at least one game.
                game_info = self.riot_api.get_game_details(game_id)
                summ_id = self.database.summoner_from_discord_id(target_id)[2]
                game_summary = game_stats.get_game_summary(game_info, summ_id, self.riot_api)
                response += f"His {readable_stat} ever was "
                response += f"{round_digits(min_or_max_value)} as {game_summary}"

            await message.channel.send(response)
        else:
            response = f"Not a valid stat: '{second_cmd}' "
            response += self.insert_emotes("{emote_carole_fucking_baskin}")
            await message.channel.send(response)

    async def handle_test_msg(self):
        self.config.testing = True
        self.active_users = [
            self.database.discord_id_from_summoner("Prince Jarvan lV"),
            self.database.discord_id_from_summoner("Senile Felines")
            #self.database.discord_id_from_summoner("Stirred Martini"),
            #self.database.discord_id_from_summoner("Dumbledonger"),
            #self.database.discord_id_from_summoner("Kazpariuz")
        ]
        #self.active_game = 4703181863 # Martin double Int-Far.
        self.active_game = 4700945429 # Me honorable mention.
        await self.declare_intfar()
        self.config.testing = False

    def get_target_name(self, split, start_index):
        if len(split) > start_index:
            return " ".join(split[start_index:])
        return None

    async def get_data_and_respond(self, handler, *args):
        try:
            await handler(*args)
        except (DatabaseError, OperationalError) as exception:
            response = "Something went wrong when querying the database! "
            response += self.insert_emotes("{emote_fu}")
            await args[0].channel.send(response)
            self.config.log(exception, self.config.log_error)

    async def on_message(self, message):
        if message.author == self.user: # Ignore message since it was sent by us (the bot).
            return

        msg = message.content.strip()
        if msg.startswith("!"):
            split = msg.split(" ")
            first_command = split[0][1:].lower()

            if first_command not in VALID_COMMANDS and first_command != "test":
                return

            if time() - self.last_message_time.get(message.author.id, 0) < self.config.message_timeout:
                # Some guy is sending messages too fast!
                await message.channel.send("Slow down cowboy! You are sending messages real sped-like!")
                return

            second_command = None if len(split) < 2 else split[1].lower()
            if first_command == "register": # Register the user who sent the command.
                if len(split) > 1:
                    summ_name = " ".join(split[1:])
                    status = self.add_user(summ_name, message.author.id)
                    await message.channel.send(status)
                else:
                    response = "You must supply a summoner name {emote_angry_gual}"
                    await message.channel.send(self.insert_emotes(response))
            elif first_command == "users": # List all registered users.
                response = ""
                for disc_id, summ_name, _ in self.database.summoners:
                    nickname = self.get_discord_nick(disc_id)
                    response += f"- {nickname} ({summ_name})\n"
                if response == "":
                    response = "No lads are currently signed up {emote_nat_really_fine} but you can change this!!"
                else:
                    response = "**--- Registered bois ---**\n" + response
                await message.channel.send(self.insert_emotes(response))
            elif first_command == "intfar": # Lookup how many intfar 'awards' the given user has.
                target_name = self.get_target_name(split, 1)
                await self.get_data_and_respond(self.handle_intfar_msg, message, target_name)
            elif first_command == "intfar_relations":
                target_name = self.get_target_name(split, 1)
                await self.get_data_and_respond(self.handle_intfar_relations_msg, message, target_name)
            elif first_command == "doinks":
                target_name = self.get_target_name(split, 1)
                await self.get_data_and_respond(self.handle_doinks_msg, message, target_name)
            elif first_command in ("help", "commands"):
                await self.handle_helper_msg(message)
            elif first_command == "status":
                await self.handle_status_msg(message)
            elif first_command == "uptime":
                await self.handle_uptime_msg(message)
            elif first_command in ["worst", "best"] and len(split) > 1: # Get game stats.
                target_name = self.get_target_name(split, 2)
                await self.get_data_and_respond(self.handle_stat_msg, message, first_command, second_command, target_name)
            elif first_command == "test" and message.author.id == MY_DISC_ID:
                await self.handle_test_msg()

            self.last_message_time[message.author.id] = time()

    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None: # User joined.
            await self.user_joined_voice(member)
        elif before.channel is not None and after.channel is None: # User left.
            await self.user_left_voice(member)
