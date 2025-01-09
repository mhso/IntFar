from api.util import SUPPORTED_GAMES
from api.awards import get_doinks_reasons, organize_doinks_stats
from discbot.commands.base import *

class DoinksCommand(Command):
    NAME = "doinks"
    DESCRIPTION = (
        "Show big doinks plays that you (or someone else) did! " +
        "`!doinks [game] all` lists all doinks stats for all users for the given game."
    )
    TARGET_ALL = True
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = [GameParam("game"), TargetParam("person")]

    async def handle(self, game: str, target_id: int):
        database = self.client.game_databases[game]
        doinks_reasons = get_doinks_reasons(game)

        def get_doinks_stats(disc_id, expanded=True):
            person_to_check = self.client.get_discord_nick(disc_id, self.message.guild.id)
            doinks_reason_ids = database.get_doinks_stats(disc_id)
            total_doinks = database.get_doinks_count(disc_id)[1]
            doinks_counts = organize_doinks_stats(game, doinks_reason_ids)

            played_id, played_count = database.get_played_with_most_doinks(disc_id)()
            played_name = self.client.api_clients[game].get_playable_name(played_id)

            msg = f"{person_to_check} has earned {total_doinks} " + "{emote_Doinks}"
            if expanded and total_doinks > 0:
                msg += "\nHe has earned the most {emote_Doinks} " 
                msg += f"when playing **{played_name}** (**{played_count}** times)"

                reason_desc = "\n" + "Big doinks awarded so far:"
                for reason_id, reason in enumerate(doinks_reasons):
                    reason_desc += f"\n- {doinks_reasons[reason]}: **{doinks_counts[reason_id]}**"

                msg += reason_desc

            return self.client.insert_emotes(msg), total_doinks

        response = ""
        if target_id is None: # Check doinks for everyone.
            messages = []
            for disc_id in database.game_users.keys():
                resp_str, doinks = get_doinks_stats(disc_id, expanded=False)
                messages.append((resp_str, doinks))

            messages.sort(key=lambda x: x[1], reverse=True)
            for resp_str, _ in messages:
                response += "- " + resp_str + "\n"

        else: # Check doinks for a specific person.
            response = get_doinks_stats(target_id)[0]

        await self.message.channel.send(response)

class DoinksRelationsCommand(Command):
    NAME = "doinks_relations"
    DESCRIPTION = "Show who you (or someone else) get Big Doinks the most with."
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = [GameParam("game"), TargetParam("person")]

    def _get_doinks_relation_stats(self, game: str, target_id: int):
        database = self.client.game_databases[game]
        data = []
        games_relations, doinks_relations = database.get_doinks_relations(target_id)
        doinks_games = database.get_doinks_count(target_id)[0]
        for disc_id, total_games in games_relations.items():
            doinks = doinks_relations.get(disc_id, 0)
            data.append(
                (
                    disc_id, total_games, doinks, int((doinks / doinks_games) * 100),
                    int((doinks / total_games) * 100)
                )
            )

        return sorted(data, key=lambda x: x[2], reverse=True)

    async def handle(self, game: str, target_id: int):
        database = self.client.game_databases[game]

        data = []
        games_relations, doinks_relations = database.get_doinks_relations(target_id)
        doinks_games = database.get_doinks_count(target_id)[0]
        for disc_id, total_games in games_relations.items():
            doinks = doinks_relations.get(disc_id, 0)
            data.append(
                (
                    disc_id, total_games, doinks, int((doinks / doinks_games) * 100),
                    int((doinks / total_games) * 100)
                )
            )

        data.sort(key=lambda x: x[2], reverse=True)

        response = (
            f"Breakdown of who {self.client.get_discord_nick(target_id, self.message.guild.id)} " +
            "has gotten Big Doinks with:\n"
        )
        for disc_id, total_games, doinks, doinks_ratio, games_ratio in data:
            nick = self.client.get_discord_nick(disc_id, self.message.guild.id)
            response += f"- {nick}: **{doinks}** times (**{doinks_ratio}%**) "
            response += f"(**{games_ratio}%** of **{total_games}** games)\n"

        await self.message.channel.send(response)

class DoinksCriteriaCommand(Command):
    NAME = "doinks_criteria"
    DESCRIPTION = "Show the different criterias needed for acquiring doinks."
    OPTIONAL_PARAMS = [GameParam("game")]

    async def handle(self, game):
        doinks_reasons = get_doinks_reasons(game)
        game_name = SUPPORTED_GAMES[game]

        response = "Criteria for being awarded {emote_Doinks}: in " + game_name + "\n"
        for reason in doinks_reasons:
            response += f"- **{reason}**: {doinks_reasons[reason]}\n"

        response += "Any of these being met will award 1 {emote_Doinks}"

        await self.message.channel.send(self.client.insert_emotes(response))
