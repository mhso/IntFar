import random
from time import sleep
from sqlite3 import DatabaseError, OperationalError
import discord
import riot_api
import game_stats

DISCORD_SERVER_ID = 512363920044982272 # TODO: Change to actual server ID.
CHANNEL_ID = 123 # TODO: Change to actual channel ID.

INTFAR_FLAVOR_TEXTS = [
    "And the Int-Far goes to... {nickname}! He wins for {reason}!",
    "Uh oh, stinky! {nickname} has been a very naughty boi! He is awarded one Int-Far token for {reason}!",
    "Oof {nickname}, better luck next time! Take this Int-Far award for {reason}!",
    "Oh heck, {nickname} did a fucky-wucky that game! He is awarded Int-Far for {reason}!"
]

STAT_COMMANDS = {
    "kills": "most_kills", "deaths": "fewest_deaths", "kda": "highest_kda",
    "damage": "most_damage", "cs": "most_cs", "gold": "most_gold",
    "kp":"highest_kp", "vision": "highest_vision_score"
}

def get_intfar_flavor_text(nickname, reason):
    flavor_text = INTFAR_FLAVOR_TEXTS[random.randint(0, len(INTFAR_FLAVOR_TEXTS)-1)]
    return flavor_text.replace("{nickname}", nickname).replace("{reason}", reason)

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
        summ_id = self.riot_api.get_summoner_id(summ_name)
        if summ_id is None:
            return "Error: Invalid summoner name."
        self.database.add_user(summ_name, summ_id, discord_id)
        return f"User '{summ_name}' with ID '{summ_id}' succesfully added!"

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
        for guild in self.guilds:
            if guild.id == DISCORD_SERVER_ID:
                for member in guild.members:
                    if member.id == disc_id:
                        return member.nick
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
            return intfar_disc_id, f"having a tragic KDA of {kda}"
        
        intfar_disc_id, deaths = self.intfar_by_deaths(stats)
        if intfar_disc_id is not None:
            return intfar_disc_id, f"dying a total of {deaths} times"

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
            command = split[0][1:]
            if command == "register":
                if len(split) > 1:
                    summ_name = "%20".join(split[1:])
                    status = self.add_user(summ_name, message.author.id)
                    await message.channel.send(status)
            elif command in STAT_COMMANDS: # Get game stats.
                stat = STAT_COMMANDS[command]
                self.config.log(f"Stat requested: {stat}")
                try:
                    stat_value = self.database.get_stat(stat, message.author.id)
                    readable_stat = stat.replace("_", " ")
                    response = f"{message.author.nick} has gotten {readable_stat} {stat_value} times."
                    await message.channel.send(response)
                except (DatabaseError, OperationalError) as exception:
                    await message.channel.send("Something went wrong when querying the database!", self.config.log_error)
                    self.config.log(exception)

    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None: # User joined.
            self.user_joined_voice(member)
        elif before.channel is not None and after.channel is None: # User left.
            self.user_left_voice(member)
