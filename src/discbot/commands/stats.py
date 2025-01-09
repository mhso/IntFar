from datetime import datetime
from time import time

from discord import Message
import api.util as api_util
from api.awards import get_intfar_reasons, get_doinks_reasons
from api.game_data import (
    get_stat_quantity_descriptions,
    stats_from_database,
    get_formatted_stat_names,
    get_formatted_stat_value
)
from api.game_data.cs2 import RANKS
from discbot.commands.misc import get_winrate
from discbot.commands.base import *
from discbot.discord_bot import DiscordClient

class StatsCommand(Command):
    NAME = "stats"
    DESCRIPTION = "Show a list of available stat keywords to check."
    OPTIONAL_PARAMS = [GameParam("game")]

    async def handle(self, game: str):
        game_name = api_util.SUPPORTED_GAMES[game]
        valid_stats = ", ".join(f"'{cmd}'" for cmd in get_stat_quantity_descriptions(game))
        response = f"**--- Valid stats for {game_name} ---**\n```"
        response += valid_stats
        response += "\n```"
        response += "You can use these stats with the following commands: "
        response += "`!average [stat]`, `!best [stat]`, or `!worst [stat]`"

        await self.message.channel.send(response)

class AverageCommand(Command):
    NAME = "average"
    DESCRIPTION = (
        "Show the average value for a stat for you (or someone else). "
        "Fx. `!average lol kda` to see your average KDA over all games. "
        "This command accepts different parameters for different games. "
        "For LoL, you can see KDA on champs (fx. `!average kda jhin`), "
        "for CS2, you can see KDA on maps (fx. `!average kda inferno`). "
        "(Minimum 10 total games is required to get average KDA)"
    )
    TARGET_ALL = True
    ACCESS_LEVEL = "self"
    MANDATORY_PARAMS = [CommandParam("stat")]
    OPTIONAL_PARAMS = [GameParam("game"), PlayableParam("champion_or_map"), TargetParam("person")]
    ALIASES = ["avg"]

    async def handle(self, stat: str, game: str, playable_id: int | str = None, disc_id: int = None):
        quantity_descs = get_stat_quantity_descriptions(game)
        if stat not in quantity_descs: # Check if the requested stat is a valid stat.
            emote = "{emote_carole_fucking_baskin}"
            response = f"Not a valid stat: '{stat}' {emote}. See `!stats` for a list of valid stats."
            await self.message.channel.send(self.client.insert_emotes(response))
            return

        playable_name = None
        if playable_id is not None:
            playable_name = self.client.api_clients[game].get_playable_name(playable_id)

        minimum_games = 10 if playable_id is None else 5
        values = self.client.game_databases[game].get_average_stat(stat, disc_id, playable_id, min_games=minimum_games)()

        for_all = disc_id is None
        readable_stat = stat.replace("_", " ")

        response = ""

        for index, (disc_id, avg_value, games) in enumerate(values):
            if for_all:
                response += "- "

            target_name = self.client.get_discord_nick(disc_id, self.message.guild.id)

            if avg_value is None:
                # No games or no games on the given champ/map.
                response += f"{target_name} has not yet played at least {minimum_games} games "

                if playable_id is not None:
                    response += f"on {playable_name} "

                response += "{emote_perker_nono}"

            elif stat == "first_blood":
                percent = f"{avg_value * 100:.2f}"
                response += f"{target_name} got first blood in **{percent}%** of **{games}** games "

                if playable_id is not None:
                    response += f"when playing **{playable_name}** "

                if not for_all:
                    response += "{emote_poggers}"

            elif stat == "rank":
                avg_rank = RANKS[int(avg_value)]
                response += f"{target_name}'s average rank is **{avg_rank}** in **{games}** games "

                if playable_name is not None:
                    response += f"when playing **{playable_name}** "

                if not for_all:
                    response += "{emote_poggers}"

            else:
                ratio = f"{avg_value:.2f}"
                response += f"{target_name} averages **{ratio}** {readable_stat} in **{games}** games "

                if playable_id is not None:
                    response += f"of playing **{playable_name}** "

                if not for_all:
                    response += "{emote_poggers}"

            if index < len(values) - 1:
                response += "\n"

        await self.message.channel.send(self.client.insert_emotes(response))

class BestOrWorstStatCommand(Command):
    TARGET_ALL = True
    ACCESS_LEVEL = "self"
    MANDATORY_PARAMS = [CommandParam("stat")]
    OPTIONAL_PARAMS = [GameParam("game"), TargetParam("person")]

    def __init__(self, client: DiscordClient, message: Message, best: bool):
        super().__init__(client, message)
        self.best = best

    async def handle(self, stat: str, game: str, target_id: int):
        """
        Get the highest or lowest value of the requested stat for the given player
        and write it to Discord. If target_id is None, instead gets the highest/lowest
        value of all time for the given stat.
        """
        stat_descs = get_stat_quantity_descriptions(game)
        if stat not in stat_descs: # Check if the requested stat is a valid stat.
            emote = "{emote_carole_fucking_baskin}"
            response = f"Not a valid stat: '{stat}' {emote}. See `!stats` for a list of valid stats."
            await self.message.channel.send(self.client.insert_emotes(response))
            return

        quantity_type = 0 if self.best else 1

        # Check whether to find the max or min of some value, when returning
        # 'his most/lowest [stat] ever was ... Usually highest is best,
        # lowest is worse, except with deaths, where the opposite is the case.
        maximize = not ((stat != "deaths") ^ self.best)

        # Get a readable description, such as 'most deaths' or 'lowest kp'.
        quantifier = stat_descs[stat][quantity_type]
        if quantifier is not None:
            readable_stat = quantifier + " " + stat
        else:
            readable_stat = stat

        readable_stat = readable_stat.replace("_", " ")

        response = ""
        check_all = target_id is None

        if check_all: # Get best/worst ever stat of everyone.
            (
                target_id, # <- Who got the highest/lowest stat ever
                min_or_max_value, # <- The highest/lowest value of the stat
                game_id # <- The game where it happened
            ) = self.client.game_databases[game].get_most_extreme_stat(stat, maximize)
        else:
            (
                stat_count, # <- How many times the stat has occured
                game_count, # <- How many games were the stat was relevant
                min_or_max_value, # <- Highest/lowest occurance of the stat value
                game_id
            ) = self.client.game_databases[game].get_best_or_worst_stat(stat, target_id, maximize)()

        recepient = self.client.get_discord_nick(target_id, self.message.guild.id)

        game_summary = None
        if min_or_max_value is not None and game_id is not None:
            min_or_max_value = api_util.round_digits(min_or_max_value)
            game_summary = self.get_game_summary(game, game_id, target_id, self.message.guild.id)

        emote_to_use = "{emote_pog}" if self.best else "{emote_peberno}"

        if check_all:
            if stat == "first_blood":
                quant = "most" if self.best else "least"
                response = f"The person who has gotten first blood the {quant} "
                response += f"is {recepient} with **{min_or_max_value}** games"
                response += self.client.insert_emotes(emote_to_use)
            else:
                response = f"The {readable_stat} ever in a game was **{min_or_max_value}** "
                response += f"by {recepient} " + self.client.insert_emotes(emote_to_use)
                if game_summary is not None:
                    response += f"\nHe got this when playing {game_summary}"
        else:
            played_id, played_count = self.client.game_databases[game].get_played_count_for_stat(
                stat, maximize, target_id
            )

            played_name = self.client.api_clients[game].get_playable_name(played_id)
            if game == "lol":
                played_type = "champion"
            elif game == "cs2":
                played_type = "map"

            game_specific_desc = f"The {played_type} he most often gets {readable_stat} on is **{played_name}** (**{played_count}** games)\n"

            response = (
                f"{recepient} has gotten {readable_stat} in a game " +
                f"**{stat_count}** times out of **{game_count}** games played " + self.client.insert_emotes(emote_to_use) + "\n"
                f"{game_specific_desc}"
            )
            if min_or_max_value is not None:
                # The target user has gotten most/fewest of 'stat' in at least one game.
                response += f"His {readable_stat} ever was "
                response += f"**{min_or_max_value}** when playing {game_summary}"

        await self.message.channel.send(response)

    def get_game_summary(self, game: str, game_id: int, target_id: int, guild_id: int) -> str:
        """
        Return a string describing the outcome of the game with the given game_id,
        for the given player, in the given guild.
        """
        game_stats = stats_from_database(
            game,
            self.client.game_databases[game],
            self.client.api_clients[game],
            guild_id,
            game_id,
        )[0]
        return game_stats.get_finished_game_summary(target_id)

class BestStatCommand(BestOrWorstStatCommand):
    NAME = "best"
    DESCRIPTION = (
        "Show how many times you (or someone else) "
        "were the best in the specific stat. "
        "Fx. `!best lol kda` shows how many times you had the best KDA in a LoL game. "
        "`!best [game] [stat] all` shows what the best ever was for that stat, and who got it."
    )
    ALIASES = ["most", "highest"]

    def __init__(self, client: DiscordClient, message: Message):
        super().__init__(client, message, True)

class WorstStatCommand(BestOrWorstStatCommand):
    NAME = "worst"
    DESCRIPTION = (
        "Show how many times you (or someone else) "
        "were the worst at the specific stat. "
        "Fx. `!worst lol kda` shows how many times you had the worst KDA in a LoL game. "
        "`!worst [game] [stat] all` shows what the worst ever was for that stat, and who got it."
    )
    ALIASES = ["least", "lowest", "fewest"]

    def __init__(self, client: DiscordClient, message: Message):
        super().__init__(client, message, False)

class MatchHistoryCommand(Command):
    NAME = "match_history"
    DESCRIPTION = (
        "See the match history of you (or someone else) for the given game."
    )
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = [GameParam("game"), TargetParam("person")]

    async def handle(self, game: str, target_id: int = None):
        formatted_stat_names = get_formatted_stat_names(game)

        all_game_stats = stats_from_database(
            game,
            self.client.game_databases[game],
            self.client.api_clients[game],
            self.message.guild.id,
        )

        formatted_entries = []
        for game_stats in all_game_stats:
            date = datetime.fromtimestamp(game_stats.timestamp).strftime("%Y/%m/%d")
            dt_1 = datetime.fromtimestamp(time())
            dt_2 = datetime.fromtimestamp(time() + game_stats.duration)
            fmt_duration = api_util.format_duration(dt_1, dt_2)

            player_stats = game_stats.find_player_stats(target_id, game_stats.filtered_player_stats)

            if player_stats is None: # Target player was not in the game
                continue

            if game == "lol":
                map_or_champ = f"{player_stats.champ_name}"
                if player_stats.role is not None:
                    role = get_formatted_stat_value("lol", "role", player_stats.role)
                    map_or_champ += f" {role}"
            else:
                map_or_champ = game_stats.map_name

            win_str = "Won" if game_stats.win == 1 else "Lost"

            # Int-Far description
            if game_stats.intfar_id == target_id:
                reasons = " and ".join(
                    f"**{r}**" for c, r in zip(
                        game_stats.intfar_reason, get_intfar_reasons(game).values()
                    )
                    if c == "1"
                )
                intfar_description = f"Int-Far for {reasons}"
            else:
                intfar_description = "Not **Int-Far**"

            # Doinks description
            if player_stats.doinks is not None:
                reasons = " and ".join(
                    f"**{r}**" for c, r in zip(
                        player_stats.doinks, get_doinks_reasons(game).values()
                    )
                    if c == "1"
                )
                doinks_description = f"Big Doinks for {reasons}"
            else:
                emote = self.client.insert_emotes("{emote_Doinks}")
                doinks_description = f"No {emote}"

            match_str = (
                f"- **{win_str}** in **{fmt_duration}** on **{date}** playing **{map_or_champ}**\n"
                f"- {doinks_description}\n"
                f"- {intfar_description}\n"
                "```css\n"
            )

            # Get the formatted stat names and stat values and figure out the max width
            # of the stat names to pad all stat entries to the same width
            formatted_stats = []
            formatted_values = []
            for stat in formatted_stat_names:
                if stat in ("game_id", "player_id", "doinks"):
                    continue

                fmt_stat = formatted_stat_names[stat]
                fmt_value = get_formatted_stat_value(game, stat, player_stats.__dict__[stat])

                formatted_stats.append(fmt_stat)
                formatted_values.append(fmt_value)

            max_width = max(len(s) for s in formatted_stats)

            for stat, value in zip(formatted_stats, formatted_values):
                padding = " " * (max_width - len(stat))

                match_str += f"\n{stat}:{padding} {value}"

            match_str += "\n```"

            formatted_entries.append(match_str)

        header = f"--- Match history for **{api_util.SUPPORTED_GAMES[game]}** ---"

        await self.client.paginate(self.message.channel, formatted_entries, 0, 1, header)

class ChampionCommand(Command):
    NAME = "champion"
    DESCRIPTION = "Show your or someone else's stats on a specific champion."
    ACCESS_LEVEL = "self"
    MANDATORY_PARAMS = [PlayableParam("champion")]
    OPTIONAL_PARAMS = [GameParam("game"), TargetParam("person")]
    ALIASES = ["champ"]

    async def handle(self, champ_id: str, game: str, target_id: int):
        if champ_id is None:
            await self.message.channel.send(f"Champion is not valid.")
            return

        with self.client.game_databases["lol"] as database:
            champ_name, winrate, games = get_winrate(self.client, champ_id, game, target_id)
            user_name = self.client.get_discord_nick(target_id, self.message.guild.id)

            if winrate is None or games == 0:
                response = f"{user_name} has not played enough games on {champ_name}."
                await self.message.channel.send(response)
                return

            doinks = database.get_played_doinks_count(target_id, champ_id)()
            intfars = database.get_played_intfar_count(target_id, champ_id)()

            response = f"Stats for {user_name} on *{champ_name}*:\n"
            response += f"Winrate: **{winrate:.2f}%** in **{int(games)}** games.\n"
            response += f"Doinks: **{doinks}**\n"
            response += f"Int-Fars: **{intfars}**\n"

            stats_to_get = [
                "kills",
                "deaths",
                "assists",
                "kda",
                "cs",
                "cs_per_min",
                "damage",
                "gold",
                "vision_score",
                "vision_wards"
            ]

            show_best = not self.message.author.is_on_mobile()

            if show_best:
                text_rows = [
                    ["Stat", "Value", "Self", "Other", "All", "Best"]
                ]
            else:
                text_rows = ["Stat", "Value", "S", "O", "A"]

            stats = {
                stat: get_formatted_stat_value(
                    game,
                    stat,
                    database.get_average_stat(stat, target_id, champ_id, min_games=1)()[0][1]
                )
                for stat in stats_to_get
            }

            min_games = 5

            if games < min_games:
                response += (
                    f"Can't display stat rankings on {champ_name}, "
                    f"because {user_name} has not played at least {min_games} games with them."
                )
                await self.message.channel.send(response)
                return

            totals = []
            formatted_stat_names = get_formatted_stat_names(game)
            for index, stat in enumerate(stats):
                stat_name = formatted_stat_names[stat]
                if stat == "vision_score":
                    stat_name = "Vision"
                elif stat == "vision_wards":
                    stat_name = "Pinks"
                elif stat == "cs_per_min":
                    stat_name = "CS/Min"

                row = [f"{stat_name}", f"{stats[stat]}"]
                best_at_champ = None

                for comparison in range(1, 4):
                    rank, best_id, total = database.get_average_stat_rank(
                        stat, target_id, champ_id, comparison, min_games
                    )()
                    row.append(str(rank))

                    if index == 0:
                        totals.append(total)
                    if comparison == 2:
                        best_at_champ = best_id

                if show_best:
                    best_name = self.client.get_discord_nick(best_at_champ, self.message.guild.id)
                    row.append(best_name)

                text_rows.append(row)

        col_lengths = [max(len(row[col]) for row in text_rows) for col in range(len(text_rows[0]))]
        response += "```css\n"
        for row_index, row in enumerate(text_rows):
            if row_index == 1:
                response += "-" * (sum(col_lengths) + len(row[0]) * 3) + "\n"

            for col_index, entry in enumerate(row):
                padding = col_lengths[col_index] - len(entry)
                response += entry + " " * padding
                if col_index < len(row) - 1:
                    response += " | "

            response += "\n"

        person = "person" if totals[1] - 1 == 1 else "people"

        response += "```\n"
        response += f"**{text_rows[0][2]}**: Rank compared to {user_name}'s **{totals[0]}*** other champs played\n"
        response += f"**{text_rows[0][3]}**: Rank compared to **{totals[1] - 1}*** other {person} playing {champ_name}\n"
        response += f"**{text_rows[0][4]}**: Rank compared to **{totals[2]}*** other people playing any champ\n"
        if show_best:
            response += f"**Best**: Who has the best rank on a stat with {champ_name}\n"
        response += f"*A minimum of **{min_games}** games on a champ is required"

        await self.message.channel.send(response)

class RankCommand(Command):
    NAME = "rank"
    DESCRIPTION = "Show your current rank in the given game."
    MANDATORY_PARAMS = [CommandParam("queue")]
    OPTIONAL_PARAMS = [GameParam("game"), TargetParam("person")]

    async def handle(self, queue: str, game: str, target_id: int):
        nickname = self.client.get_discord_nick(target_id, self.message.guild.id)
        rank_info = self.client.game_databases[game].get_current_rank(target_id)
        fmt_stat_names = get_formatted_stat_names(game)

        if game == "lol":
            queues = ["solo", "flex"]
            queue_names = [fmt_stat_names["rank_solo"], fmt_stat_names["rank_flex"]]
        elif game == "cs2":
            queues = ["premier"]
            queue_names = [fmt_stat_names["rank_premier"]]

        if queue not in queues:
            response = f"Invalid rank type, should be one of {', '.join(queues)}."
            await self.message.channel.send(response)
            return

        rank = get_formatted_stat_value(game, f"rank_{queue}", rank_info[queues.index(queue)])
        name = queue_names[queues.index(queue)]

        response = f"{nickname} is currently **{rank}** in **{name}**"

        await self.message.channel.send(response)
