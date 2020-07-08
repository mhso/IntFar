import random
import discord
import riot_api

DISCORD_SERVER_ID = 512363920044982272 # TODO: Change to real ID.
CHANNEL_ID = 123 # TODO: Change to real ID.

INTFAR_FLAVOR_TEXTS = [
    "And the Int Far goes to... {nickname}! For {reason}!",
    "{nickname} has been a very naughty boi! He is awarded one Int Far token for {reason}!",
    "Oof {nickname}, better luck next time! Take this Int Far award for {reason}!"
]

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
            return False

        if active_game is not None and self.active_game is None:
            self.active_game = active_game
            self.config.status_interval = 30 # Check status every 30 seconds.
            return False
        elif active_game is None and self.active_game is not None: # The current game is over.
            self.config.status_interval = 60*10
            return True

    def get_discord_nick(self, disc_id):
        for guild in self.guilds:
            if guild.id == DISCORD_SERVER_ID:
                for member in guild.members:
                    if member.id == disc_id:
                        return member.nick
        return None

    def intfar_by_kda(self, data):
        def calc_kda(data_entry):
            stats = data_entry[1]
            return (stats["kills"] + stats["assists"]) / stats["deaths"]

        sorted_by_kda = sorted(data, key=calc_kda)
        return (sorted_by_kda[0][0], calc_kda(sorted_by_kda[0])
                if sorted_by_kda[0] < self.config.kda_lower_threshold
                else None)

    async def send_intfar_message(self, disc_id, reason):
        nickname = self.get_discord_nick(disc_id)
        message = get_intfar_flavor_text(nickname, reason)
        await self.channel_to_write.send(message)

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

        intfar_disc_id, lowest_kda = self.intfar_by_kda(filtered_stats)
        if intfar_disc_id is not None:
            self.send_intfar_message(intfar_disc_id, f"having a tragic KDA of {lowest_kda}")

        self.active_game = None
        self.config.log("Game over!")

    def user_joined_voice(self, member):
        self.config.log("User joined voice: " + str(member.id))
        summoner_info = self.database.summoner_from_discord_id(member.id)
        if summoner_info is not None:
            self.active_users.append(summoner_info)
            self.config.log("Summoner joined voice: " + summoner_info[1])
            if self.polling_is_active():
                self.config.log("Polling is now active!")

    def user_left_voice(self, member):
        self.config.log("User left voice: " + str(member.id))
        summoner_info = self.database.summoner_from_discord_id(member.id)
        if summoner_info is not None:
            self.active_users.remove(summoner_info)
            self.config.log("Summoner left voice: " + summoner_info[1])

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
        if message.author == self.user: # Message was sent by us (the bot).
            return

        msg = message.content.strip()
        if msg.startswith("!register"):
            split = msg.split(" ")
            if len(split) > 1:
                summ_name = "%20".join(split[1:])
                status = self.add_user(summ_name, message.author.id)
                await message.channel.send(status)

    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None: # User joined.
            self.user_joined_voice(member)
        elif before.channel is not None and after.channel is None: # User left.
            self.user_left_voice(member)
