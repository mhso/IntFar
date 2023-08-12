from dataclasses import dataclass
from time import time
from datetime import datetime
from traceback import print_exc
from abc import ABC, abstractmethod

from mhooge_flask.logging import logger

from api.database import DBException, Database
from api.config import Config
from api.util import format_duration, round_digits, format_tokens_amount, parse_amount_str
from api.game_stats import GameStats
from api import game_stats

MAX_BETTING_THRESHOLD = 5 # The latest a bet can be made (in game-time in minutes)
MINIMUM_BETTING_AMOUNT = 5

# IDs that are saved to the database that each correspond
# to an event that a user can bet on.
BETTING_IDS = {
    "game_win": 0,
    "game_loss": 1,
    "no_intfar": 2,
    "intfar": 3,
    "intfar_kda": 4,
    "intfar_deaths": 5,
    "intfar_kp": 6,
    "intfar_vision": 7,
    "doinks": 8,
    "doinks_kda": 9,
    "doinks_kills": 10,
    "doinks_damage": 11,
    "doinks_penta": 12,
    "doinks_vision": 13,
    "doinks_kp": 14,
    "doinks_monsters": 15,
    "doinks_cs": 16,
    "most_kills": 17,
    "most_damage": 18,
    "most_kp": 19,
    "highest_kda": 20
}

# Types of bets. Some are handled the same, so they are grouped logically.
BETTING_TYPES_INDICES = {
    "game": 0,
    "intfar": 2,
    "intfar_reason": 4,
    "doinks": 8,
    "doinks_reason": 9,
    "stats": 17
}

# Textual descriptions of the different bets.
BETTING_DESC = {
    0: "winning the game",
    1: "losing the game",
    2: "no one being Int-Far",
    3: "someone being Int-Far",
    4: "someone being Int-Far by low KDA",
    5: "someone being Int-Far by many deaths",
    6: "someone being Int-Far by low KP",
    7: "someone being Int-Far by low vision score",
    8: "someone being awarded doinks",
    9: "someone being awarded doinks for high KDA",
    10: "someone being awarded doinks for many kills",
    11: "someone being awarded doinks for high damage",
    12: "someone being awarded doinks for getting a pentakill",
    13: "someone being awarded doinks for high vision score",
    14: "someone being awarded doinks for high KP",
    15: "someone being awarded doinks for securing all epic monsters",
    16: "someone being awarded doinks for having more than 8 cs/min",
    17: "someone getting the most kills",
    18: "someone doing the most damage",
    19: "someone having the highest kill participation",
    20: "someone having the highest KDA"
}

BETTING_STATS = [
    "kills", "damage", "kp", "kda"
]

TARGET_OPTIONAL = 0
TARGET_REQUIRED = 1
TARGET_INVALID = -1

@dataclass
class Bet:
    event_id: str
    description: str
    target_required: int
    base_return: float

class BetResolver(ABC):
    def __init__(self, bet: Bet, game_stats: GameStats, target_id: int=None):
        self.bet = bet
        self.game_stats = game_stats
        self.target_id = target_id

    @abstractmethod
    def resolve_intfar_reason(self):
        ...

    @abstractmethod
    def resolve_doinks_reason(self):
        ...

    @abstractmethod
    def resolve_stats(self):
        ...

    def resolve_game_outcome(self):
        bet_on_win = self.bet.event_id == "game_win"
        return bool(self.game_stats.win) ^ bet_on_win

    def resolve_has_intfar(self):
        intfar = self.game_stats.intfar_id
        if self.target_id is None: # Bet was about whether anyone was Int-Far.
            return (intfar is None) ^ (self.bet.event_id == "intfar")

        return intfar == self.target_id # Bet was about a specific person being Int-Far.

    def resolve_was_doinks(self):
        doinks = {
            player_stats.disc_id: player_stats.doinks
            for player_stats in self.game_stats.filtered_player_stats
        }
        if self.target_id is None:
            return len(doinks) > 0

        return self.target_id in doinks

    @property
    @abstractmethod
    def should_resolve_with_intfar_reason(self) -> list[str]:
        ...

    @property
    @abstractmethod
    def should_resolve_with_doinks_reason(self) -> list[str]:
        ...

    @property
    @abstractmethod
    def should_resolve_with_stats(self) -> list[str]:
        ...

    @property
    def should_resolve_with_game_outcome(self) -> list[str]:
        return ["game_win", "game_loss"]

    @property
    def should_resolve_with_has_intfar(self) -> list[str]:
        return ["no_intfar", "intfar"]

    @property
    def should_resolve_with_has_doinks(self) -> list[str]:
        return ["doinks"]

    def resolve_bet(self):
        resolver_list = [
            (self.should_resolve_with_game_outcome, self.resolve_game_outcome),
            (self.should_resolve_with_has_intfar, self.resolve_has_intfar),
            (self.should_resolve_with_has_doinks, self.resolve_was_doinks),
            (self.should_resolve_with_intfar_reason, self.resolve_intfar_reason),
            (self.should_resolve_with_doinks_reason, self.resolve_doinks_reason),
            (self.should_resolve_with_stats, self.resolve_stats),
        ]

        for bet_list, resolver_func in resolver_list:
            if self.bet.event_id in bet_list:
                return resolver_func()

        raise ValueError("Could not match bet with the proper resolver!")

def bet_requires_target(event_id: int):
    return event_id > 16

def bet_requires_no_target(event_id: int):
    return event_id < 3

def resolve_game_outcome(game_data: list[tuple[dict, int]], bet_on_win: bool):
    stats = game_data[0][1]
    return not (stats["gameWon"] ^ bet_on_win)

def resolve_is_intfar(intfar, _, target_id: int):
    if target_id is None: # Bet was about whether anyone was Int-Far.
        return intfar is not None
    return intfar == target_id # Bet was about a specific person being Int-Far.

def resolve_not_intfar(intfar, intfar_reason: str, _):
    return not resolve_is_intfar(intfar, intfar_reason, None)

def intfar_by_reason(intfar, reason_str: str, target_id: int, reason_id: int):
    return (resolve_is_intfar(intfar, reason_str, target_id)
            and reason_str[reason_id] == "1")

def resolve_is_intfar_by_kda(intfar, intfar_reason: str, target_id: int):
    return intfar_by_reason(intfar, intfar_reason, target_id, 0)

def resolve_is_intfar_by_deaths(intfar, intfar_reason: str, target_id: int):
    return intfar_by_reason(intfar, intfar_reason, target_id, 1)

def resolve_is_intfar_by_kp(intfar, intfar_reason: str, target_id: int):
    return intfar_by_reason(intfar, intfar_reason, target_id, 2)

def resolve_is_intfar_by_vision(intfar, intfar_reason: str, target_id: int):
    return intfar_by_reason(intfar, intfar_reason, target_id, 3)

def resolve_got_doinks(doinks, target_id: int):
    if target_id is None:
        return len(doinks) > 0
    return target_id in doinks

def resolve_doinks_by_reason(doinks, target_id, reason):
    if target_id is not None:
        return target_id in doinks and doinks[target_id][reason] == "1"
    for disc_id in doinks:
        if doinks[disc_id][reason] == "1":
            return True
    return False

def resolve_doinks_for_kda(doinks, target_id):
    return resolve_doinks_by_reason(doinks, target_id, 0)

def resolve_doinks_for_kills(doinks, target_id):
    return resolve_doinks_by_reason(doinks, target_id, 1)

def resolve_doinks_for_damage(doinks, target_id):
    return resolve_doinks_by_reason(doinks, target_id, 2)

def resolve_doinks_for_penta(doinks, target_id):
    return resolve_doinks_by_reason(doinks, target_id, 3)

def resolve_doinks_for_vision(doinks, target_id):
    return resolve_doinks_by_reason(doinks, target_id, 4)

def resolve_doinks_for_kp(doinks, target_id):
    return resolve_doinks_by_reason(doinks, target_id, 5)

def resolve_doinks_for_monsters(doinks, target_id):
    return resolve_doinks_by_reason(doinks, target_id, 6)

def resolve_doinks_for_cs(doinks, target_id):
    return resolve_doinks_by_reason(doinks, target_id, 7)

def resolve_most_kills(game_data, target_id):
    # Ties for most kills are NOT included. If more than one person has most kills, bet is lost.
    most_kills_ties = game_stats.get_outlier(game_data, "kills", asc=False, include_ties=True)[0]
    return target_id in most_kills_ties and len(most_kills_ties) == 1

def resolve_most_damage(game_data, target_id):
    # Ties for most damage is included. If more than one person has most dmg, bet is still won.
    most_damage_ties = game_stats.get_outlier(game_data, "totalDamageDealtToChampions",
                                              asc=False, include_ties=True)[0]
    return target_id in most_damage_ties

def resolve_highest_kp(game_data, target_id):
    # Ties for highest kp is NOT included. If more than one person has highest kp, bet is lost.
    highest_kp_ties = game_stats.get_outlier(game_data, "kp", asc=False, include_ties=True)[0]
    return target_id in highest_kp_ties and len(highest_kp_ties) == 1

def resolve_highest_kda(game_data, target_id):
    # Ties for highets KDA is NOT included. If more than one person has highest KDA, bet is lost.
    highest_kda_ties = game_stats.get_outlier(game_data, "kda", asc=False, include_ties=True)[0]
    return target_id in highest_kda_ties and len(highest_kda_ties) == 1

RESOLVE_INTFAR_BET_FUNCS = [
    resolve_not_intfar, resolve_is_intfar, resolve_is_intfar_by_kda,
    resolve_is_intfar_by_deaths, resolve_is_intfar_by_kp, resolve_is_intfar_by_vision
]

RESOLVE_DOINKS_BET_FUNCS = [
    resolve_got_doinks, resolve_doinks_for_kda, resolve_doinks_for_kills,
    resolve_doinks_for_damage, resolve_doinks_for_penta, resolve_doinks_for_vision,
    resolve_doinks_for_kp, resolve_doinks_for_monsters, resolve_doinks_for_cs
]

RESOLVE_STATS_BET_FUNCS = [
    resolve_most_kills, resolve_most_damage, resolve_highest_kp, resolve_highest_kda
]

class BettingHandler(ABC):
    def __init__(self, game: str, config: Config, database: Database):
        self.game = game
        self.config = config
        self.database = database

        self.betting_tokens_for_win = config.betting_tokens_for_win
        self.betting_tokens_for_loss = config.betting_tokens_for_loss

    @property
    def all_bets(self) -> list[Bet]:
        return [
            Bet("game_win", "winning the game", TARGET_INVALID, 2),
            Bet("game_loss", "losing the game", TARGET_INVALID, 2),
            Bet("no_intfar", "no one being Int-Far", TARGET_INVALID, 2),
            Bet("intfar", "someone being Int-Far", TARGET_OPTIONAL, 2),
            Bet("doinks", "someone being awarded doinks", TARGET_OPTIONAL, 2),
        ]

    @abstractmethod
    def get_bet_resolver(self, bet: Bet, game_stats: GameStats, target_id: int=None) -> BetResolver:
        ...

    def get_bet(self, event_id: str):
        for bet in self.all_bets:
            if bet.event_id == event_id:
                return bet

        return None

    def get_intfar_return(self, bet: Bet, target_id: int):
        is_intfar = bet.event_id == "intfar"
        if target_id is None or not is_intfar:
            games_total = self.database.get_games_count(self.game)[0]
            intfars_total = self.database.get_intfar_count(self.game)
            intfar_count = intfars_total if is_intfar else games_total - intfars_total
            return intfar_count, games_total

        games_played, intfar_reason_ids = self.database.get_intfar_stats(self.game, target_id)
        return len(intfar_reason_ids), games_played

    def get_intfar_reason_return(self, intfar_index: int, target_id: int):
        reason_count = 0
        num_games = 0
        if target_id is None:
            intfar_reason_ids = self.database.get_intfar_reason_counts(self.game)[0]
            num_games = self.database.get_games_count(self.game)[0]
            reason_count = intfar_reason_ids[intfar_index]
        else:
            num_games, intfar_reason_ids = self.database.get_intfar_stats(self.game, target_id)
            for reason_id in intfar_reason_ids:
                if reason_id[0][intfar_index] == "1":
                    reason_count += 1

        return reason_count, num_games

    def get_doinks_return(self, target_id: int):
        if target_id is None:
            games_total = self.database.get_games_count(self.game)[0]
            doinks_count = self.database.get_doinks_count(self.game)[0]
            return doinks_count, games_total

        games_played = self.database.get_games_count(self.game, target_id)[0]
        doinks_count = self.database.get_doinks_count(self.game, target_id)[0]
        return doinks_count, games_played

    def get_doinks_reason_return(self, doinks_index: int, target_id: int):
        reason_count = 0
        num_games = 0
        if target_id is None:
            doinks_reason_ids = self.database.get_doinks_reason_counts(self.game)
            num_games = self.database.get_games_count(self.game)[0]
            reason_count = doinks_reason_ids[doinks_index]
        else:
            num_games = self.database.get_games_count(self.game, target_id)[0]
            doinks_reason_ids = self.database.get_doinks_stats(self.game, target_id)
            for reason_id in doinks_reason_ids:
                if reason_id[0][doinks_index] == "1":
                    reason_count += 1

        return reason_count, num_games

    def get_stats_return(self, stat, target_id):
        best_in_stat_count = self.database.get_best_or_worst_stat(self.game, stat, target_id)[0]
        num_games = self.database.get_intfar_stats(self.game, target_id)[0]
        return best_in_stat_count, num_games

    def award_tokens_for_playing(self, disc_id, tokens_gained):
        self.database.update_token_balance(disc_id, tokens_gained, True)

    def get_dynamic_bet_desc(self, event: str, target_person: str=None):
        bet_desc = self.get_bet(event).description
        if target_person is not None:
            bet_desc = bet_desc.replace("someone", target_person)
        return bet_desc

    def get_bet_return_desc(self, bet_str: str, target_id: int, target_name: str) -> str:
        """
        Get a description of the return value of a specific bet, if placed on
        an event and optionally targetting a specific person.

        :param bet_str:     The name of the event to place the bet on
        :param target_id:   Discord ID of the person to target with the bet (or None)
        :param target_name: Name of the person to target with the bet (or None)
        """
        bet = self.get_bet(bet_str)
        if bet is None:
            return f"Invalid event to bet on: '{bet_str}'."

        event_desc = self.get_dynamic_bet_desc(bet_str, target_name)

        base_return = self.get_dynamic_bet_return(bet, target_id)
        readable_return = round_digits(base_return)

        response = f"Betting on `{event_desc}` would return {readable_return} times your investment.\n"
        response += "If you bet after the game has started, the return will be lower.\n"
        if bet_str > 2:
            start = "If" if target_id is None else "Since"
            response += f"{start} you bet on this event happening to a *specific* person "
            response += "(not just *anyone*), then the return will be further multiplied "
            response += "by how many people are in the game (2x return if 2 people are in "
            response += "the game, 3x return if 3 people, etc)."

        return response

    def get_dynamic_bet_return(self, bet: Bet, target_id: int) -> int:
        """
        Get a value for how many tokens can be won by a bet on a given target.

        :param event_id:    ID of the event to place the bet on
        :param target:      Discord ID of person to target with the bet or None
                            if the bet has no target
        """
        resolver = self.get_bet_resolver(bet, None, target_id)

        count = 0
        num_games = 0
        if bet.event_id in resolver.should_resolve_with_has_intfar:
            count, num_games = self.get_intfar_return(bet, target_id)
        elif bet.event_id in resolver.should_resolve_with_intfar_reason:
            intfar_index = resolver.should_resolve_with_intfar_reason.index(bet.event_id)
            count, num_games = self.get_intfar_reason_return(intfar_index, target_id)
        elif bet.event_id in resolver.should_resolve_with_has_doinks:
            count, num_games = self.get_doinks_return(target_id)
        elif bet.event_id in resolver.should_resolve_with_doinks_reason:
            doinks_index = resolver.should_resolve_with_doinks_reason.index(bet.event_id)
            count, num_games = self.get_doinks_reason_return(doinks_index, target_id)
        elif bet.event_id in resolver.should_resolve_with_stats:
            stat_index = resolver.should_resolve_with_stats.index(bet.event_id)
            stat = resolver.should_resolve_with_stats[stat_index].split("_")[1]
            count, num_games = self.get_stats_return(stat, target_id)

        if num_games == 0: # No games has been played for given target, ratio is 0
            return bet.base_return
        if count == 0: # Event never happened, set ratio to amount of games played
            return max(num_games, 1)

        return num_games / count

    def get_bet_value(self, bet_amount: int, event_id: str, bet_timestamp: int, target_id: int):
        bet = self.get_bet(event_id)
        base_return = self.get_dynamic_bet_return(bet, target_id)
        if bet_timestamp <= 120: # Bet was made before game started, award full value.
            ratio = 1.0
        else: # Scale value with game time at which bet was made.
            max_time = 60 * (MAX_BETTING_THRESHOLD + 2.5)
            ratio = 1 - ((bet_timestamp - 120) / max_time)

        # Reward a minimum of bet amount + 5%
        value = int(max(bet_amount * base_return * ratio, bet_amount * 1.05))

        return value, base_return, ratio

    def resolve_bet(
        self,
        disc_id: int,
        bet_ids: list[int],
        amounts: list[int],
        bet_timestamp: int,
        events: list[str],
        targets: list[int],
        game_stats: GameStats,
        bet_multiplier: int
    ) -> tuple[bool, int]:
        """
        Resolves the given bet for the given player. This determines whether the bet
        was won or not, and awards the correct betting tokens if it was.

        ### Parameters
        :param disc_id:         Discord ID of the user who placed the bet
        :param bet_ids:         List of database IDs of the placed bets
        :param amounts:         List of amount of points that was placed on each bet
        :param bet_timestamp:   How many seconds the game was underway when the bet
                                was placed or None if game had not started
        :param events:          List of events that the bet was placed on
        :param targets:         List of user Discord IDs to target with each bet
        :param target_names:    List of user names to target with each bet

        ### Returns
        :result:
    
        Tuple containing a boolean indicating whether the bet was won and an
        integer indicating the total tokens won from the bet.
        """
        # Multiplier for betting on a specific person to do something. If more people are
        # in the game, the multiplier is higher.
        person_multiplier = len(game_stats.filtered_player_stats)
        amount_multiplier = len(amounts)

        total_value = 0
        all_success = True

        for amount, event_id, target_id in zip(amounts, events, targets):
            bet = self.get_bet(event_id)
            resolver = self.get_bet_resolver(bet, game_stats, target_id)
            success = resolver.resolve_bet()

            all_success = all_success and success

            bet_value = (
                self.get_bet_value(amount, event_id, bet_timestamp, target_id)[0]
                if success
                else 0
            )

            if target_id is not None:
                bet_value = bet_value * person_multiplier

            total_value += bet_value

        total_value = total_value * amount_multiplier * bet_multiplier
        timestamp = int(time())

        for bet_id in bet_ids:
            try:
                self.database.mark_bet_as_resolved(
                    bet_id, game_stats.game_id, timestamp, all_success, total_value
                )
            except DBException:
                logger.exception("Database error during bet resolution!")
                return

        if all_success: # Only award points if all bets were won
            self.database.update_token_balance(disc_id, total_value, True)

        return all_success, total_value

    def get_bet_placed_text(
        self,
        data: tuple[int, int, int, str, str],
        all_in: bool,
        duration: int,
        ticket: int = None
    ) -> str:
        """
        Get a string describing a bet that was placed.

        :param data:        Tuple of relevant data about the bet
        :param all_in:      Whether the user placing the bet bet all their tokens on it
        :param duration:    How many seconds a current game is underway
        :param ticket:      Ticket ID, only relevant if the bet is a multi-bet
        """
        tokens_name = self.config.betting_tokens

        response = ""
        if len(data) > 1:
            response = "Multi-bet successfully placed! "
            response += "You bet on **all** the following happening:"

            for amount, _, _, base_return, bet_desc in data:
                response += f"\n - `{bet_desc}` for **{format_tokens_amount(amount)}** {tokens_name} "
                response += f"(**{base_return}x** return)."
            response += f"\nThis bet uses the following ticket ID: **{ticket}**. "
            response += "You will need this ticket to cancel the bet.\n"
        else:
            amount, _, _, base_return, bet_desc = data[0]
            response = f"Bet succesfully placed: `{bet_desc}` for "
            if all_in:
                capitalized = tokens_name[1:-1].upper()
                response += f"***ALL YOUR {capitalized}, YOU MAD LAD!!!***\n"
            else:
                response += f"**{format_tokens_amount(amount)}** {tokens_name}.\n"
            response += f"The return multiplier for that event is **{base_return}**.\n"

        if duration == 0:
            response += "You placed your bet before the game started, "
            response += "you will get the full reward.\n"
        else:
            response += "You placed your bet during the game, therefore "
            response += "you will not get the full reward.\n"

        response += "Potential winnings:\n"

        return response

    def get_bet_error_msg(self, bet_desc, error):
        return f"Bet was not placed: '{bet_desc}' - {error}"

    def check_bet_validity(
        self,
        disc_id: int,
        guild_id: int,
        bet_amount: str,
        game_timestamp: int,
        bet_str: str,
        balance: int,
        running_cost: int,
        bet_target: int,
        target_name: str,
        ticket: int
    ) -> tuple[bool, str]:
        """
        Check whether a given bet is valid. This includes whether the correct values
        are given for the bet, whether the bet is a duplicate, whether a game is too
        far progressed to place the bet, and whether the user has enough tokens.

        ### Parameters
        :param disc_id:         Discord ID of the user placing the bet
        :param guild_id:        ID of the Discord server in which the bet should be placed
        :param bet_amount:      Amount of points to place on the bet
        :param game_timestamp:  How many seconds the current game is underway (or None)
                                if no game is currently ongoing
        :param bet_str:         String describing which event to place the bet on
        :param balance:         The amount of betting tokens the user has before the
                                bet is placed
        :param running_cost:    Cost of the bet in betting tokens
        :param bet_target:      Discord ID of the user the bet targets (or None)
        :param target_name:     Discord name of the user the bet targets (or None)

        ### Returns
        :result:
    
        Tuple containing a boolean indicating whether the bet is valid
        and a string describing why it is not, if it isn't or a tuple of relevant
        data about the bet, if it is.
        """
        event_id = BETTING_IDS.get(bet_str)
        tokens_name = self.config.betting_tokens
        if event_id is None:
            return (False, f"Bet was not placed: Invalid event to bet on: '{bet_str}'.")

        if bet_requires_no_target(event_id):
            bet_target = None
            target_name = None

        bet_desc = self.get_dynamic_bet_desc(event_id, target_name)

        if bet_requires_target(event_id) and bet_target is None:
            err_msg = self.get_bet_error_msg(bet_desc, "A person is required as the 'target' of that bet.")
            return (False, err_msg)

        min_amount = MINIMUM_BETTING_AMOUNT
        amount = 0
        try:
            amount = parse_amount_str(bet_amount.strip(), balance)

            if amount < min_amount: # Bet was for less than the minimum allowed amount.
                err_msg = self.get_bet_error_msg(
                    bet_desc, f"Betting amount is too low. Must be minimum {min_amount}."
                )
                return (False, err_msg)
        except ValueError:
            err_msg = self.get_bet_error_msg(bet_desc, f"Invalid bet amount: '{bet_amount}'.")
            return (False, err_msg)

        time_now = time()
        duration = 0 if game_timestamp is None else time_now - game_timestamp
        if duration > 60 * MAX_BETTING_THRESHOLD:
            err_msg = self.get_bet_error_msg(
                bet_desc,
                "The game is too far progressed. You must place bet before " +
                f"{MAX_BETTING_THRESHOLD} minutes in game."
            )

            return (False, err_msg)

        if self.database.get_bet_id(disc_id, guild_id, event_id, bet_target, ticket) is not None:
            err_msg = self.get_bet_error_msg(bet_desc, "Such a bet has already been made!")
            return (False, err_msg)

        if running_cost + amount > balance:
            err_msg = self.get_bet_error_msg(bet_desc, f"You do not have enough {tokens_name}.")
            return (False, err_msg)

        return (True, (amount, event_id, duration, bet_desc))

    def place_bet(
        self,
        disc_id: int,
        guild_id: int,
        amounts: list[str],
        game_timestamp: int,
        events: list[str],
        targets: list[int],
        target_names: list[str]
    ) -> tuple[bool, str, tuple[int, int]]:
        """
        Place one or more bets if the best are valid
        and the user has enough points to afford them.

        ### Parameters
        :param disc_id:         Discord ID of the user placing the bet
        :param guild_id:        ID of the Discord server in which the bet should be placed
        :param amounts:         List of amount of points to bet for on each bet
        :param game_timestamp:  How many seconds the current game is underway (or None)
                                if no game is currently ongoing
        :param events:          List of events to bet on
        :param targets:         List of user Discord IDs to target with each bet
        :param target_names:    List of user names to target with each bet

        ### Returns
        :result:
    
        Tuple containing a boolean indicating whether the bet was sucessully
        placed, a string describing the bet, and a tuple of internal database
        IDs of the bet, which are necessary if the bet should be cancelled.
        """
        tokens_name = self.config.betting_tokens
        ticket = None if len(amounts) == 1 else self.database.generate_ticket_id(disc_id)
        bet_data = []
        reward_equation = ""
        game_duration = 0
        time_ratio = 0
        final_value = 0
        first = True
        any_target = False
        bet_id = None
        used_events = set()

        try:
            balance = self.database.get_token_balance(disc_id)
            running_cost = 0 # Total cost of the bet

            # Run through betting amounts, events, target discord IDs, and target names
            for bet_amount, event, target, target_name in zip(amounts, events, targets, target_names):
                valid, data = self.check_bet_validity(
                    disc_id, guild_id, bet_amount, game_timestamp, event,
                    balance, running_cost, target, target_name, ticket
                )

                if not valid:
                    return (False, data, None)

                # Unpack parsed amounts, betting event ID, current game duration, and betting description
                amount, event_id, game_duration, bet_desc = data

                # Ensure that no events and targets are bet on more than once
                if (event_id, target) in used_events:
                    err_msg = self.get_bet_error_msg(bet_desc, "Duplicate Event.")
                    return (False, err_msg, None)

                used_events.add((event_id, target))

                running_cost += amount

                bet_value, base_return, time_ratio = self.get_bet_value(
                    amount, event_id, game_duration, target
                )

                final_value += bet_value
                return_readable = round_digits(base_return)

                bet_data.append((amount, event_id, target, return_readable, bet_desc))

            # Run through the parsed bet data and generate a string describing
            # the bet and the potential reward it could give
            for amount, event_id, bet_target, base_return, bet_desc in bet_data:
                bet_id = self.database.make_bet(
                    disc_id, guild_id, event_id, amount,
                    game_duration, bet_target, ticket
                )

                if not first:
                    reward_equation += " + "
                reward_equation += f"{amount} x {base_return}"

                if bet_target is not None: # Multiplier for targetting specific player
                    reward_equation += " x [players_in_game]"
                    any_target = True

                first = False

        except DBException:
            # Log error along with relevant variables
            logger.bind(
                disc_id=disc_id,
                guild_id=guild_id,
                amounts=amounts,
                game_timestamp=game_timestamp,
                events=events,
                targets=targets,
                target_names=target_names,
                bet_data=bet_data,
                ticket=ticket
            ).exception("Bet could not be placed")

            return (False, "Bet was not placed: Database error occured :(", None)

        # Show multiplier for betting on multiple events at once
        final_value *= len(amounts)
        if len(amounts) > 1:
            reward_equation = "(" + reward_equation
            reward_equation += f") x {len(amounts)}"

        # Show point penalty if game is already started
        ratio_readable = round_digits(time_ratio)
        if game_duration > 0:
            reward_equation += f" x {ratio_readable}"

        reward_equation += f" = **{format_tokens_amount(final_value)}** {tokens_name}"

        if any_target:
            reward_equation += " (minimum)\n"

        # Describe why a penalty was given if game is underway
        if game_duration > 0:
            dt_start = datetime.fromtimestamp(game_timestamp)
            dt_now = datetime.fromtimestamp(time())
            duration_fmt = format_duration(dt_start, dt_now)
            reward_equation += f"\n{ratio_readable} is a penalty for betting "
            reward_equation += f"{duration_fmt} after the game started."

        # Describe why a multiplier was given for targetting a specific person
        if any_target:
            reward_equation += (
                "[players_in_game] is a multiplier. " +
                f"Because you bet on a specific person, you will get more {tokens_name} if " +
                "more players are in the game."
            )

        bet_all = len(amounts) == 1 and amounts[0] == "all"
        response = self.get_bet_placed_text(bet_data, bet_all, game_duration, ticket)

        balance_resp = f"\nYour {tokens_name} balance is now `{format_tokens_amount(balance - running_cost)}`."

        bet_id = None if len(amounts) > 1 else bet_id

        return (True, response + reward_equation + balance_resp, (bet_id, ticket))

    def delete_bet(
        self,
        disc_id: int,
        bet_id: int,
        ticket: int,
        game_timestamp: int
    ) -> tuple[bool, tuple[int, int]]:
        """
        Delete a previously placed bet from the database and refund the amount
        placed on the bet.

        ### Parameters
        :param disc_id:         Discord ID of the user who made the bet
        :param bet_id:          Database ID of the bet that should be deleted (or None)
        :param ticket:          Database ID of the multi-bet that should be deleted (or None)
        :parma game_timestamp:  How many seconds the game was underway when the bet
                                was placed or None if game had not started

        ### Returns
        :result:

        Tuple containing a boolean indicating whether the bet was sucessully deleted
        and a tuple containing the new token balance for the user after refunding
        the bet and the amount refunded.
        """
        if game_timestamp is not None: # Game has already started.
            return (False, "Bet was not cancelled: Game is underway!")

        if ticket is None and self.database.get_better_id(bet_id) != disc_id:
            return (False, "Bet was not cancelled: Bet does not exist, or you don't own the bet!")

        if ticket is None:
            amount_refunded = self.database.cancel_bet(bet_id, disc_id)
        else:
            amount_refunded = self.database.cancel_multi_bet(ticket, disc_id)

        new_balance = self.database.get_token_balance(disc_id)

        return (True, (new_balance, amount_refunded))

    def cancel_bet(
        self,
        disc_id: int,
        guild_id: int,
        bet_str: str,
        game_timestamp: int,
        target_id: int,
        target_name: str
    ) -> tuple[bool, str]:
        """
        Cancels a bet that has previously been placed if the game it was placed on
        has not yet started.

        ### Parameters
        :param disc_id:         Discord ID of the user cancelling the bet
        :param guild_id:        ID of the Discord server in which the bet was placed
        :param bet_str:         String describing the bet that should be cancelled
        :param game_timestamp:  How many seconds the current game is underway (or None)
                                if no game is currently ongoing
        :param target_id:       Discord ID of the user the bet was targetting (or None)
        :param target_name:     Discord name of the user the bet was targetting (or None)

        ### Returns
        :result:
    
        Tuple containing a boolean indicating whether the bet was sucessully
        cancelled and a string describing the bet that was cancelled.
        """
        ticket = None
        event_id = BETTING_IDS.get(bet_str)
        tokens_name = self.config.betting_tokens
        if event_id is None:
            try:
                ticket = int(bet_str)
            except ValueError:
                return (False, f"Bet was not cancelled: Not a valid betting event: '{bet_str}'")

        try:
            bet_id = self.database.get_bet_id(disc_id, guild_id, event_id, target_id, ticket)
            if bet_id is None:
                return (
                    False,
                    "Bet was not cancelled: No bet exists with the specified parameters."
                )

            success, data = self.delete_bet(disc_id, bet_id, ticket, game_timestamp)
            if not success:
                return (False, data)

            new_balance, amount_refunded = data
            if ticket is None:
                bet_desc = self.get_dynamic_bet_desc(event_id, target_name)
                response = (
                    f"Bet on `{bet_desc}` for {format_tokens_amount(amount_refunded)} " +
                    f"{tokens_name} successfully cancelled.\n"
                )
            else:
                response = f"Multi-bet with ticket ID **{ticket}** successfully cancelled.\n"
            response += f"Your {tokens_name} balance is now `{format_tokens_amount(new_balance)}`."
            return (True, response)
        except DBException:
            print_exc()
            return (False, "Bet was not cancelled: Database error occured :(")

    def get_gift_err_msg(self, err_msg):
        return f"Transfer failed: {err_msg}"

    def give_tokens(
        self,
        disc_id: int,
        amount_str: str,
        receiver_id: int,
        receiver_name: str
    ) -> tuple[bool, str]:
        """
        Transfer a given amount of betting tokens from one user to another.

        ### Parameters
        :param disc_id:         Discord ID of the user giving the tokens
        :param amount_str:      String describing the amount of tokens to give
        :param receiver_id:     Discord ID of the user recieving the tokens
        :param receiver_name:   Discord name of the user recieving the tokens

        ### Returns
        :result:
    
        Tuple containing a boolean indicating whether the tokens were sucessully
        transferred and a string describing the transfer.
        """
        amount = 0
        balance = 0
        tokens_name = self.config.betting_tokens
        try:
            balance = self.database.get_token_balance(disc_id)
        except DBException:
            print_exc()
            err_msg = self.get_gift_err_msg("Database error occured :(")
            return (False, err_msg)

        try:
            amount = parse_amount_str(amount_str.strip(), balance)
        except ValueError:
            # String describing the amount to give was invalid
            err_msg = self.get_gift_err_msg(f"Invalid token amount: '{amount_str}'.")
            return (False, err_msg)

        if balance < amount:
            # Sender does not have the specified amount of tokens to give
            err_msg = self.get_gift_err_msg(f"You do not have enough {tokens_name}.")
            return (False, err_msg)

        try:
            self.database.give_tokens(disc_id, amount, receiver_id)
        except DBException:
            print_exc()
            err_msg = self.get_gift_err_msg("Database error occured :(")
            return (False, err_msg)

        receiver_balance = self.database.get_token_balance(receiver_id)

        response = f"Transfer of **{format_tokens_amount(amount)}** {tokens_name} to {receiver_name} succesfully made.\n"
        response += f"You now have **{format_tokens_amount(balance - amount)}** {tokens_name}.\n"
        response += f"{receiver_name} now has **{format_tokens_amount(receiver_balance)}** {tokens_name}."

        return (True, response)
