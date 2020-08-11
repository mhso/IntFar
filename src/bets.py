from time import time
from database import DBException
from traceback import print_exc

BETTING_IDS = {
    "game_win": 0,
    "game_loss": 1,
    "intfar": 2,
    "intfar_kda": 3,
    "intfar_deaths": 4,
    "intfar_kp": 5,
    "intfar_vision": 6,
    "doinks": 7,
    "doinks_kda": 8,
    "doinks_kills": 9,
    "doinks_damage": 10,
    "doinks_penta": 11,
    "doinks_vision": 12,
    "doinks_kp": 13,
    "doinks_monsters": 14
}

BETTING_DESC = {
    0: "winning the game",
    1: "losing the game",
    2: "someone being Int-Far",
    3: "someone being Int-Far by low KDA",
    4: "someone being Int-Far by many deaths",
    5: "someone being Int-Far by low KP",
    6: "someone being Int-Far by low vision score",
    7: "someone being awarded doinks",
    8: "someone being awarded doinks for high KDA",
    9: "someone being awarded doinks for many kills",
    10: "someone being awarded doinks for high damage",
    11: "someone being awarded doinks for getting a pentakill",
    12: "someone being awarded doinks for high vision score",
    13: "someone being awarded doinks for high KP",
    14: "someone being awarded doinks for securing all epic monsters"
}

def get_dynamic_bet_desc(event_id, target_person=None):
    bet_desc = BETTING_DESC[event_id].capitalize()
    if target_person is not None:
        bet_desc = bet_desc.replace("Someone", target_person)
    return bet_desc

def resolve_game_outcome(game_data, bet_on_win):
    stats = game_data[0][1]
    return not (stats["gameWon"] ^ bet_on_win)

def resolve_is_intfar(intfar, intfar_reason, target_id):
    if target_id is None: # Bet was about whether anyone was Int-Far.
        return intfar is not None
    return intfar == target_id # Bet was about a specific person being Int-Far.

def intfar_by_reason(intfar, reason_str, target_id, reason):
    reason_matches = reason_str[reason] == "1"
    if target_id is None:
        return reason_matches
    return intfar == target_id and reason_matches

def resolve_is_intfar_by_kda(intfar, intfar_reason, target_id):
    return intfar_by_reason(intfar, intfar_reason, target_id, 0)

def resolve_is_intfar_by_deaths(intfar, intfar_reason, target_id):
    return intfar_by_reason(intfar, intfar_reason, target_id, 1)

def resolve_is_intfar_by_kp(intfar, intfar_reason, target_id):
    return intfar_by_reason(intfar, intfar_reason, target_id, 2)

def resolve_is_intfar_by_vision(intfar, intfar_reason, target_id):
    return intfar_by_reason(intfar, intfar_reason, target_id, 3)

def resolve_got_doinks(doinks, target_id):
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

RESOLVE_INTFAR_BET_FUNCS = [
    resolve_is_intfar, resolve_is_intfar_by_kda, resolve_is_intfar_by_deaths,
    resolve_is_intfar_by_kp, resolve_is_intfar_by_vision
]

RESOLVE_DOINKS_BET_FUNCS = [
    resolve_got_doinks, resolve_doinks_for_kda, resolve_doinks_for_kills,
    resolve_doinks_for_damage, resolve_doinks_for_penta, resolve_doinks_for_vision,
    resolve_doinks_for_kp, resolve_doinks_for_monsters
]

class BettingHandler:
    MAX_BETTING_THRESHOLD = 10 # The latest a bet can be made (in game-time in minutes)
    MINIMUM_BETTING_AMOUNT = 5

    def __init__(self, database, config):
        self.database = database
        self.config = config

    def award_tokens_for_playing(self, disc_id, game_won):
        tokens_gained = (self.config.betting_tokens_for_win
                         if game_won
                         else self.config.betting_tokens_for_loss)
        self.database.update_token_balance(disc_id, tokens_gained, True)

    def get_active_bets(self, disc_id):
        return self.database.get_active_bets(disc_id)

    def get_bet_return_desc(self, bet_str):
        event_id = BETTING_IDS.get(bet_str)
        if event_id is None:
            return f"Invalid event to bet on: '{bet_str}'."

        event_desc = BETTING_DESC[event_id]

        base_return = self.database.get_bet_return(event_id)
        response = f"Betting on `{event_desc}` would return {base_return} times your investment.\n"
        response += "If you bet after the game has started, the return will be lower.\n"
        if event_id > 1:
            response += "If you bet on this event happening to a *specific* person "
            response += "(not just *anyone*), then the return will be further multiplied "
            response += "by how many people are in the game (2x return if 2 people are in "
            response += "the game, 3x return if 3 people, etc)."
        return response

    def get_bet_value(self, bet_amount, event_id, bet_timestamp):
        base_return = self.database.get_bet_return(event_id)
        if bet_timestamp == 0: # Bet was made before game started, award full value.
            ratio = 1.0
        else:
            max_time = 60 * BettingHandler.MAX_BETTING_THRESHOLD
            ratio = bet_timestamp / max_time # Scale value with game time at which bet was made.

        value = int(bet_amount * base_return * ratio)
        if value < 1:
            value = 1 # If value rounds down to 0, reward a minimum of 1 payout.

        return value, base_return, ratio

    def resolve_bet(self, disc_id, bet_id, amount, event_id, bet_timestamp, target_id, game_data):
        intfar, intfar_reason, doinks, game_stats = game_data
        # Multiplier for betting on a specific person to do something. If more people are
        # in the game, the multiplier is higher.
        person_multiplier = len(game_stats)
        success = False
        if event_id in (0, 1): # The bet concerns winning or losing the game.
            success = resolve_game_outcome(game_stats, event_id == 0)
        elif event_id < 7: # The bet concerns someone being Int-Far for something.
            resolve_func = RESOLVE_INTFAR_BET_FUNCS[event_id-2]
            success = resolve_func(intfar, intfar_reason, target_id)
        elif event_id < 15:
            resolve_func = RESOLVE_DOINKS_BET_FUNCS[event_id-7]
            success = resolve_func(doinks, target_id)

        bet_value = (self.get_bet_value(amount, event_id, bet_timestamp)[0]
                     if success
                     else 0)

        try:
            self.database.mark_bet_as_resolved(disc_id, bet_id, success, bet_value)
        except DBException:
            print_exc()
            self.config.log("Database error during bet resolution!", self.config.log_error)
            return

        return success, bet_value * person_multiplier

    def place_bet(self, disc_id, bet_amount, game_timestamp, bet_str, bet_target):
        event_id = BETTING_IDS.get(bet_str)
        tokens_name = self.config.betting_tokens
        if event_id is None:
            return f"Bet was not placed: Invalid event to bet on: '{bet_str}'."

        min_amount = BettingHandler.MINIMUM_BETTING_AMOUNT
        amount = 0
        try:
            amount = int(bet_amount)
            if amount < min_amount: # Bet was for less than the minimum allowed amount.
                return (
                    "Bet was not placed: Betting amount is too low. " +
                    f"Must be minimum {min_amount}."
                )
        except ValueError:
            return f"Bet was not placed: Invalid bet amount: '{bet_amount}'."

        duration = 0 if game_timestamp is None else time() - game_timestamp
        if duration > 60 * BettingHandler.MAX_BETTING_THRESHOLD:
            return (
                "Bet was not placed: The game is too far progressed. You must place bet before " +
                f"{BettingHandler.MAX_BETTING_THRESHOLD} minutes in game."
            )

        current_balance = 0

        try: # Actually save the bet in the database.
            if self.database.bet_exists(disc_id, event_id, bet_target):
                return "Bet was not placed: Such a bet has already been made!"
            current_balance = self.database.get_token_balance(disc_id)
            if current_balance >= amount:
                self.database.make_bet(disc_id, event_id, amount, duration, bet_target)
            else:
                return f"Bet was not placed: You do not have enough {tokens_name}."
        except DBException:
            print_exc()
            return "Bet was not placed: Database error occured :("

        bet_value, base_return, time_ratio = self.get_bet_value(amount, event_id, duration)

        bet_desc = BETTING_DESC[event_id]
        response = f"Bet succesfully placed: `{bet_desc}` for {amount} {tokens_name}.\n"
        response += f"The return for that event is {base_return}.\n"
        if duration == 0:
            response += "You placed your bet before the game started, "
            response += "you will get the full reward. Potential winnings:\n"
        else:
            response += "You placed your bet during the game, therefore "
            response += "you will not get the full reward. Potential winnings:\n"

        award_equation = f"{amount} x {base_return}"
        if duration > 0:
            award_equation += f" x {time_ratio}"
        if bet_target is not None:
            award_equation += " x [players_in_game]"
        award_equation += f" = {bet_value} {tokens_name}"

        if duration > 0:
            award_equation += f"\n{time_ratio} is a penalty for betting during the game."
        if bet_target is not None:
            award_equation += (
                "\n[players_in_game] is a multiplier. " +
                f"Because you bet on a specific person, you will get more {tokens_name} if " +
                "more players are in the game."
            )

        new_balance = current_balance - amount
        balance_resp = f"\nYour {tokens_name} balance is now `{new_balance}`."

        return response + award_equation + balance_resp

    def cancel_bet(self, disc_id, bet_amount, bet_str, game_timestamp, target):
        event_id = BETTING_IDS.get(bet_str)
        tokens_name = self.config.betting_tokens
        if event_id is None:
            return f"Bet was not cancelled: Not a valid betting event: '{bet_str}'"

        amount = 0
        try:
            amount = int(bet_amount)
        except ValueError:
            return f"Bet was not placed: Invalid bet amount: '{bet_amount}'."

        try:
            if not self.database.bet_exists(disc_id, event_id, target):
                return "Bet was not cancelled: No bet exists with the specified parameters."

            if game_timestamp is not None: # Game has already started.
                return "Bet was not cancelled: Game is underway!"

            self.database.cancel_bet(disc_id, event_id, amount, target)
            new_balance = self.database.get_token_balance(disc_id)

            bet_desc = BETTING_DESC[event_id]
            response = f"Bet on `{bet_desc}` for {amount} {tokens_name} successfully cancelled.\n"
            response += f"Your {tokens_name} balance is now `{new_balance}`."
            return response
        except DBException:
            print_exc()
            return "Bet was not cancelled: Database error occured :("
