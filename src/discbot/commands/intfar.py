import api.util as api_util
from api.awards import get_intfar_reasons, get_intfar_criterias_desc, organize_intfar_stats
from discbot.commands.base import *

def get_intfar_relation_stats(client: DiscordClient, game: str, target_id: int):
    database = client.game_databases[game]
    data = []
    games_relations, intfars_relations = database.get_intfar_relations(target_id)
    total_intfars = len(database.get_intfar_stats(target_id)[1])
    for disc_id, total_games in games_relations.items():
        intfars = intfars_relations.get(disc_id, 0)
        data.append(
            (
                disc_id, total_games, intfars, int((intfars / total_intfars) * 100),
                int((intfars / total_games) * 100)
            )
        )

    return sorted(data, key=lambda x: x[2], reverse=True)

class IntfarCommand(Command):
    NAME = "intfar"
    DESCRIPTION = (
        "Show how many times you (or someone else) has been the Int-Far. " +
        "`!intfar [game] all` lists Int-Far stats for all users for the given game."
    )
    TARGET_ALL = True
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = [GameParam("game"), TargetParam("person")]

    async def handle(self, game, target_id):
        database = self.client.game_databases[game]
        current_month = api_util.current_month()
        intfar_reasons = get_intfar_reasons(game)

        def format_for_all(disc_id, monthly=False):
            person_to_check = self.client.get_discord_nick(disc_id, self.message.guild.id)
            games_played, intfar_reason_ids = database.get_intfar_stats(disc_id, monthly)
            games_played, intfars, _, pct_intfar = organize_intfar_stats(game, games_played, intfar_reason_ids)
            msg = f"{person_to_check}: Int-Far **{intfars}** times "
            msg += f"**({pct_intfar:.2f}%** of {games_played} games) "
            msg = self.client.insert_emotes(msg)
            return msg, intfars, pct_intfar, games_played

        def format_for_single(disc_id):
            person_to_check = self.client.get_discord_nick(disc_id, self.message.guild.id)
            games_played, intfar_reason_ids = database.get_intfar_stats(disc_id, False)
            games_played, intfars, intfar_counts, pct_intfar = organize_intfar_stats(game, games_played, intfar_reason_ids)
            intfars_of_the_month = database.get_intfars_of_the_month()
            user_is_ifotm = intfars_of_the_month != [] and intfars_of_the_month[0][0] == disc_id

            played_id, played_count = database.get_played_with_most_intfars(disc_id)()
            if game == "lol":
                played_name = self.client.api_clients["lol"].get_champ_name(played_id)
            elif game == "cs2":
                played_name = self.client.api_clients["cs2"].get_map_name(played_id)

            msg = f"{person_to_check} has been Int-Far **{intfars}** times "
            msg += "{emote_unlimited_chins}"
            if intfars > 0:
                monthly_games, monthly_infar_ids = database.get_intfar_stats(disc_id, True)
                monthly_games, monthly_intfars, _, pct_monthly = organize_intfar_stats(game, monthly_games, monthly_infar_ids)

                ratio_desc = f"\nHe has inted the most when playing **{played_name}** (**{played_count}** times).\n"
                ratio_desc += f"In total, he was Int-Far in **{pct_intfar:.2f}%** of his "
                ratio_desc += f"{games_played} games played.\n"
                ratio_desc += f"In {current_month}, he was Int-Far in **{monthly_intfars}** "
                ratio_desc += f"of his {monthly_games} games played (**{pct_monthly:.2f}%**).\n"

                reason_desc = "Int-Fars awarded so far:\n"
                for reason_id, reason in enumerate(intfar_reasons):
                    reason_desc += f"- {reason}: **{intfar_counts[reason_id]}**\n"

                longest_streak, date_ended = database.get_longest_intfar_streak(disc_id)
                streak_desc = f"His longest Int-Far streak was **{longest_streak}** games in a row "
                if date_ended is not None:
                    streak_desc += f"(ended **{date_ended}**) "
                streak_desc += "{emote_suk_a_hotdok}\n"

                longest_non_streak, date_ended = database.get_longest_no_intfar_streak(disc_id)
                no_streak_desc = f"His longest streak of *not* being Int-Far was **{longest_non_streak}** games in a row "
                if date_ended is not None:
                    no_streak_desc += f"(ended **{date_ended})** "
                no_streak_desc += "{emote_pog}\n"

                relations_data = get_intfar_relation_stats(self.client, game, disc_id)[0]
                most_intfars_nick = self.client.get_discord_nick(relations_data[0], self.message.guild.id)
                relations_desc = f"He has inted the most when playing with {most_intfars_nick} "
                relations_desc += f"where he inted **{relations_data[2]}** games (out of a total **{relations_data[1]}** "
                relations_desc += f"games played with this person, equal to **{relations_data[3]}%** of all games)"
                relations_desc += "{emote_smol_gual}"

                msg += ratio_desc + reason_desc + streak_desc + no_streak_desc + relations_desc
                if user_is_ifotm:
                    msg += f"\n**{person_to_check} currently stands to be Int-Far of the Month "
                    msg += f"of {current_month}!** :tada:"

            msg = self.client.insert_emotes(msg)
            return msg

        response = ""
        if target_id is None: # Check intfar stats for everyone.
            messages_all_time = []
            messages_monthly = []
            for disc_id in database.game_users.keys():
                resp_str_all_time, intfars, pct_all_time, _ = format_for_all(disc_id)
                resp_str_month, intfars_month, pct_month, games_played = format_for_all(disc_id, monthly=True)

                messages_all_time.append((resp_str_all_time, intfars, pct_all_time))
                if games_played > 0: # Don't include users with no games this month.
                    messages_monthly.append((resp_str_month, intfars_month, pct_month))

            messages_all_time.sort(key=lambda x: (x[1], x[2]), reverse=True)
            messages_monthly.sort(key=lambda x: (x[1], x[2]), reverse=True)

            response = "**--- All time stats ---**"
            for data in messages_all_time:
                response += f"\n- {data[0]}"

            await self.message.channel.send(response)

            response = f"**--- Stats for {current_month} ---**"

            if len(messages_monthly) == 0: # No games this month
                response += "\nNo one has played any games (yet) this month."
            else:
                for data in messages_monthly:
                    response += f"\n- {data[0]}"

        else: # Check intfar stats for a specific person.
            response = format_for_single(target_id)

        await self.message.channel.send(response)

class IntfarRelationsCommand(Command):
    NAME = "intfar_relations"
    DESCRIPTION = "Show who you (or someone else) int the most games with."
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = [GameParam("game"), TargetParam("person")]

    async def handle(self, game: str, target_id: int):
        data = get_intfar_relation_stats(self.client, game, target_id)

        response = (
            f"Breakdown of players {self.client.get_discord_nick(target_id, self.message.guild.id)} "
            "has inted with:\n"
        )
        for disc_id, total_games, intfars, intfar_ratio, games_ratio in data:
            nick = self.client.get_discord_nick(disc_id, self.message.guild.id)
            response += f"- {nick}: **{intfars}** times (**{intfar_ratio}%**) "
            response += f"(**{games_ratio}%** of **{total_games}** games)\n"

        await self.message.channel.send(response)

class IntfarCriteriaCommand(Command):
    NAME = "intfar_criteria"
    DESCRIPTION = (
        "List the things that need to happen for a person to get " +
        "Int-Far because of a specific criteria. Fx. `!intfar_criteria lol kda`."
    )
    OPTIONAL_PARAMS = [GameParam("game"), CommandParam("criteria")]

    async def handle(self, game: str, criteria: str = None):
        intfar_reasons = get_intfar_reasons(game)
        intfar_criterias = get_intfar_criterias_desc(game)
        valid_criteria = criteria in intfar_criterias
        game_name = api_util.SUPPORTED_GAMES[game]

        if criteria is not None and not valid_criteria:
            response = f"Not a valid criteria: '{criteria}', should be one of: {', '.join(intfar_reasons)}"
            await self.message.channel.send(response)
            return

        if valid_criteria:
            response = f"Criteria for being Int-Far in {game_name} by {intfar_reasons[criteria]}:"
            for line in intfar_criterias[criteria]:
                response += f"\n- {line}"
        else:
            response = f"Possible criterias for getting Int-Far in {game_name}:\n"
            for reason in intfar_reasons:
                response += f"- **{reason}**: {intfar_reasons[reason]}\n"

            response += "Write `!intfar_criteria [reason] to see more specific criteria."

        if valid_criteria:
            response += "\nThese criteria must **all** be met to be Int-Far."

        await self.message.channel.send(response)
