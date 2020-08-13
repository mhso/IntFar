from test.assertion import Assertion
import bets
from database import Database
from config import Config

LOUD = False

def test_game_won_success(bet_handler, db_client, test_runner):
    disc_id = 267401734513491969
    bet_amount = "20"
    game_timestamp = None
    bet_str = "game_win"
    bet_target = None
    target_name = None
    game_data = (None, None, None, [(0, {"gameWon": True})])

    test_runner.set_current_test("Bet on game_win (success)")
    wipe_db(db_client)

    balance = db_client.get_token_balance(disc_id)
    test_runner.assert_equals(balance, 100, "Token balance before bet placed.")

    success, response = bet_handler.place_bet(disc_id, bet_amount, game_timestamp,
                                              bet_str, bet_target, target_name)

    if LOUD:
        print(response)

    balance = db_client.get_token_balance(disc_id)

    test_runner.assert_true(success, "Bet placed.")
    test_runner.assert_equals(balance, 100 - int(bet_amount), "Token balance after bet placed.")

    active_bets = bet_handler.get_active_bets(disc_id)

    test_runner.assert_equals(len(active_bets), 1, "# Active bets after bet placed.")

    bet_id, amount, event_id, bet_timestamp, target = active_bets[0]

    test_runner.assert_equals(amount, int(bet_amount), "Bet amount.")
    test_runner.assert_equals(event_id, bets.BETTING_IDS[bet_str], "Bet event ID.")
    test_runner.assert_equals(bet_timestamp, 0, "Bet timestamp.")
    test_runner.assert_equals(target, None, "Bet target.")

    success, bet_value = bet_handler.resolve_bet(disc_id, bet_id, amount, event_id,
                                                 bet_timestamp, target, game_data)

    base_return = db_client.get_bet_return(event_id)

    test_runner.assert_equals(bet_value, int(bet_amount) * base_return, "Bet value.")
    test_runner.assert_true(success, "Bet was won.")

    new_balance = db_client.get_token_balance(disc_id)

    test_runner.assert_equals(new_balance, 100 - int(bet_amount) + bet_value, "Token balance after win.")

    active_bets = bet_handler.get_active_bets(disc_id)

    test_runner.assert_equals(len(active_bets), 0, "# Active bets after bet resolved.")

def test_game_won_fail(bet_handler, db_client, test_runner):
    disc_id = 267401734513491969
    bet_amount = "30"
    game_timestamp = None
    bet_str = "game_win"
    bet_target = None
    target_name = None
    game_data = (None, None, None, [(0, {"gameWon": False})])

    test_runner.set_current_test("Bet on game_win (fail)")
    wipe_db(db_client)

    success, response = bet_handler.place_bet(disc_id, bet_amount, game_timestamp,
                                              "whew", bet_target, target_name)

    if LOUD:
        print(response)

    test_runner.assert_false(success, "Bet not placed - Invalid event.")

    balance = db_client.get_token_balance(disc_id)

    test_runner.assert_equals(balance, 100, "Token balance not affected.")

    success, response = bet_handler.place_bet(disc_id, "huehuehue", game_timestamp,
                                              bet_str, bet_target, target_name)
    if LOUD:
        print(response)

    test_runner.assert_false(success, "Bet not placed - Invalid amount string.")

    success, response = bet_handler.place_bet(disc_id, "-100", game_timestamp,
                                              bet_str, bet_target, target_name)
    if LOUD:
        print(response)

    test_runner.assert_false(success, "Bet not placed - Amount too low.")

    timestamp_late = 60 * (bets.BettingHandler.MAX_BETTING_THRESHOLD)
    success, response = bet_handler.place_bet(disc_id, bet_amount, timestamp_late,
                                              bet_str, bet_target, target_name)
    if LOUD:
        print(response)

    test_runner.assert_false(success, "Bet not placed - Timestamp too late.")

    success, response = bet_handler.place_bet(disc_id, 300, game_timestamp,
                                              bet_str, bet_target, target_name)
    if LOUD:
        print(response)

    test_runner.assert_false(success, "Bet not placed - Too few tokens.")

    success, response = bet_handler.place_bet(disc_id, bet_amount, game_timestamp,
                                              bet_str, bet_target, target_name)
    if LOUD:
        print(response)

    balance = db_client.get_token_balance(disc_id)

    test_runner.assert_true(success, "Bet placed.")
    test_runner.assert_equals(balance, 100 - int(bet_amount), "Token balance after bet placed.")

    active_bets = bet_handler.get_active_bets(disc_id)

    test_runner.assert_equals(len(active_bets), 1, "# Active bets after bet placed.")

    bet_id, amount, event_id, bet_timestamp, target = active_bets[0]

    success, bet_value = bet_handler.resolve_bet(disc_id, bet_id, amount, event_id,
                                                 bet_timestamp, target, game_data)

    test_runner.assert_equals(bet_value, 0, "Bet value.")
    test_runner.assert_false(success, "Bet was lost.")

    new_balance = db_client.get_token_balance(disc_id)

    test_runner.assert_equals(new_balance, 100 - int(bet_amount), "Token balance after loss.")

    active_bets = bet_handler.get_active_bets(disc_id)

    test_runner.assert_equals(len(active_bets), 0, "# Active bets after bet resolved.")

def wipe_db(db_client):
    db_client.reset_bets()

def run_tests():
    conf = Config()
    conf.database = "test.db"
    database_client = Database(conf)
    test_runner = Assertion()
    bet_handler = bets.BettingHandler(conf, database_client)

    test_game_won_success(bet_handler, database_client, test_runner)
    test_game_won_fail(bet_handler, database_client, test_runner)

    test_runner.print_test_summary()
