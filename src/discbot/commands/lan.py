from datetime import datetime
from time import time

import api.lan as lan_api
import api.util as api_util
from api.awards import get_intfar_reasons, get_doinks_reasons, organize_intfar_stats, organize_doinks_stats
from discbot.commands.base import *

_GAME = "lol"

class BaseLANCommand(Command):
    async def send_lan_not_started_msg(self):
        now_dt = datetime.now()
        lan_start = lan_api.LAN_PARTIES[lan_api.LATEST_LAN_PARTY].start_time
        lan_dt = datetime.fromtimestamp(lan_start)
        duration = api_util.format_duration(now_dt, lan_dt)
        response = f"LAN is starting in `{duration}`! Check back then for cool stats " + "{emote_nazi}"
        await self.message.channel.send(self.client.insert_emotes(response))

    async def send_tally_messages(self, messages: List[Tuple[str]], event_name: str, for_all: bool):
        response = f"{event_name} awarded at this LAN:" if for_all else "At this LAN, "
        for data in messages:
            if for_all:
                response += "\n- "
            response += f"{data[0]}"

        await self.message.channel.send(self.client.insert_emotes(response))

class LANCommand(BaseLANCommand):
    NAME = "lan"
    DESCRIPTION = "Show information about how the current LAN is going."
    ACCESS_LEVEL = "all"
    GUILDS = [GUILD_MAP["core"]]

    async def handle(self):
        lan_party = lan_api.LAN_PARTIES[lan_api.LATEST_LAN_PARTY]
        if time() < lan_party.start_time:
            await self.send_lan_not_started_msg()
            return

        database = self.client.game_databases[_GAME]

        # General info about how the current LAN is going.
        games_stats = database.get_games_count(
            time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
        )

        if games_stats is None:
            response = "No games have been played yet!"
        else:
            games_played, first_game_timestamp, games_won, _ = games_stats
            pct_won = (games_won / games_played) * 100

            dt_start = datetime.fromtimestamp(first_game_timestamp)
            dt_now = datetime.now()
            if dt_now.timestamp() > lan_party.end_time:
                dt_now = datetime.fromtimestamp(lan_party.end_time)

            duration = api_util.format_duration(dt_start, dt_now)

            champs_played = len(
                database.get_played_ids(
                    time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
                )
            )

            intfars = database.get_intfar_count(
                time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
            )
            doinks = database.get_doinks_count(
                time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
            )[1]

            longest_game_duration, longest_game_time = database.get_longest_game(
                time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
            )
            longest_game_start = datetime.fromtimestamp(longest_game_time)
            longest_game_end = datetime.fromtimestamp(longest_game_time + longest_game_duration)
            longest_game = api_util.format_duration(longest_game_start, longest_game_end)

            response = (
                "At this LAN:\n" +
                f"- We have been clapping cheeks for **{duration}**\n" +
                f"- **{games_played}** games have been played (**{pct_won:.2f}%** was won)\n" +
                f"- **{intfars}** Int-Far awards have been given\n"
                f"- **{doinks}** Doinks have been awarded\n"
                f"- **{champs_played}** unique champs have been played\n"
                f"- **{longest_game}** was the duration of the longest game"
            )

        await self.message.channel.send(response)

class LANPerformanceCommand(BaseLANCommand):
    NAME = "lan_performance"
    DESCRIPTION = "Show the performance of you (or someone else) at the current LAN."
    ACCESS_LEVEL = "all"
    OPTIONAL_PARAMS = [TargetParam("person")]
    GUILDS = [GUILD_MAP["core"]]

    async def handle(self, target_id: int):
        lan_party = lan_api.LAN_PARTIES[lan_api.LATEST_LAN_PARTY]
        if time() < lan_party.start_time:
            await self.send_lan_not_started_msg()
            return

        # Info about various stats for a person at the current LAN.
        all_avg_stats, all_ranks = lan_api.get_average_stats(self.client.game_databases[_GAME], lan_party)

        if all_avg_stats is None:
            response = "No games have yet been played at this LAN."
            await self.message.channel.send(response)
            return

        name = self.client.get_discord_nick(target_id, self.message.guild.id)

        response = f"At this LAN, {name} has the following average stats:"

        for stat_name in all_avg_stats:
            stats = all_avg_stats[stat_name]

            user_value = None
            user_rank = 0
            for index, (disc_id, stat_value) in enumerate(stats):
                if disc_id == target_id:
                    if stat_name in ("Damage to champs", "Gold earned"):
                        stat_value = int(stat_value)
                    user_value = api_util.round_digits(stat_value)
                    user_rank = index + 1

            response += f"\n{stat_name}: **{user_value}** (rank **{user_rank}**/**5**)"

        user_total_rank = 0
        for index, rank_data in enumerate(all_ranks):
            if rank_data[0] == target_id:
                user_total_rank = index + 1
                break

        response += "\n---------------------------------------------"
        response += f"\nTotal rank: **{user_total_rank}**/**5**"

        await self.message.channel.send(response)


class LANIntfarCommand(BaseLANCommand):
    NAME = "lan_intfar"
    DESCRIPTION = (
        "Show how many Int-Fars you (or someone else) has gotten at the current LAN."
    )
    TARGET_ALL = True
    ACCESS_LEVEL = "all"
    OPTIONAL_PARAMS = [TargetParam("person")]
    GUILDS = [GUILD_MAP["core"]]

    def _format_intfar(self, disc_id: int, expanded: bool):
        database = self.client.game_databases[_GAME]
        lan_party = lan_api.LAN_PARTIES[lan_api.LATEST_LAN_PARTY]
        person_to_check = self.client.get_discord_nick(disc_id, self.message.guild.id)

        games_played, intfar_reason_ids = database.get_intfar_stats(
            disc_id, time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
        )
        games_played, intfars, intfar_counts, pct_intfar = organize_intfar_stats(_GAME, games_played, intfar_reason_ids)

        if expanded:
            msg = f"{person_to_check} has been "
        else:
            msg = f"{person_to_check}: "

        msg += f"Int-Far **{intfars}** time"
        if intfars != 1:
            msg += "s"
        msg += f" **({pct_intfar:.2f}%** of {games_played} games) "

        intfar_reasons = get_intfar_reasons(_GAME)

        if expanded and intfars > 0:
            msg += "\nInt-Fars awarded so far:"
            for reason_id, reason in enumerate(intfar_reasons.values()):
                msg += f"\n- {reason}: **{intfar_counts[reason_id]}**"

        return msg, intfars, pct_intfar

    async def handle(self, target_id: int = None):
        lan_party = lan_api.LAN_PARTIES[lan_api.LATEST_LAN_PARTY]
        if time() < lan_party.start_time:
            await self.send_lan_not_started_msg()
            return

        targets = lan_party.participants if target_id is None else [target_id]
        messages = []
        for target in targets:
            resp_str, intfars, pct = self._format_intfar(target, target_id is not None)
            messages.append((resp_str, intfars, pct))
        
        messages.sort(key=lambda x: (x[1], x[2]), reverse=True)

        await self.send_tally_messages(messages, "Int-Fars", target_id is None)

class LANDoinksCommand(BaseLANCommand):
    NAME = "lan_doinks"
    DESCRIPTION = (
        "Show how many Doinks you (or someone else) has gotten at the current LAN."
    )
    TARGET_ALL = True
    ACCESS_LEVEL = "all"
    OPTIONAL_PARAMS = [TargetParam("person")]
    GUILDS = [GUILD_MAP["core"]]

    def _format_doinks(self, disc_id: int, expanded: bool):
        database = self.client.game_databases[_GAME]
        lan_party = lan_api.LAN_PARTIES[lan_api.LATEST_LAN_PARTY]
        person_to_check = self.client.get_discord_nick(disc_id, self.message.guild.id)

        doinks_reason_ids = database.get_doinks_stats(
            disc_id, time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
        )
        total_doinks = database.get_doinks_count(
            disc_id, time_after=lan_party.start_time, time_before=lan_party.end_time, guild_id=lan_party.guild_id
        )[1]
        doinks_counts = organize_doinks_stats(_GAME, doinks_reason_ids)

        if expanded:
            msg = f"{person_to_check} has earned "
        else:
            msg = f"{person_to_check}: "

        msg += f"{total_doinks} " + "{emote_Doinks}"

        doinks_reasons = get_doinks_reasons(_GAME)

        if expanded and total_doinks > 0:
            msg += "\nBig doinks awarded so far:"
            for reason_id, reason in enumerate(doinks_reasons):
                msg += f"\n - {reason}: **{doinks_counts[reason_id]}**"

        return msg, total_doinks

    async def handle(self, target_id: int = None):
        lan_party = lan_api.LAN_PARTIES[lan_api.LATEST_LAN_PARTY]
        if time() < lan_party.start_time:
            await self.send_lan_not_started_msg()
            return

        targets = lan_party.participants if target_id is None else [target_id]
        messages = []
        for target in targets:
            resp_str, doinks = self._format_doinks(target, target_id is not None)
            messages.append((resp_str, doinks))

        messages.sort(key=lambda x: x[1], reverse=True)

        await self.send_tally_messages(messages, "Doinks", target_id is None)

class JeopardyJoinCommand(BaseLANCommand):
    NAME = "jeopardy"
    DESCRIPTION = "Join Jeopardy."
    ACCESS_LEVEL = "all"
    GUILDS = [GUILD_MAP["core"]]
    
    async def handle(self):
        author_id = self.message.author.id

        if not lan_api.is_lan_ongoing(datetime.now().timestamp(), self.message.guild.id):
            return

        client_secret = self.client.meta_database.get_client_secret(author_id)
        url = f"{api_util.get_website_link()}/jeopardy/{client_secret}"
        response_dm = "Go to this link to join Jeopardy!\n"
        response_dm += url

        mention = self.client.get_mention_str(author_id, self.message.guild.id)
        response_server = (
            f"Psst, {mention}, I sent you a DM with a secret link, "
            "where you can join Jeopardy {emote_peberno}"
        )

        await self.message.channel.send(self.client.insert_emotes(response_server))

        # Send DM to the user
        dm_sent = await self.client.send_dm(response_dm, author_id)
        if not dm_sent:
            await self.message.channel.send(
                "Error: DM Message could not be sent for some reason ;( try again!"
            )
