from time import time
from datetime import datetime
from traceback import print_exc
from api.database import DBException
from api.util import format_duration, round_digits, format_tokens_amount
from api import game_stats

MAX_BETTING_THRESHOLD = 5 # The latest a bet can be made (in game-time in minutes)
MINIMUM_BETTING_AMOUNT = 5

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

BETTING_TYPES_INDICES = {
    "game": 0,
    "intfar": 2,
    "intfar_reason": 4,
    "doinks": 8,
    "doinks_reason": 8,
    "stats": 17
}

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

def get_dynamic_bet_desc(event_id, target_person=None):
    bet_desc = BETTING_DESC[event_id]
    if target_person is not None:
        bet_desc = bet_desc.replace("someone", target_person)
    return bet_desc

def bet_requires_target(event_id):
    return event_id > 15

def bet_requires_no_target(event_id):
    return event_id < 3

def resolve_game_outcome(game_data, bet_on_win):
    stats = game_data[0][1]
    return not (stats["gameWon"] ^ bet_on_win)

def resolve_is_intfar(intfar, intfar_reason, target_id):
    if target_id is None: # Bet was about whether anyone was Int-Far.
        return intfar is not None
    return intfar == target_id # Bet was about a specific person being Int-Far.

def resolve_not_intfar(intfar, intfar_reason, target_id):
    return not resolve_is_intfar(intfar, intfar_reason, None)

def intfar_by_reason(intfar, reason_str, target_id, reason):
    return (resolve_is_intfar(intfar, reason_str, target_id)
            and reason_str[reason] == "1")

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
    resolve_doinks_for_kp, resolve_doinks_for_monsters
]

RESOLVE_STATS_BET_FUNCS = [
    resolve_most_kills, resolve_most_damage, resolve_highest_kp, resolve_highest_kda
]

class BettingHandler:
    def __init__(self, config, database):
        self.config = config
        self.database = database
        self.betting_tokens_for_win = config.betting_tokens_for_win
        self.betting_tokens_for_loss = config.betting_tokens_for_loss

    def award_tokens_for_playing(self, disc_id, tokens_gained):
        self.database.update_token_balance(disc_id, tokens_gained, True)

    def get_bet_return_desc(self, bet_str, target_id, target_name):
        event_id = BETTING_IDS.get(bet_str)
        if event_id is None:
            return f"Invalid event to bet on: '{bet_str}'."

        event_desc = get_dynamic_bet_desc(event_id, target_name)

        base_return = self.get_dynamic_bet_return(event_id, target_id)
        readable_return = round_digits(base_return)

        response = f"Betting on `{event_desc}` would return {readable_return} times your investment.\n"
        response += "If you bet after the game has started, the return will be lower.\n"
        if event_id > 2:
            start = "If" if target_id is None else "Since"
            response += f"{start} you bet on this event happening to a *specific* person "
            response += "(not just *anyone*), then the return will be further multiplied "
            response += "by how many people are in the game (2x return if 2 people are in "
            response += "the game, 3x return if 3 people, etc)."
        return response

    def get_intfar_return(self, target, is_intfar):
        if target is None or not is_intfar:
            games_total = self.database.get_games_count()[0]
            intfars_total = self.database.get_intfar_count()[0]
            intfar_count = intfars_total if is_intfar else games_total - intfars_total
            return intfar_count, games_total

        games_played, intfar_reason_ids = self.database.get_intfar_stats(target)
        return len(intfar_reason_ids), games_played

    def get_intfar_reason_return(self, target, reason):
        reason_count = 0
        num_games = 0
        if target is None:
            intfar_reason_ids = self.database.get_intfar_reason_counts()[0]
            num_games = self.database.get_games_count()[0]
            reason_count = intfar_reason_ids[reason]
        else:
            num_games, intfar_reason_ids = self.database.get_intfar_stats(target)
            for reason_id in intfar_reason_ids:
                if reason_id[0][reason] == "1":
                    reason_count += 1

        return reason_count, num_games

    def get_doinks_return(self, target):
        if target is None:
            games_total = self.database.get_games_count()[0]
            doinks_total = self.database.get_doinks_count()[0]
            return doinks_total, games_total

        games_played = self.database.get_intfar_stats(target)[0]
        doinks_reason_ids = self.database.get_doinks_stats(target)

        return len(doinks_reason_ids), games_played

    def get_doinks_reason_return(self, target, reason):
        reason_count = 0
        num_games = 0
        if target is None:
            doinks_reason_ids = self.database.get_doinks_reason_counts()
            num_games = self.database.get_games_count()[0]
            reason_count = doinks_reason_ids[reason]
        else:
            num_games = self.database.get_intfar_stats(target)[0]
            doinks_reason_ids = self.database.get_doinks_stats(target)
            for reason_id in doinks_reason_ids:
                if reason_id[0][reason] == "1":
                    reason_count += 1

        return reason_count, num_games

    def get_stats_return(self, target, stat_id):
        stat = BETTING_STATS[stat_id]
        best_in_stat_count = self.database.get_stat(stat, True, target)[0]
        num_games = self.database.get_intfar_stats(target)[0]
        return best_in_stat_count, num_games

    def get_dynamic_bet_return(self, event_id, target):
        if event_id > 1:
            count = 0
            num_games = 0
            if event_id < BETTING_TYPES_INDICES["intfar_reason"]:
                count, num_games = self.get_intfar_return(target, event_id == 3)
            elif event_id < BETTING_TYPES_INDICES["doinks"]:
                count, num_games = self.get_intfar_reason_return(target, event_id - BETTING_TYPES_INDICES["intfar_reason"])
            elif event_id == BETTING_TYPES_INDICES["doinks"]:
                count, num_games = self.get_doinks_return(target)
            elif event_id < BETTING_TYPES_INDICES["stats"]:
                count, num_games = self.get_doinks_reason_return(target, event_id - BETTING_TYPES_INDICES["doinks_reason"])
            elif event_id < len(BETTING_TYPES_INDICES):
                count, num_games = self.get_stats_return(target, event_id - BETTING_TYPES_INDICES["stats"])

            if num_games == 0: # No games has been played for given target, ratio is 0.
                return self.database.get_base_bet_return(event_id)
            if count == 0: # Event never happened, set ratio to amount of games played.
                return num_games

            return num_games / count

        return self.database.get_base_bet_return(event_id)

    def get_bet_value(self, bet_amount, event_id, bet_timestamp, target):
        base_return = self.get_dynamic_bet_return(event_id, target)
        if bet_timestamp <= 2: # Bet was made before game started, award full value.
            ratio = 1.0
        else: # Scale value with game time at which bet was made.
            max_time = 60 * MAX_BETTING_THRESHOLD
            ratio = 1 - ((bet_timestamp - 2) / max_time)

        value = int(bet_amount * base_return * ratio)
        if value < 1:
            value = 1 # If value rounds down to 0, reward a minimum of 1 payout.

        return value, base_return, ratio

    def resolve_bet(
            self, disc_id, bet_ids, amounts, events, bet_timestamp, targets, game_data
    ):
        intfar, intfar_reason, doinks, stats, clash_multiplier = game_data
        # Multiplier for betting on a specific person to do something. If more people are
        # in the game, the multiplier is higher.
        person_multiplier = len(stats)
        amount_multiplier = len(amounts)
        self.config.log(f"Disc ID: {disc_id}")
        self.config.log(f"Person multiplier: {person_multiplier}")
        self.config.log(f"Amount of bets: {amount_multiplier}")
        total_value = 0
        all_success = True
        for amount, event_id, target_id in zip(amounts, events, targets):
            success = False
            if event_id in (0, 1): # The bet concerns winning or losing the game.
                success = resolve_game_outcome(stats, event_id == 0)
            elif event_id < BETTING_TYPES_INDICES["doinks"]: # The bet concerns someone being Int-Far for something.
                resolve_func = RESOLVE_INTFAR_BET_FUNCS[event_id - BETTING_TYPES_INDICES["intfar"]]
                success = resolve_func(intfar, intfar_reason, target_id)
            elif event_id < BETTING_TYPES_INDICES["stats"]:
                resolve_func = RESOLVE_DOINKS_BET_FUNCS[event_id - BETTING_TYPES_INDICES["doinks"]]
                success = resolve_func(doinks, target_id)
            elif event_id < len(BETTING_TYPES_INDICES):
                resolve_func = RESOLVE_STATS_BET_FUNCS[event_id - BETTING_TYPES_INDICES["stats"]]
                success = resolve_func(stats, target_id)

            all_success = all_success and success

            bet_value = (self.get_bet_value(amount, event_id, bet_timestamp, target_id)[0]
                         if success
                         else 0)

            if target_id is not None:
                bet_value = bet_value * person_multiplier

            total_value += bet_value

        total_value = total_value * amount_multiplier * clash_multiplier
        timestamp = int(time())

        for bet_id in bet_ids:
            try:
                self.database.mark_bet_as_resolved(bet_id, timestamp, all_success, total_value)
            except DBException:
                print_exc()
                self.config.log("Database error during bet resolution!", self.config.log_error)
                return

        if all_success:
            self.database.update_token_balance(disc_id, total_value, True)

        return all_success, total_value

    def get_bet_placed_text(self, data, all_in, duration, ticket=None):
        tokens_name = self.config.betting_tokens

        response = ""
        if len(data) > 1:
            response = "Multi-bet successfully placed! "
            response += "You bet on **all** the following happening:"

            for amount, _, _, base_return, bet_desc in data:
                response += f"\n - `{bet_desc}` for **{format_tokens_amount(amount)}** {tokens_name} "
                response += f"(**{base_return}x** return)."
            response += f"\nThis bet uses the following ticket ID: {ticket}. "
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
        return f"Bet was not placed: {bet_desc} - {error}"

    def parse_bet_amount(self, amount_str):
        mult = 1
        if amount_str[-1].lower() == "t":
            mult = 1e12
            amount_str = amount_str[:-1]
        elif amount_str[-1].lower() == "b":
            mult = 1e9
            amount_str = amount_str[:-1]
        elif amount_str[-1].lower() == "m":
            mult = 1e6
            amount_str = amount_str[:-1]
        elif amount_str[-1].lower() == "k":
            mult = 1e3
            amount_str = amount_str[:-1]

        return int(float(amount_str) * mult)

    def check_bet_validity(
            self, disc_id, guild_id, bet_amount, game_timestamp,
            bet_str, balance, bet_target, target_name, ticket
    ):
        event_id = BETTING_IDS.get(bet_str)
        tokens_name = self.config.betting_tokens
        if event_id is None:
            return (False, f"Bet was not placed: Invalid event to bet on: '{bet_str}'.")

        if bet_requires_no_target(event_id):
            bet_target = None
            target_name = None

        bet_desc = get_dynamic_bet_desc(event_id, target_name)

        if bet_requires_target(event_id) and bet_target is None:
            err_msg = self.get_bet_error_msg(bet_desc, "A person is required as the 'target' of that bet.")
            return (False, err_msg)

        min_amount = MINIMUM_BETTING_AMOUNT
        amount = 0
        try:
            amount = balance if bet_amount == "all" else self.parse_bet_amount(bet_amount.strip())

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
        if balance < amount:
            err_msg = self.get_bet_error_msg(bet_desc, f"You do not have enough {tokens_name}.")
            return (False, err_msg)
        return (True, (amount, event_id, duration, bet_desc))

    def place_bet(self, disc_id, guild_id, amounts, game_timestamp, events, targets, target_names):
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
            for bet_amount, event, target, target_name in zip(amounts, events, targets, target_names):
                valid, data = self.check_bet_validity(
                    disc_id, guild_id, bet_amount, game_timestamp, event,
                    balance, target, target_name, ticket
                )

                if not valid:
                    return (False, data, None)

                amount, event_id, game_duration, bet_desc = data

                if (event_id, target) in used_events:
                    return (False, "Error: Duplicate Event in bet.", None)

                used_events.add((event_id, target))

                balance -= amount

                bet_value, base_return, time_ratio = self.get_bet_value(amount, event_id,
                                                                        game_duration, target)

                final_value += bet_value
                return_readable = round_digits(base_return)

                bet_data.append((amount, event_id, target, return_readable, bet_desc))

            for amount, event_id, bet_target, base_return, bet_desc in bet_data:
                bet_id = self.database.make_bet(
                    disc_id, guild_id, event_id, amount,
                    game_duration, bet_target, ticket
                )

                if not first:
                    reward_equation += " + "
                reward_equation += f"{amount} x {base_return}"

                if bet_target is not None:
                    reward_equation += " x [players_in_game]"
                    any_target = True

                first = False
        except DBException:
            print_exc()
            return (False, "Bet was not placed: Database error occured :(", None)

        final_value *= len(amounts)
        if len(amounts) > 1:
            reward_equation = "(" + reward_equation
            reward_equation += f") x {len(amounts)}"

        ratio_readable = round_digits(time_ratio)
        if game_duration > 0:
            reward_equation += f" x {ratio_readable}"

        reward_equation += f" = **{format_tokens_amount(final_value)}** {tokens_name}"

        if any_target:
            reward_equation += " (minimum)\n"

        if game_duration > 0:
            dt_start = datetime.fromtimestamp(game_timestamp)
            dt_now = datetime.fromtimestamp(time())
            duration_fmt = format_duration(dt_start, dt_now)
            reward_equation += f"\n{ratio_readable} is a penalty for betting "
            reward_equation += f"{duration_fmt} after the game started."

        if any_target:
            reward_equation += (
                "[players_in_game] is a multiplier. " +
                f"Because you bet on a specific person, you will get more {tokens_name} if " +
                "more players are in the game."
            )

        bet_all = len(amounts) == 1 and amounts[0] == "all"

        response = self.get_bet_placed_text(bet_data, bet_all, game_duration, ticket)

        balance_resp = f"\nYour {tokens_name} balance is now `{format_tokens_amount(balance)}`."

        bet_id = None if len(amounts) > 1 else bet_id

        return (True, response + reward_equation + balance_resp, (bet_id, ticket))

    def delete_bet(self, disc_id, bet_id, ticket, game_timestamp):
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

    def cancel_bet(self, disc_id, guild_id, bet_str, game_timestamp, target_id, target_name):
        ticket = None
        event_id = BETTING_IDS.get(bet_str)
        tokens_name = self.config.betting_tokens
        if event_id is None:
            try:
                ticket = int(bet_str)
            except ValueError:
                return (False, f"Bet was not cancelled: Not a valid betting event: '{bet_str}'")

        try:
            bet_id = self.database.get_bet_id(disc_id, event_id, guild_id, target_id, ticket)
            if bet_id is None:
                return (False, "Bet was not cancelled: No bet exists with the specified parameters.")

            success, data = self.delete_bet(disc_id, bet_id, ticket, game_timestamp)
            if not success:
                return (False, data)

            new_balance, amount_refunded = data
            if ticket is None:
                bet_desc = get_dynamic_bet_desc(event_id, target_name)
                response = f"Bet on `{bet_desc}` for {format_tokens_amount(amount_refunded)} {tokens_name} successfully cancelled.\n"
            else:
                response = f"Multi-bet with ticket ID {ticket} successfully cancelled.\n"
            response += f"Your {tokens_name} balance is now `{format_tokens_amount(new_balance)}`."
            return (True, response)
        except DBException:
            print_exc()
            return (False, "Bet was not cancelled: Database error occured :(")

    def get_gift_err_msg(self, err_msg):
        return f"Transfer failed: {err_msg}"

    def give_tokens(self, disc_id, amount_str, receiver_id, receiver_name):
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
            amount = balance if amount_str == "all" else self.parse_bet_amount(amount_str)
        except ValueError:
            err_msg = self.get_gift_err_msg(f"Invalid token amount: '{amount_str}'.")
            return (False, err_msg)

        if balance < amount:
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
