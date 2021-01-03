from sys import argv
from discbot.test.assertion import Assertion
from api import bets
from api.database import Database
from api.config import Config

LOUD = False

def test_game_won_success(bet_handler, db_client, test_runner):
    disc_id = 267401734513491969
    bet_amount = ["20"]
    game_timestamp = None
    bet_str = ["game_win"]
    bet_target = [None]
    target_name = [None]
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
    test_runner.assert_equals(balance, 100 - int(bet_amount[0]), "Token balance after bet placed.")

    active_bets = bet_handler.get_active_bets(disc_id)

    test_runner.assert_equals(len(active_bets), 1, "# Active bets after bet placed.")

    bet_ids, amounts, event_ids, targets, bet_timestamp, _ = active_bets[0]

    test_runner.assert_equals(amounts[0], int(bet_amount[0]), "Bet amount.")
    test_runner.assert_equals(event_ids[0], bets.BETTING_IDS[bet_str[0]], "Bet event ID.")
    test_runner.assert_equals(bet_timestamp, 0, "Bet timestamp.")
    test_runner.assert_equals(targets[0], None, "Bet target.")

    success, bet_value = bet_handler.resolve_bet(disc_id, bet_ids, amounts, event_ids,
                                                 bet_timestamp, targets, game_data)

    base_return = db_client.get_base_bet_return(event_ids[0])

    test_runner.assert_equals(bet_value, int(bet_amount[0]) * base_return, "Bet value.")
    test_runner.assert_true(success, "Bet was won.")

    new_balance = db_client.get_token_balance(disc_id)

    test_runner.assert_equals(new_balance, 100 - int(bet_amount[0]) + bet_value, "Token balance after win.")

    active_bets = bet_handler.get_active_bets(disc_id)

    test_runner.assert_equals(len(active_bets), 0, "# Active bets after bet resolved.")

def test_game_won_fail(bet_handler, db_client, test_runner):
    disc_id = 267401734513491969
    bet_amount = ["30"]
    game_timestamp = None
    bet_str = ["game_win"]
    bet_target = [None]
    target_name = [None]
    game_data = (None, None, None, [(0, {"gameWon": False})])

    test_runner.set_current_test("Bet on game_win (fail)")
    wipe_db(db_client)

    success, response = bet_handler.place_bet(disc_id, bet_amount, game_timestamp,
                                              ["whew"], bet_target, target_name)

    if LOUD:
        print(response)

    test_runner.assert_false(success, "Bet not placed - Invalid event.")

    balance = db_client.get_token_balance(disc_id)

    test_runner.assert_equals(balance, 100, "Token balance not affected.")

    success, response = bet_handler.place_bet(disc_id, ["huehuehue"], game_timestamp,
                                              bet_str, bet_target, target_name)
    if LOUD:
        print(response)

    test_runner.assert_false(success, "Bet not placed - Invalid amount string.")

    success, response = bet_handler.place_bet(disc_id, ["-100"], game_timestamp,
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

    success, response = bet_handler.place_bet(disc_id, ["300"], game_timestamp,
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
    test_runner.assert_equals(balance, 100 - int(bet_amount[0]), "Token balance after bet placed.")

    active_bets = bet_handler.get_active_bets(disc_id)

    test_runner.assert_equals(len(active_bets), 1, "# Active bets after bet placed.")

    bet_ids, amounts, event_ids, targets, bet_timestamp, _ = active_bets[0]

    success, bet_value = bet_handler.resolve_bet(disc_id, bet_ids, amounts, event_ids,
                                                 bet_timestamp, targets, game_data)

    test_runner.assert_equals(bet_value, 0, "Bet value.")
    test_runner.assert_false(success, "Bet was lost.")

    new_balance = db_client.get_token_balance(disc_id)

    test_runner.assert_equals(new_balance, 100 - int(bet_amount[0]), "Token balance after loss.")

    active_bets = bet_handler.get_active_bets(disc_id)

    test_runner.assert_equals(len(active_bets), 0, "# Active bets after bet resolved.")

def test_no_intfar(bet_handler, db_client, test_runner):
    disc_id = 267401734513491969
    bet_amount = ["30"]
    game_timestamp = None
    bet_str = ["no_intfar"]
    bet_target = [None]
    target_name = [None]
    game_data = (None, None, None, [(0, {"gameWon": True})])

    test_runner.set_current_test("Bet on no Int-Far")
    wipe_db(db_client)

    success, response = bet_handler.place_bet(disc_id, bet_amount, game_timestamp,
                                              bet_str, bet_target, target_name)

    if LOUD:
        print(response)

    test_runner.assert_true(success, "Bet placed.")

    active_bets = bet_handler.get_active_bets(disc_id)

    test_runner.assert_equals(len(active_bets), 1, "# Active bets after bet placed.")

    bet_id, amount, event_id, target, bet_timestamp, _ = active_bets[0]

    success, _ = bet_handler.resolve_bet(disc_id, bet_id, amount, event_id,
                                         bet_timestamp, target, game_data)

    test_runner.assert_true(success, "Bet was won.")

    game_data = (267401734513491969, None, None, [(0, {"gameWon": True})])

    bet_handler.place_bet(disc_id, bet_amount, game_timestamp,
                          bet_str, bet_target, target_name)

    active_bets = bet_handler.get_active_bets(disc_id)

    bet_id, amount, event_id, target, bet_timestamp, _ = active_bets[0]

    success, _ = bet_handler.resolve_bet(disc_id, bet_id, amount, event_id,
                                         bet_timestamp, target, game_data)

    test_runner.assert_false(success, "Bet was lost.")

def test_award_tokens_for_game(bet_handler, db_client, test_runner):
    disc_id = 267401734513491969

    test_runner.set_current_test("Award tokens for game")
    wipe_db(db_client)

    balance = db_client.get_token_balance(disc_id)
    test_runner.assert_equals(balance, 100, "Token balance before game won.")

    token_gain = bet_handler.betting_tokens_for_win
    bet_handler.award_tokens_for_playing(disc_id, token_gain)

    balance = db_client.get_token_balance(disc_id)
    test_runner.assert_equals(balance, 100 + token_gain, "Token balance after game won.")

    db_client.update_token_balance(disc_id, token_gain, False)
    balance = db_client.get_token_balance(disc_id)

    test_runner.assert_equals(balance, 100, "Token balance before game lost.")

    token_gain = bet_handler.betting_tokens_for_loss
    bet_handler.award_tokens_for_playing(disc_id, token_gain)

    balance = db_client.get_token_balance(disc_id)
    test_runner.assert_equals(balance, 100 + token_gain, "Token balance after game lost.")

def test_dynamic_bet_return(bet_handler, db_client, test_runner):
    disc_id = 115142485579137029
    expected_results = [
        2.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
        1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 2.0,
        1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
        1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0
    ]

    test_runner.set_current_test("Dynamic bet return")
    wipe_db(db_client)

    for runs in range(2):
        target = disc_id if runs == 1 else None
        for index, event_name in enumerate(bets.BETTING_IDS):
            split = event_name.split("_")
            test_name = " ".join(word.capitalize() for word in split)
            if target is not None:
                test_name += " w/ Target"
            event_id = bets.BETTING_IDS[event_name]
            index += (runs * len(bets.BETTING_IDS))
            print((event_id, target))
            bet_return = bet_handler.get_dynamic_bet_return(event_id, target)

            test_runner.assert_equals(bet_return, expected_results[index], test_name)

def test_multi_bet_success(bet_handler, db_client, test_runner):
    disc_id = 267401734513491969

    bet_amount = ["30", "20"]
    game_timestamp = None
    bet_str = ["no_intfar", "game_win"]
    bet_target = [None, None]
    target_name = [None, None]
    game_data = (None, None, None, [(0, {"gameWon": True})])

    test_runner.set_current_test("Multi-bet (success)")
    wipe_db(db_client)

    success, response = bet_handler.place_bet(disc_id, bet_amount, game_timestamp,
                                              bet_str, bet_target, target_name)

    if LOUD:
        print(response)

    test_runner.assert_true(success, "Bet placed.")

    active_bets = bet_handler.get_active_bets(disc_id)

    test_runner.assert_equals(len(active_bets), 1, "# Active bets after bet placed.")

    bet_ids, amounts, event_ids, targets, bet_timestamp, _ = active_bets[0]

    success, _ = bet_handler.resolve_bet(disc_id, bet_ids, amounts, event_ids,
                                         bet_timestamp, targets, game_data)

    test_runner.assert_true(success, "Bet was won.")

    game_data = (267401734513491969, None, None, [(0, {"gameWon": True})])

    bet_handler.place_bet(disc_id, bet_amount, game_timestamp,
                          bet_str, bet_target, target_name)

    active_bets = bet_handler.get_active_bets(disc_id)

    bet_ids, amounts, event_ids, targets, bet_timestamp, _ = active_bets[0]

    success, _ = bet_handler.resolve_bet(disc_id, bet_ids, amounts, event_ids,
                                         bet_timestamp, targets, game_data)

    test_runner.assert_false(success, "Bet was lost (there was Int-Far).")

    game_data = (None, None, None, [(0, {"gameWon": False})])

    bet_handler.place_bet(disc_id, bet_amount, game_timestamp,
                          bet_str, bet_target, target_name)

    active_bets = bet_handler.get_active_bets(disc_id)

    bet_ids, amounts, event_ids, targets, bet_timestamp, _ = active_bets[0]

    success, _ = bet_handler.resolve_bet(disc_id, bet_ids, amounts, event_ids,
                                         bet_timestamp, targets, game_data)

    test_runner.assert_false(success, "Bet was lost (game lost).")

    bet_amount = ["30", "20"]
    game_timestamp = None
    bet_str = ["intfar", "most_kills"]
    bet_target = [115142485579137029, 267401734513491969]
    target_name = ["Dave", "Gual"]
    stats = [
        (115142485579137029, {"gameWon": True, "kills": 10}),
        (267401734513491969, {"gameWon": True, "kills": 20})
    ]
    game_data = (115142485579137029, None, None, stats)

    success, response = bet_handler.place_bet(disc_id, bet_amount, game_timestamp,
                                              bet_str, bet_target, target_name)

    if LOUD:
        print(response)

    active_bets = bet_handler.get_active_bets(disc_id)

    bet_ids, amounts, event_ids, targets, bet_timestamp, _ = active_bets[0]

    success, value = bet_handler.resolve_bet(disc_id, bet_ids, amounts, event_ids,
                                             bet_timestamp, targets, game_data)

    test_runner.assert_true(success, "Bet was won.")

    success, response = bet_handler.place_bet(disc_id, bet_amount, game_timestamp,
                                              bet_str, bet_target, target_name)

    if LOUD:
        print(response)

    balance_before = db_client.get_token_balance(disc_id)

    success, response = bet_handler.place_bet(disc_id, bet_amount, game_timestamp,
                                              bet_str, bet_target, target_name)

    active_bets = bet_handler.get_active_bets(disc_id)

    bet_ids, amounts, event_ids, targets, bet_timestamp, ticket = active_bets[0]

    success, response = bet_handler.cancel_bet(disc_id, ticket, game_timestamp,
                                               None, None)

    if LOUD:
        print(response)

    test_runner.assert_true(success, "Bet was cancelled.")

    balance_after = db_client.get_token_balance(disc_id)

    test_runner.assert_equals(balance_after, balance_before, "Tokens were refunded.")

def test_multi_bet_fail(bet_handler, db_client, test_runner):
    disc_id = 267401734513491969

    bet_amount = ["30", "20"]
    game_timestamp = None
    bet_str = ["no_intfar", "game_win"]
    bet_target = [None, None]
    target_name = [None, None]
    game_data = (None, None, None, [(0, {"gameWon": True})])

    test_runner.set_current_test("Multi-bet (fail)")
    wipe_db(db_client)

    success, response = bet_handler.place_bet(disc_id, bet_amount, game_timestamp,
                                              ["no_intfar", "whew"], bet_target, target_name)

    if LOUD:
        print(response)

    test_runner.assert_false(success, "Bet not placed - Invalid event.")

    balance = db_client.get_token_balance(disc_id)

    test_runner.assert_equals(balance, 100, "Token balance not affected.")

    success, response = bet_handler.place_bet(disc_id, ["20", "no"], game_timestamp,
                                              bet_str, bet_target, target_name)

    if LOUD:
        print(response)

    test_runner.assert_false(success, "Bet not placed - Invalid amount str.")

    success, response = bet_handler.place_bet(disc_id, ["20", "90"], game_timestamp,
                                              bet_str, bet_target, target_name)

    if LOUD:
        print(response)

    test_runner.assert_false(success, "Bet not placed - Not enough tokens 1.")

    success, response = bet_handler.place_bet(disc_id, ["all", "5"], game_timestamp,
                                              bet_str, bet_target, target_name)

    if LOUD:
        print(response)

    test_runner.assert_false(success, "Bet not placed - Not enough tokens 2.")

def wipe_db(db_client):
    db_client.reset_bets()

def run_tests():
    conf = Config()
    conf.database = "test.db"
    database_client = Database(conf)
    test_runner = Assertion()
    bet_handler = bets.BettingHandler(conf, database_client)

    test_to_run = -1
    if len(argv) > 1:
        test_to_run = int(argv[1])
        if len(argv) > 2:
            global LOUD
            LOUD = argv[2] == "1"

    tests = [
        test_game_won_success, test_game_won_fail,
        test_award_tokens_for_game, test_no_intfar,
        test_dynamic_bet_return, test_multi_bet_success,
        test_multi_bet_fail
    ]

    tests_to_run = tests if test_to_run == -1 else [tests[test_to_run]]

    for test in tests_to_run:
        test(bet_handler, database_client, test_runner)

    test_runner.print_test_summary()
