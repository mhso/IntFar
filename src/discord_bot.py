import random
from time import sleep
from sqlite3 import DatabaseError, OperationalError
import discord
import riot_api
import game_stats

DISCORD_SERVER_ID = 512363920044982272 # TODO: Change to actual server ID.
CHANNEL_ID = 123 # TODO: Change to actual channel ID.

INTFAR_FLAVOR_TEXTS = [
    "And the Int-Far goes to... {nickname} :hairy_retard: He wins for {reason}!",
    "Uh oh, stinky :happy_nono:! {nickname} has been a very naughty boi! He is awarded one Int-Far token for {reason}!",
    "Oof {nickname}, better luck next time :smol_dave: take this Int-Far award for {reason}!",
    "Oh heck :morton: {nickname} did a fucky-wucky that game! He is awarded Int-Far for {reason}!",
    "Yikes :big_dave: unlucko game from {nickname}. Accept this pity gift of being crowned Int-Far for {reason}."
]

MOST_DEATHS_FLAVORS = [
    "dying a total of {deaths} times",
    "feeding every child in Africa by giving away {deaths} kills",
    "being dead 69% of the game with {deaths} deaths",
    "having a permanent gray screen with {deaths} deaths"
]

LOWEST_KDA_FLAVORS = [
    "having a tragic KDA of {kda}",
    "putting any Iron IV scrub to shame with a KDA of {kda}",
    "being an anti KDA player with a KDA of {kda}"
]

STAT_COMMANDS = [
    "kills", "deaths", "kda", "damage",
    "cs", "gold", "kp", "vision_wards", "vision_score"
]

QUANTITY_DESC = [
    ("most", "fewest"), ("fewest", "most"), ("highest", "lowest"), ("most", "least"),
    ("most", "least"), ("most", "least"), ("most", "fewest"), ("highest", "lowest")
]

def get_intfar_flavor_text(nickname, reason):
    flavor_text = INTFAR_FLAVOR_TEXTS[random.randint(0, len(INTFAR_FLAVOR_TEXTS)-1)]
    return flavor_text.replace("{nickname}", nickname).replace("{reason}", reason)

def get_reason_flavor_text(value, reason):
    flavor_values = []
    if reason == "kda":
        flavor_values = LOWEST_KDA_FLAVORS
    elif reason == "deaths":
        flavor_text = MOST_DEATHS_FLAVORS
    flavor_text = flavor_values[random.randint(0, len(flavor_values)-1)]
    return flavor_text.replace("{" + reason + "}", value)

class DiscordClient(discord.Client):
    def __init__(self, config, database):
        super().__init__()
        self.riot_api = riot_api.APIClient(config)
        self.config = config
        self.database = database
        self.active_users = []
        self.active_game = None
        self.channel_to_write = None

    def poll_for_game_end(self):
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
                sleep(sleep_per_loop)
                time_slept += sleep_per_loop
        except KeyboardInterrupt:
            return

        game_status = self.check_game_status()
        if game_status == 2: # Game is over.
            self.declare_intfar()
        else:
            self.poll_for_game_end()

    def poll_for_game_start(self):
        time_slept = 0
        sleep_per_loop = 0.5
        self.config.log("People are active in voice channels! Polling for games...")
        try:
            while time_slept < self.config.status_interval:
                if not self.polling_is_active(): # Stop if people leave voice channels.
                    return
                sleep(sleep_per_loop)
                time_slept += sleep_per_loop
        except KeyboardInterrupt:
            return

        game_status = self.check_game_status()
        if game_status == 1: # Game has started.
            self.poll_for_game_end()
        else:
            self.poll_for_game_start()

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
            return "Error: Invalid summoner name :PepeHands:"
        self.database.add_user(summ_name, summ_id, discord_id)
        self.config.log(self.database.summoners)
        return f"User '{summ_name}' with summoner ID '{summ_id}' succesfully added!"

    def polling_is_active(self): # We only check game statuses if there are two or more active users.
        return len(self.active_users) > 1

    def check_game_status(self):
        active_game = None
        game_ids = set()
        # First check if users are in the same game (or all are in no games).
        for _, _, summ_id in self.active_users:
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
        elif active_game is None and self.active_game is not None: # The current game is over.
            self.config.status_interval = 60*10
            return 2 # Game is over.
        return 0

    def get_discord_nick(self, disc_id):
        """
        Return Discord nickname matching the given Discord ID.
        """
        for guild in self.guilds:
            if guild.id == DISCORD_SERVER_ID:
                for member in guild.members:
                    if member.id == disc_id:
                        return member.name
        return None

    def intfar_by_kda(self, data):
        """
        Returns the info of the Int-Far, if this person has a truly terribhle KDA.
        This is determined by:
            - KDA being the lowest of the group
            - KDA being less than 1.0
            - Number of deaths being more than 2.
        Returns None if none of these criteria matches a person.
        """
        intfar, stats = game_stats.get_outlier(data, "kda")
        lowest_kda = game_stats.calc_kda(stats)
        deaths = stats["deaths"]
        return ((intfar, lowest_kda)
                if lowest_kda < self.config.kda_lower_threshold and deaths > 2
                else None, None)

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
        return ((intfar, highest_deaths)
                if highest_deaths > self.config.highest_death_threshold and kda < 2.1
                else None, None)

    async def send_intfar_message(self, disc_id, reason):
        nickname = self.get_discord_nick(disc_id)
        message = get_intfar_flavor_text(nickname, reason)
        await self.channel_to_write.send(message)

    def get_intfar_details(self, stats):
        intfar_disc_id, kda = self.intfar_by_kda(stats)
        if intfar_disc_id is not None:
            return intfar_disc_id, get_reason_flavor_text(kda, "kda")

        intfar_disc_id, deaths = self.intfar_by_deaths(stats)
        if intfar_disc_id is not None:
            return intfar_disc_id, get_reason_flavor_text(deaths, "deaths")

        return None, None

    def declare_intfar(self): # Check final game status.
        game_info = self.riot_api.get_game_details(self.active_game)
        filtered_stats = []
        for disc_id, _, summ_id in self.active_users:
            for part_info in game_info["participantIdentities"]:
                if summ_id == part_info["player"]["summonerId"]:
                    for participant in game_info["participants"]:
                        if part_info["participantId"] == participant["participantId"]:
                            filtered_stats.append((disc_id, participant["stats"]))
                            break
                    break

        intfar_disc_id, reason = self.get_intfar_details(filtered_stats)
        if intfar_disc_id is not None:
            self.send_intfar_message(intfar_disc_id, reason)

        try:
            self.database.record_stats(intfar_disc_id, self.active_game, filtered_stats)
        except (DatabaseError, OperationalError) as exception:
            self.config.log("Game stats could not be saved!", self.config.log_error)
            self.config.log(exception)
        self.config.log("Game over! Stats were saved succesfully.")
        self.active_game = None

    def user_joined_voice(self, member):
        self.config.log("User joined voice: " + str(member.id))
        summoner_info = self.database.summoner_from_discord_id(member.id)
        if summoner_info is not None:
            self.active_users.append(summoner_info)
            self.config.log("Summoner joined voice: " + summoner_info[1])
            if self.polling_is_active():
                self.config.log("Polling is now active!")
                self.poll_for_game_start()

    def user_left_voice(self, member):
        self.config.log("User left voice: " + str(member.id))
        summoner_info = self.database.summoner_from_discord_id(member.id)
        if summoner_info is not None:
            self.active_users.remove(summoner_info)
            self.config.log("Summoner left voice: " + summoner_info[1])
            if not self.polling_is_active():
                self.config.log("Polling is no longer active.")

    async def on_ready(self):
        self.config.log('Logged on as {0}!'.format(self.user))
        for guild in self.guilds: # Add all users currently in voice channels as active users.
            if guild.id == DISCORD_SERVER_ID:
                for voice_channel in guild.voice_channels:
                    members_in_voice = voice_channel.members
                    for member in members_in_voice:
                        self.user_joined_voice(member)
                for text_channel in guild.text_channels:
                    if text_channel.id == CHANNEL_ID:
                        self.channel_to_write = text_channel
                        return

    async def on_message(self, message):
        if message.author == self.user: # Ignore message since it was sent by us (the bot).
            return

        msg = message.content.strip()
        if msg.startswith("!"):
            split = msg.split(" ")
            first_command = split[0][1:]
            second_command = None if len(split) < 2 else split[1]
            if first_command == "register":
                if len(split) > 1:
                    summ_name = " ".join(split[1:])
                    status = self.add_user(summ_name, message.author.id)
                    await message.channel.send(status)
            elif first_command == "users":
                response = ""
                for disc_id, summ_name, _ in self.database.summoners:
                    nickname = self.get_discord_nick(disc_id)
                    response += f"- {nickname} ({summ_name})\n"
                if response == "":
                    response = "No lads are currently signed up :nat_really_fine: but you can change this!!"
                else:
                    response = "**--- Registered bois ---**\n" + response
                await message.channel.send(response)
            elif first_command in ("help", "commands"):
                valid_stats = ", ".join("'" + cmd + "'" for cmd in STAT_COMMANDS)
                response = "I gotchu fam :nazi:\n"
                response += "**--- Valid commands, and their usages, are listed below ---**\n```"
                response += (
                    "!register [summoner_name] - Sign up for the Int-Far™ Tracker™ " +
                    "by providing your summoner name (fx. '!register imaqtpie').\n\n" +
                    "!users - List all users who are currently signed up for the Int-Far™ Tracker™.\n\n" +
                    "!help - Show this helper text.\n\n" +
                    "!commands - Show this helper text.\n\n" +
                    "!best [stat] - Show how many times you were the best in the specific stat. " +
                    "Fx. '!best kda' shows how many times you had the best KDA in a game.\n\n" +
                    "!worst [stat] - Show how many times you were the worst at the specific stat.\n\n```" +
                    "**--- Valid stats ---**\n```"
                )
                response += valid_stats
                response += "\n```"
                await message.channel.send(response)
            elif first_command in ["worst", "best"] and len(split) > 1: # Get game stats.
                if second_command in STAT_COMMANDS:
                    stat_index = STAT_COMMANDS.index(second_command)
                    stat = STAT_COMMANDS[stat_index]
                    self.config.log(f"Stat requested: {first_command} {stat}")
                    try:
                        best = second_command == "best"
                        quantity_type = 0 if best else 1
                        stat_value = self.database.get_stat(stat, best, message.author.id)
                        readable_stat = QUANTITY_DESC[stat_index][quantity_type] + " " + stat
                        response = f"{message.author.name} has gotten {readable_stat} {stat_value} times."
                        await message.channel.send(response)
                    except (DatabaseError, OperationalError) as exception:
                        await message.channel.send("Something went wrong when querying the database! :fu:", self.config.log_error)
                        self.config.log(exception)
                else:
                    await message.channel.send(f"Not a valid stat: {second_command} :carole_fucking_baskin:")

    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None: # User joined.
            self.user_joined_voice(member)
        elif before.channel is not None and after.channel is None: # User left.
            self.user_left_voice(member)
