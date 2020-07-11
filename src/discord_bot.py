import random
from time import time
from sqlite3 import DatabaseError, OperationalError
import asyncio
import discord
import riot_api
import game_stats

DISCORD_SERVER_ID = 619073595561213953
CHANNEL_ID = 730744358751567902

INTFAR_FLAVOR_TEXTS = [
    "And the Int-Far goes to... {nickname} {emote_hairy_retard} He wins for {reason}!",
    "Uh oh, stinky {emote_happy_nono}! {nickname} has been a very naughty boi! He is awarded one Int-Far token for {reason}!",
    "Oof {nickname}, better luck next time {emote_smol_dave} take this Int-Far award for {reason}!",
    "Oh heck {emote_morton} {nickname} did a fucky-wucky that game! He is awarded Int-Far for {reason}!",
    "Yikes {emote_big_dave} unlucko game from {nickname}. Accept this pity gift of being crowned Int-Far for {reason}.",
    "Some serious smol dick energy from {nickname} that game {emote_gual_yikes} have an Int-Far for {reason}.",
    "Welp... {nickname}, you really let everyone down on that one {emote_nat_really_fine} +1 Int-Far to you for {reason}!"
]

NO_INTFAR_FLAVOR_TEXTS = [
    "Hecking good job bois, no one inted their ass off that game {emote_uwucat}",
    "No one sucked enough to be crowned Int-Far that game! Big doinks all around {emote_big_doinks}",
    "Get outta my face bitch! BOW!! No Int-Far that game {emote_Bitcoinect}",
    "We are so god damn good at this game!! No inting = no problems {emote_main}",
    "Being this good is not easy, but damn do we pull it off well! No Int-Far that game {emote_swell}"
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

LOWEST_KP_FLAVORS = [
    "living on an island and getting {kp}% kill participation",
    "refusing to help his team, having a {kp}% kill participation",
    "doing TOO much social distancing with {kp}% kill participation"
]

LOWEST_VISION_FLAVORS = [
    "playing with a blindfold on with {visionScore} vision score",
    "hating winning with a vision score of {visionScore}",
    "loving enemy death brushes a bit too much with {visionScore} vision score"
]

VALID_COMMANDS = [
    "register", "users", "help", "commands", "intfar", "best", "worst"
]

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

class DiscordClient(discord.Client):
    def __init__(self, config, database):
        super().__init__()
        self.riot_api = riot_api.APIClient(config)
        self.config = config
        self.database = database
        self.active_users = []
        self.active_game = None
        self.channel_to_write = None
        self.initialized = False
        self.last_message_time = {}

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
                asyncio.create_task(self.poll_for_game_start())
            except Exception as e:
                print("Exception after game was over: " + str(e.with_traceback(e)))
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

    def intfar_by_kp(self, data, team_kills):
        """
        Returns the info of the Int-Far, if this person has very low kill participation.
        This is determined by:
            - Having the lowest KP in the group
            - KP being less than 30
            - Number of kills + assists being less than 10
        Returns None if none of these criteria matches a person.
        """
        intfar, stats = game_stats.get_outlier(data, "kp", total_kills=team_kills)
        lowest_kp = game_stats.calc_kill_participation(stats, team_kills)
        kills = stats["kills"]
        assists = stats["assists"]
        if lowest_kp < self.config.kp_lower_threshold and kills + assists < 10:
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
        if lowest_score < self.config.vision_score_lower_threshold and kda < 3:
            return (intfar, lowest_score)
        return (None, None)

    async def send_intfar_message(self, disc_id, reason):
        nickname = self.get_discord_nick(disc_id)
        if nickname is None:
            self.config.log(f"Int-Far Discord nickname could not be found! Discord ID: {disc_id}",
                            self.config.log_warning)
            nickname = f"Unknown (w/ discord ID '{disc_id}')"
        if reason is None:
            self.config.log(f"Int-Far reason was None!", self.config.log_warning)
            reason = "being really, really bad"
        message = get_intfar_flavor_text(nickname, reason)
        message = self.insert_emotes(message)
        await self.channel_to_write.send(message)

    def get_intfar_details(self, stats, team_kills):
        intfar_disc_id, kda = self.intfar_by_kda(stats)
        if intfar_disc_id is not None:
            self.config.log("Int-Far because of KDA.")
            return intfar_disc_id, get_reason_flavor_text(f"{kda:.2f}", "kda")

        intfar_disc_id, deaths = self.intfar_by_deaths(stats)
        if intfar_disc_id is not None:
            self.config.log("Int-Far because of deaths.")
            return intfar_disc_id, get_reason_flavor_text(str(deaths), "deaths")

        intfar_disc_id, kp = self.intfar_by_kp(stats, team_kills)
        if intfar_disc_id is not None:
            self.config.log("Int-Far because of kill participation.")
            return intfar_disc_id, get_reason_flavor_text(str(kp), "kp")

        intfar_disc_id, vision_score = self.intfar_by_vision_score(stats)
        if intfar_disc_id is not None:
            self.config.log("Int-Far because of vision score.")
            return intfar_disc_id, get_reason_flavor_text(str(vision_score), "visionScore")

        return None, None

    def get_filtered_stats(self, game_info):
        kills_per_team = {100: 0, 200: 0}
        our_team = 100
        filtered_stats = []
        for part_info in game_info["participantIdentities"]:
            for participant in game_info["participants"]:
                if part_info["participantId"] == participant["participantId"]:
                    kills_per_team[participant["teamId"]] += participant["stats"]["kills"]
                    for disc_id, _, summ_id in self.active_users:
                        if summ_id == part_info["player"]["summonerId"]:
                            our_team = participant["teamId"]
                            filtered_stats.append((disc_id, participant["stats"]))
        return filtered_stats, kills_per_team[our_team]

    async def declare_intfar(self): # Check final game status.
        game_info = self.riot_api.get_game_details(self.active_game, tries=2)
        filtered_stats, kills_by_our_team = self.get_filtered_stats(game_info)

        intfar_disc_id, reason = self.get_intfar_details(filtered_stats, kills_by_our_team)
        if intfar_disc_id is not None:
            await self.send_intfar_message(intfar_disc_id, reason)
        else:
            self.config.log("No Int-Far that game!")
            response = get_no_intfar_flavor_text()
            await self.channel_to_write.send(self.insert_emotes(response))

        try: # Save stats.
            self.database.record_stats(intfar_disc_id, self.active_game, filtered_stats, kills_by_our_team)
        except (DatabaseError, OperationalError) as exception:
            self.config.log("Game stats could not be saved!", self.config.log_error)
            self.config.log(exception)
            raise exception

        self.config.log("Game over! Stats were saved succesfully.")
        self.active_game = None

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
        if summoner_info is not None:
            self.active_users.remove(summoner_info)
            self.config.log("Summoner left voice: " + summoner_info[1])
            self.config.log(f"Active users: {len(self.active_users)}")

    async def test_stuff(self):
        game_id = 4699244357
        print("WE DOING IT", flush=True)
        self.active_users = [
            (347489125877809155, "Nønø", "vWqeigv3NlpebAwh309gZ8zWul9rNIv6zUKXGFeRWqih9ko"),
            (267401734513491969, "Senile Felines", "LRjsmujd76mwUe5ki-cOhcfrpAVsMpsLeA9BZqSl6bMiOI0"),
        ]
        #self.active_game = game_id
        self.config.status_interval = 10
        asyncio.create_task(self.poll_for_game_start())

    async def on_ready(self):
        if self.initialized:
            self.config.log("Ready was called, but bot was already initialized... Weird stuff.")
            return

        await self.change_presence(
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
                        start_polling = count == 1
                        await self.user_joined_voice(member, start_polling)
                        count += 1
                for text_channel in guild.text_channels:
                    if text_channel.id == CHANNEL_ID:
                        self.channel_to_write = text_channel
                        return

    async def handle_helper_msg(self, message):
        valid_stats = ", ".join("'" + cmd + "'" for cmd in STAT_COMMANDS)
        response = "I gotchu fam {emote_nazi}\n"
        response += "The Int-Far™ Tracker™ is a highly sophisticated bot "
        response += "that watches when people in this server plays League, "
        response += "and judges them harshly if they int too hard {emote_simp_but_closeup}\n"
        response += "**--- Valid commands, and their usages, are listed below ---**\n```"
        response += (
            "!register [summoner_name] - Sign up for the Int-Far™ Tracker™ " +
            "by providing your summoner name (fx. '!register imaqtpie').\n\n" +
            "!users - List all users who are currently signed up for the Int-Far™ Tracker™.\n\n" +
            "!help - Show this helper text.\n\n" +
            "!commands - Show this helper text.\n\n" +
            "!intfar (summoner_name) - Show how many times you (if no summoner name is included), " +
            "or someone else, has been the Int-Far. '!intfar all' lists Int-Far stats for all users.\n\n"
            "!best [stat] (summoner_name) - Show how many times you (or someone else) " +
            "were the best in the specific stat. " +
            "Fx. '!best kda' shows how many times you had the best KDA in a game.\n\n" +
            "!worst [stat] (summoner_name) - Show how many times you (or someone else) " +
            "were the worst at the specific stat.\n\n```" +
            "**--- Valid stats ---**\n```"
        )
        response += valid_stats
        response += "\n```"
        await message.channel.send(self.insert_emotes(response))

    async def handle_intfar_msg(self, message, target_name):
        def get_intfar_stats(disc_id):
            person_to_check = self.get_discord_nick(disc_id)
            stat_value = self.database.get_stat("int_far", "int_far", True, disc_id)[0]
            msg = f"{person_to_check} has been an Int-Far {stat_value} times "
            msg += self.insert_emotes("{emote_unlimited_chins}")
            return msg

        response = ""
        if target_name is not None: # Check intfar stats for someone else.
            if target_name == "all":
                for disc_id, _, _ in self.database.summoners:
                    response += "- " + get_intfar_stats(disc_id) + "\n"
            else:
                user_data = self.database.discord_id_from_summoner(target_name.strip())
                if user_data is None:
                    msg = f"Error: Invalid summoner name {self.get_emoji_by_name('PepeHands')}"
                    await message.channel.send(msg)
                    return
                response = get_intfar_stats(user_data[0])
        else: # Check intfar stats for the person sending the message.
            response = get_intfar_stats(message.author.id)

        await message.channel.send(response)

    async def handle_stat_msg(self, message, first_cmd, second_cmd, target_name):
        if second_cmd in STAT_COMMANDS:
            stat = second_cmd
            stat_index = STAT_COMMANDS.index(stat)
            self.config.log(f"Stat requested: {first_cmd} {stat}")
            try:
                best = first_cmd == "best"
                quantity_type = 0 if best else 1
                maximize = not ((stat != "deaths") ^ best)
                id_to_check = message.author.id
                recepient = message.author.name

                if target_name is not None: # Get someone else's stat information.
                    user_data = self.database.discord_id_from_summoner(target_name.strip())
                    if user_data is None:
                        msg = f"Error: Invalid summoner name {self.get_emoji_by_name('fu')}"
                        await message.channel.send(msg)
                        return
                    id_to_check = user_data[0]
                    recepient = self.get_discord_nick(id_to_check)

                stat_count, min_or_max_value, game_id = self.database.get_stat(stat + "_id", stat, best, id_to_check, maximize)
                game_info = self.riot_api.get_game_details(game_id)
                summ_id = self.database.summoner_from_discord_id(id_to_check)[2]
                game_summary = game_stats.get_game_summary(game_info, summ_id)

                readable_stat = QUANTITY_DESC[stat_index][quantity_type] + " " + stat

                response = (f"{recepient} has gotten {readable_stat} in a game " +
                            f"{stat_count} times " + self.insert_emotes("{emote_pog}") + "\n")
                if min_or_max_value is not None:
                    response += f"His {readable_stat} ever was {min_or_max_value} as {game_summary}"

                await message.channel.send(response)
            except (DatabaseError, OperationalError) as exception:
                response = self.insert_emotes("Something went wrong when querying the database! {emote_fu}")
                await message.channel.send(response, self.config.log_error)
                self.config.log(exception)
        else:
            response = self.insert_emotes(f"Not a valid stat: '{second_cmd}' " + "{emote_carole_fucking_baskin}")
            await message.channel.send(response)

    async def on_message(self, message):
        if message.author == self.user: # Ignore message since it was sent by us (the bot).
            return

        msg = message.content.strip()
        if msg.startswith("!"):
            split = msg.split(" ")
            first_command = split[0][1:]

            if first_command not in VALID_COMMANDS:
                return

            if time() - self.last_message_time.get(message.author.id, 0) < self.config.message_timeout:
                # Some guy is sending messages too fast!
                await message.channel.send("Slow down cowboy! You are sending messages real sped-like!")
                return

            second_command = None if len(split) < 2 else split[1]
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
                target_name = None
                if len(split) > 1:
                    target_name = " ".join(split[1:])
                await self.handle_intfar_msg(message, target_name)
            elif first_command in ("help", "commands"):
                await self.handle_helper_msg(message)
            elif first_command in ["worst", "best"] and len(split) > 1: # Get game stats.
                target_name = None
                if len(split) > 2:
                    target_name = " ".join(split[2:])
                await self.handle_stat_msg(message, first_command, second_command, target_name)

            self.last_message_time[message.author.id] = time()

    async def on_voice_state_update(self, member, before, after):
        if before.channel is None and after.channel is not None: # User joined.
            await self.user_joined_voice(member)
        elif before.channel is not None and after.channel is None: # User left.
            await self.user_left_voice(member)
