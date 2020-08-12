from shutil import copyfile
from os import remove
from test.assertion import Assertion
import bets
from database import Database
from config import Config

LOUD = False

def run_tests():
    conf = Config()
    copyfile("database.db", "test.db")
    conf.database = "test.db"
    database_client = Database(conf)
    test_runner = Assertion()
    bet_handler = bets.BettingHandler(conf, database_client)

    game_data = [(0, {"gameWon": True})]  

    disc_id = 267401734513491969
    bet_amount = 20
    game_timestamp = None
    bet_str = "game_win"
    bet_target = None
    target_name = None

    balance = database_client.get_token_balance(disc_id)
    test_runner.assert_equals(balance, 100, "Game Won Bet - Token balance before.")

    success, response = bet_handler.place_bet(disc_id, bet_amount, game_timestamp,
                                              bet_str, bet_target, target_name)

    if LOUD:
        print(response)

    balance = database_client.get_token_balance(disc_id)

    test_runner.assert_true(success, "Game Won Bet - Bet placed.")
    test_runner.assert_equals(balance, 100 - bet_amount, "Game Won Bet - Token balance after.")

    active_bets = bet_handler.get_active_bets(disc_id)

    test_runner.assert_equals(len(active_bets), 1, "Game Won Bet - # Active bets equals 1")

    bet_id, amount, event_id, bet_timestamp, target = active_bets[0]

    bet_handler.resolve_bet(disc_id, bet_id, amount, event_id, bet_timestamp, target, None)

    test_runner.print_test_summary()

    remove("test.db")
