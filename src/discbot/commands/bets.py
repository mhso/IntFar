from asyncio import sleep
from typing import List

import api.util as api_util
from api.meta_database import DEFAULT_GAME
from api import betting
from discbot.commands.base import *
from discbot.commands.meta import UsageCommand
from discbot.commands.util import extract_target_name

class BettingCommand(Command):
    NAME = "betting"
    DESCRIPTION = "Show information about betting, as well as a list of possible events to bet on."
    OPTIONAL_PARAMS = [GameParam("game")]

    async def handle(self, game: str):
        max_mins = betting.MAX_BETTING_THRESHOLD
        tokens_name = self.client.config.betting_tokens
        response = (
            "Betting usage: `!bet [game] [amount] [event] (person)`\n"
            "This places a bet on the next (or current) match for the given game.\n"
            f"`!bet [game] all [event] (person)` bets **all** your {tokens_name} on an event!\n"
            f"You can place a bet during a game, but it has to be done before {max_mins} "
            "minutes. Betting during a game returns a lower reward, based on "
            "how much time has passed in the game.\n"
            f"**--- List of available events to bet on for {api_util.SUPPORTED_GAMES[game]} ---**"
        )
        await self.message.channel.send(response)

        game_response = ""
        for bet in self.client.betting_handlers[game].all_bets:
            game_response += f"\n`{bet.event_id}` - Bet on {bet.description}"

        await sleep(0.5)
        await self.message.channel.send(game_response)

class MakeBetCommand(Command):
    NAME = "bet"
    DESCRIPTION = (
        "Bet a specific amount of credits on one or more events happening " +
        "in the current or next game. Fx. `!bet lol 100 game_win`, `!bet cs2 all intfar slurp` " +
        "or `!bet lol 20 game_win & 30 no_intfar` (bet on game win *AND* no Int-Far in a League game)."
    )
    ACCESS_LEVEL = "all"

    async def handle(self, game: str, amounts: List[str], events: List[str], targets: List[str]):
        if events == [] or amounts == [] or None in amounts or None in events:
            await UsageCommand(self.client, self.message).handle("bet")
            return

        target_ids = []
        target_names = []

        for target_name in targets:
            target_id = None
            discord_name = None

            if target_name is not None: # Bet on a specific person doing a thing.
                if target_name == "me":
                    target_id = self.message.author.id
                else:
                    target_name = target_name.lower()
                    target_id = self.client.try_get_user_data(target_name.strip(), self.message.guild.id)

                    if target_id is None:
                        msg = "Error: Invalid summoner or Discord name "
                        msg += f"{self.client.get_emoji_by_name('PepeHands')}"
                        await self.message.channel.send(msg)
                        return
        
                discord_name = self.client.get_discord_nick(target_id, self.message.guild.id)

            target_ids.append(target_id)
            target_names.append(discord_name)

        with self.client.meta_database:
            with self.client.game_databases[game]:
                response = self.client.betting_handlers[game].place_bet(
                    self.message.author.id,
                    self.message.guild.id,
                    amounts,
                    self.client.get_game_start(game, self.message.guild.id),
                    events,
                    target_ids,
                    target_names
                )[1]

        await self.message.channel.send(response)

    async def parse_args(self, args: List[str]):
        amounts = []
        events = []
        targets = []

        if len(args) == 0:
            return [None, [], [], []]

        game = args[0]
        if game not in api_util.SUPPORTED_GAMES:
            game = DEFAULT_GAME
            index = 0
        else:
            index = 1

        while index < len(args):
            event = args[index+1]
            amount = args[index]
            if "&" in (event, amount):
                raise ValueError("Multi-bet input is formatted incorrectly!")

            target = None
            if index + 2 < len(args) and args[index+2] != "&":
                try:
                    end_index = args.index("&", index)
                except ValueError:
                    end_index = len(args)
                target = extract_target_name(args, index+2, end_index)
                index = end_index + 1
            else:
                index += 3

            amounts.append(amount)
            events.append(event)
            targets.append(target)

        return [game, amounts, events, targets]

class CancelBetCommand(Command):
    NAME = "cancel_bet"
    DESCRIPTION = (
        "Cancel a previously placed bet with the given parameters. " +
        "To cancel a multi-bet, provide the ticket generated for that bet. " +
        "A bet can't be cancelled when a game has started."
    )
    ACCESS_LEVEL = "all"
    MANDATORY_PARAMS = [CommandParam("event/ticket")]
    OPTIONAL_PARAMS = [GameParam("game"), TargetParam("person", None)]

    async def handle(self, betting_event: str, game: str, target_id: int = None):
        target_name = (
            None if target_id is None
            else self.client.get_discord_nick(target_id, self.message.guild.id)
        )

        response = self.client.betting_handlers[game].cancel_bet(
            self.message.author.id,
            self.message.guild.id,
            betting_event,
            self.client.get_game_start(game, self.message.guild.id),
            target_id,
            target_name
        )[1]

        await self.message.channel.send(response)

class GiveTokensCommand(Command):
    NAME = "give"
    DESCRIPTION = "Give good-boi points to someone."
    ACCESS_LEVEL = "all"
    MANDATORY_PARAMS = [CommandParam("amount"), TargetParam("person")]

    async def handle(self, amount: str, target_id: int):
        target_name = self.client.get_discord_nick(target_id, self.message.guild.id)

        max_tokens_before, max_tokens_holder = self.client.meta_database.get_max_tokens_details()

        response = self.client.betting_handlers[DEFAULT_GAME].give_tokens(
            self.message.author.id, amount, target_id, target_name
        )[1]

        balance_after = self.client.meta_database.get_token_balance(target_id)

        if balance_after > max_tokens_before and target_id != max_tokens_holder:
            # This person now has the most tokens of all users!
            tokens_name = self.client.config.betting_tokens
            response += f"\n{target_name} now has the most {tokens_name} of everyone! "
            await self.client.assign_top_tokens_role(max_tokens_holder, target_id)

        await self.message.channel.send(response)

class ActiveBetCommand(Command):
    NAME = "active_bets"
    DESCRIPTION = "See a list of your (or someone else's) active bets."
    TARGET_ALL = True
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = [GameParam("game", allow_default=False), TargetParam("person")]

    async def handle(self, game: str, target_id: int):
        def get_bet_description(game: str, disc_id: int, single_person :bool = True):
            active_bets = self.client.game_databases[game].get_bets(True, disc_id)
            recepient = self.client.get_discord_nick(disc_id, self.message.guild.id)

            response = ""
            if active_bets is None:
                if single_person:
                    response = f"{recepient} has no active bets."
                else:
                    response = None
            else:
                tokens_name = self.client.config.betting_tokens
                response = f"{recepient} has the following active bets:"
                bets_by_guild = {guild_id: [] for guild_id in api_util.GUILD_IDS}
                for bet_data in active_bets:
                    bets_by_guild[bet_data[1]].append(bet_data)

                for guild_id in bets_by_guild:
                    guild_bets = bets_by_guild[guild_id]
                    if guild_bets != []:
                        guild_name = self.client.get_guild_name(guild_id)
                        response += f"\n=== In **{guild_name}** ==="

                    for _, guild_id, _, amounts, events, targets, _, ticket, _ in guild_bets:
                        bets_str = "\n- "
                        total_cost = 0
                        if len(amounts) > 1:
                            bets_str += f"Multi-bet (ticket = {ticket}): "
                        for index, (amount, event, target) in enumerate(zip(amounts, events, targets)):
                            person = None
                            if target is not None:
                                person = self.client.get_discord_nick(target, self.message.guild.id)

                            bet_desc = self.client.betting_handlers[game].get_dynamic_bet_desc(event, person)
                            bets_str += f"`{bet_desc}`"
                            if index != len(amounts) - 1:
                                bets_str += " & "

                            total_cost += amount

                        bets_str += f" for **{total_cost}** {tokens_name}"

                        response += bets_str

            return response

        response = ""

        games_to_check = [game] if game is not None else api_util.SUPPORTED_GAMES
        for game in games_to_check:
            game_response = f"Bets for **{api_util.SUPPORTED_GAMES[game]}**:\n"
            if target_id is None:
                # Check active bets for everyone
                any_bet = False
                for disc_id in self.client.game_databases[game].game_users.keys():
                    bets_for_person = get_bet_description(game, disc_id, False)
                    if bets_for_person is not None:
                        if any_bet:
                            bets_for_person = "\n" + bets_for_person
                        game_response += bets_for_person
                        any_bet = True

                if any_bet:
                    if response != "":
                        game_response = "\n" + game_response

                    response += game_response

            else:
                # Check active bets for a single person
                game_response += get_bet_description(game, target_id)
                if response != "":
                    game_response = "\n" + game_response

                response += game_response

        if target_id is None and response == "":
            response = "No one has any active bets."

        await self.message.channel.send(response)

class AllBetsCommand(Command):
    NAME = "bets"
    DESCRIPTION = "See a description of your (or someone else's) lifetime bets."
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = [GameParam("game"), TargetParam("person")]

    async def handle(self, game: str, target_id: int):
        game_name = api_util.SUPPORTED_GAMES[game]
        all_bets = self.client.game_databases[game].get_bets(False, target_id)
        tokens_name = self.client.config.betting_tokens
        bets_won = 0
        had_target = 0
        during_game = 0
        spent = 0
        most_often_event = 0
        max_event_count = 0
        winnings = 0
        betting_descs = {bet.event_id: bet.description for bet in self.client.betting_handlers[game].all_bets}
        event_counts = {event_id: 0 for event_id in betting_descs}

        target_name = self.client.get_discord_nick(target_id, self.message.guild.id)

        if all_bets is None:
            response = f"{target_name} has not won or lost any bets yet!"
        else:
            for _, _, _, amounts, events, targets, game_time, result, payout in all_bets:
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
            event_desc = betting_descs[most_often_event]

            response = f"{target_name} has made a total of **{len(all_bets)}** bets for **{game_name}**.\n"
            response += f"- Bets won: **{bets_won} ({pct_won}%)**\n"
            response += f"- Average amount of {tokens_name} wagered: **{api_util.format_tokens_amount(average_amount)}**\n"
            response += f"- Total {tokens_name} wagered: **{api_util.format_tokens_amount(spent)}**\n"
            response += f"- Total {tokens_name} won: **{api_util.format_tokens_amount(winnings)}**\n"
            response += f"- Bet made the most often: `{event_desc}` (made **{max_event_count}** times)\n"
            response += f"- Bets that targeted a person: **{had_target} ({pct_target}%)**\n"
            response += f"- Bets made during a game: **{during_game} ({pct_during}%)**"

        await self.message.channel.send(response)

class TokenBalanceCommand(Command):
    NAME = "betting_tokens"
    DESCRIPTION = "See how many betting tokens you (or someone else) has."
    TARGET_ALL = True
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = [TargetParam("person")]
    ALIASES = ["gbp", "balance"]

    async def handle(self, target_id: int):
        def get_token_balance(disc_id):
            name = self.client.get_discord_nick(disc_id, self.message.guild.id)
            balance = self.client.meta_database.get_token_balance(disc_id)
            return balance, name

        tokens_name = self.client.config.betting_tokens

        response = ""
        if target_id is None: # Get betting balance for all.
            balances = []
            for disc_id in self.client.meta_database.all_users.keys():
                balance, name = get_token_balance(disc_id)
                balances.append((balance, name))

            balances = [
                f"{name} has **{api_util.format_tokens_amount(balance)}** {tokens_name}"
                for balance, name
                in sorted(balances, key=lambda x: x[0], reverse=True)
            ]

            response = "\n".join(balances)
        else:
            balance, name = get_token_balance(target_id)
            response = f"{name} has **{api_util.format_tokens_amount(balance)}** {tokens_name}"

        await self.message.channel.send(response)

class BetReturnCommand(Command):
    NAME = "bet_return"
    DESCRIPTION = (
        "See the return award of a specific betting "
        "event (targetting 'person', if given)."
    )
    ACCESS_LEVEL = "self"
    MANDATORY_PARAMS = [CommandParam("event")]
    OPTIONAL_PARAMS = [GameParam("game"), TargetParam("person", None)]

    async def handle(self, betting_event: str, game: str, target_id: int = None):
        target_name = (
            None if target_id is None
            else self.client.get_discord_nick(target_id, self.message.guild.id)
        )

        response = self.client.betting_handlers[game].get_bet_return_desc(betting_event, target_id, target_name)
        await self.message.channel.send(response)
