from sys import argv
from test.runner import TestRunner, test
from api import bets, award_qualifiers
from api.database import Database
from api.config import Config
from api.util import format_tokens_amount
from api.game_stats import get_filtered_stats

LOUD = False

class TestWrapper(TestRunner):
    def __init__(self):
        super().__init__()
        conf = Config()
        conf.database = "test.db"
        database_client = Database(conf)
        bet_handler = bets.BettingHandler(conf, database_client)
        self.before_all(bet_handler, database_client)

    def before_test(self):
        self.test_args[1].reset_bets()

    @test
    def test_game_won_success(self, bet_handler, db_client):
        disc_id = 267401734513491969
        guild_id = 619073595561213953
        bet_amount = ["20"]
        game_timestamp = None
        bet_str = ["game_win"]
        bet_target = [None]
        target_name = [None]
        game_data = (None, None, None, [(0, {"gameWon": True})], 1)

        balance = db_client.get_token_balance(disc_id)
        self.assert_equals(balance, 100, "Token balance before bet placed.")

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp, bet_str, bet_target, target_name
        )

        if LOUD:
            print(response)

        balance = db_client.get_token_balance(disc_id)

        self.assert_true(success, "Bet placed.")
        self.assert_equals(balance, 100 - int(bet_amount[0]), "Token balance after bet placed.")

        active_bets = db_client.get_bets(True, disc_id)

        self.assert_equals(len(active_bets), 1, "# Active bets after bet placed.")

        bet_ids, g_id, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

        self.assert_equals(guild_id, g_id, "Guild ID.")
        self.assert_equals(amounts[0], int(bet_amount[0]), "Bet amount.")
        self.assert_equals(event_ids[0], bets.BETTING_IDS[bet_str[0]], "Bet event ID.")
        self.assert_equals(bet_timestamp, 0, "Bet timestamp.")
        self.assert_equals(targets[0], None, "Bet target.")

        success, bet_value = bet_handler.resolve_bet(disc_id, bet_ids, amounts, event_ids,
                                                     bet_timestamp, targets, game_data)

        base_return = db_client.get_base_bet_return(event_ids[0])

        self.assert_equals(bet_value, int(bet_amount[0]) * base_return, "Bet value.")
        self.assert_true(success, "Bet was won.")

        new_balance = db_client.get_token_balance(disc_id)

        self.assert_equals(new_balance, 100 - int(bet_amount[0]) + bet_value, "Token balance after win.")

        active_bets = db_client.get_bets(True, disc_id)

        self.assert_equals(active_bets, None, "No active bets after bet resolved.")

    @test
    def test_game_won_fail(self, bet_handler, db_client):
        disc_id = 267401734513491969
        guild_id = 619073595561213953
        bet_amounts = ["30"]
        game_timestamp = None
        bet_strs = ["game_win"]
        bet_targets = [None]
        target_names = [None]
        game_data = (None, None, None, [(0, {"gameWon": False})], 1)

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amounts, game_timestamp,
            ["whew"], bet_targets, target_names
        )

        if LOUD:
            print(response)

        self.assert_false(success, "Bet not placed - Invalid event.")

        balance = db_client.get_token_balance(disc_id)

        self.assert_equals(balance, 100, "Token balance not affected.")

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, ["huehuehue"], game_timestamp,
            bet_strs, bet_targets, target_names
        )
        if LOUD:
            print(response)

        self.assert_false(success, "Bet not placed - Invalid amount string.")

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, ["-100"], game_timestamp,
            bet_strs, bet_targets, target_names
        )
        if LOUD:
            print(response)

        self.assert_false(success, "Bet not placed - Amount too low.")

        timestamp_late = 60 * (bets.MAX_BETTING_THRESHOLD)
        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amounts, timestamp_late,
            bet_strs, bet_targets, target_names
        )
        if LOUD:
            print(response)

        self.assert_false(success, "Bet not placed - Timestamp too late.")

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, ["300"], game_timestamp,
            bet_strs, bet_targets, target_names
        )
        if LOUD:
            print(response)

        self.assert_false(success, "Bet not placed - Too few tokens.")

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amounts, game_timestamp,
            bet_strs, bet_targets, target_names
        )
        if LOUD:
            print(response)

        balance = db_client.get_token_balance(disc_id)

        self.assert_true(success, "Bet placed.")
        self.assert_equals(balance, 100 - int(bet_amounts[0]), "Token balance after bet placed.")

        active_bets = db_client.get_bets(True, disc_id)

        self.assert_equals(len(active_bets), 1, "# Active bets after bet placed.")

        bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

        success, bet_value = bet_handler.resolve_bet(
            disc_id, bet_ids, amounts, event_ids, bet_timestamp, targets, game_data
        )

        self.assert_equals(bet_value, 0, "Bet value.")
        self.assert_false(success, "Bet was lost.")

        new_balance = db_client.get_token_balance(disc_id)

        self.assert_equals(new_balance, 100 - int(bet_amounts[0]), "Token balance after loss.")

        active_bets = db_client.get_bets(True, disc_id)

        self.assert_equals(active_bets, None, "No active bets after bet resolved.")

    @test
    def test_no_intfar(self, bet_handler, db_client):
        disc_id = 267401734513491969
        guild_id = 619073595561213953
        bet_amount = ["30"]
        game_timestamp = None
        bet_str = ["no_intfar"]
        bet_target = [None]
        target_name = [None]
        game_data = (None, None, None, [(0, {"gameWon": True})], 1)

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp,
            bet_str, bet_target, target_name
        )

        if LOUD:
            print(response)

        self.assert_true(success, "Bet placed.")

        active_bets = db_client.get_bets(True, disc_id)

        self.assert_equals(len(active_bets), 1, "# Active bets after bet placed.")

        bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

        success, _ = bet_handler.resolve_bet(disc_id, bet_ids, amounts, event_ids,
                                            bet_timestamp, targets, game_data)

        self.assert_true(success, "Bet was won.")

        game_data = (267401734513491969, None, None, [(0, {"gameWon": True})], 1)

        bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp,
            bet_str, bet_target, target_name
        )

        active_bets = db_client.get_bets(True, disc_id)

        bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

        success, _ = bet_handler.resolve_bet(
            disc_id, bet_ids, amounts, event_ids,
            bet_timestamp, targets, game_data
        )

        self.assert_false(success, "Bet was lost.")

    @test
    def test_award_tokens_for_game(self, bet_handler, db_client):
        disc_id = 267401734513491969

        balance = db_client.get_token_balance(disc_id)
        self.assert_equals(balance, 100, "Token balance before game won.")

        token_gain = bet_handler.betting_tokens_for_win
        bet_handler.award_tokens_for_playing(disc_id, token_gain)

        balance = db_client.get_token_balance(disc_id)
        self.assert_equals(balance, 100 + token_gain, "Token balance after game won.")

        db_client.update_token_balance(disc_id, token_gain, False)
        balance = db_client.get_token_balance(disc_id)

        self.assert_equals(balance, 100, "Token balance before game lost.")

        token_gain = bet_handler.betting_tokens_for_loss
        bet_handler.award_tokens_for_playing(disc_id, token_gain)

        balance = db_client.get_token_balance(disc_id)
        self.assert_equals(balance, 100 + token_gain, "Token balance after game lost.")

    def test_dynamic_bet_return(self, bet_handler, db_client):
        disc_id = 115142485579137029 # Dave
        expected_results = [
            2.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 2.0, 2.0,
            1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0
        ]

        for runs in range(2):
            target = disc_id if runs == 1 else None
            for index, event_name in enumerate(bets.BETTING_IDS):
                split = event_name.split("_")
                test_name = " ".join(word.capitalize() for word in split)
                if target is not None:
                    test_name += " w/ Target"
                event_id = bets.BETTING_IDS[event_name]
                index += (runs * len(bets.BETTING_IDS))
                bet_return = bet_handler.get_dynamic_bet_return(event_id, target)

                self.assert_equals(bet_return, expected_results[index], test_name)

    @test
    def test_multi_bet_success(self, bet_handler, db_client):
        disc_id = 267401734513491969
        guild_id = 619073595561213953

        bet_amount = ["30", "20"]
        game_timestamp = None
        bet_str = ["no_intfar", "game_win"]
        bet_target = [None, None]
        target_name = [None, None]
        game_data = (None, None, None, [(0, {"gameWon": True})], 1)

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp,
            bet_str, bet_target, target_name
        )

        if LOUD:
            print(response)

        self.assert_true(success, "Bet placed.")

        active_bets = db_client.get_bets(True, disc_id)

        self.assert_equals(len(active_bets), 1, "# Active bets after bet placed.")

        bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

        success, _ = bet_handler.resolve_bet(
            disc_id, bet_ids, amounts, event_ids, bet_timestamp, targets, game_data
        )

        self.assert_true(success, "Bet was won.")

        game_data = (267401734513491969, None, None, [(0, {"gameWon": True})], 1)

        bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp,
            bet_str, bet_target, target_name
        )

        active_bets = db_client.get_bets(True, disc_id)

        bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

        success, _ = bet_handler.resolve_bet(
            disc_id, bet_ids, amounts, event_ids, bet_timestamp, targets, game_data
        )

        self.assert_false(success, "Bet was lost (there was Int-Far).")

        game_data = (None, None, None, [(0, {"gameWon": False})], 1)

        bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp,
            bet_str, bet_target, target_name
        )

        active_bets = db_client.get_bets(True, disc_id)

        bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

        success, _ = bet_handler.resolve_bet(
            disc_id, bet_ids, amounts, event_ids, bet_timestamp, targets, game_data
        )

        self.assert_false(success, "Bet was lost (game lost).")

        bet_amount = ["30", "20"]
        game_timestamp = None
        bet_str = ["intfar", "most_kills"]
        bet_target = [115142485579137029, 267401734513491969]
        target_name = ["Dave", "Gual"]
        stats = [
            (115142485579137029, {"gameWon": True, "kills": 10}),
            (267401734513491969, {"gameWon": True, "kills": 20})
        ]
        game_data = (115142485579137029, None, None, stats, 1)

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp,
            bet_str, bet_target, target_name
        )

        if LOUD:
            print(response)

        active_bets = db_client.get_bets(True, disc_id)

        bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

        success, value = bet_handler.resolve_bet(
            disc_id, bet_ids, amounts, event_ids, bet_timestamp, targets, game_data
        )

        self.assert_true(success, "Bet was won.")

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp,
            bet_str, bet_target, target_name
        )

        if LOUD:
            print(response)

        balance_before = db_client.get_token_balance(disc_id)

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp,
            bet_str, bet_target, target_name
        )

        active_bets = db_client.get_bets(True, disc_id)

        bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, ticket, _ = active_bets[0]

        success, response = bet_handler.cancel_bet(
            disc_id, guild_id, ticket, game_timestamp, None, None
        )

        if LOUD:
            print(response)

        self.assert_true(success, "Bet was cancelled.")

        balance_after = db_client.get_token_balance(disc_id)

        self.assert_equals(balance_after, balance_before, "Tokens were refunded.")

    @test
    def test_multi_bet_fail(self, bet_handler, db_client):
        disc_id = 267401734513491969
        guild_id = 619073595561213953

        bet_amount = ["30", "20"]
        game_timestamp = None
        bet_str = ["no_intfar", "game_win"]
        bet_target = [None, None]
        target_name = [None, None]

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp,
            ["no_intfar", "whew"], bet_target, target_name)

        if LOUD:
            print(response)

        self.assert_false(success, "Bet not placed - Invalid event.")

        balance = db_client.get_token_balance(disc_id)

        self.assert_equals(balance, 100, "Token balance not affected.")

        success, response, _  = bet_handler.place_bet(
            disc_id, guild_id, ["20", "no"], game_timestamp,
            bet_str, bet_target, target_name
        )

        if LOUD:
            print(response)

        self.assert_false(success, "Bet not placed - Invalid amount str.")

        success, response, _  = bet_handler.place_bet(
            disc_id, guild_id, ["20", "90"], game_timestamp,
            bet_str, bet_target, target_name
        )

        if LOUD:
            print(response)

        self.assert_false(success, "Bet not placed - Not enough tokens 1.")

        success, response, _  = bet_handler.place_bet(
            disc_id, guild_id, ["all", "5"], game_timestamp,
            bet_str, bet_target, target_name
        )

        if LOUD:
            print(response)

        self.assert_false(success, "Bet not placed - Not enough tokens 2.")

    @test
    def test_misc(self, bet_handler, db_client):
        tokens = [
            6, 100, 1000, 10000, 100000, 1000000000
        ]
        expected = [
            "6", "100", "1.000", "10.000", "100.000", "1.000.000.000"
        ]

        for token_amount, expected_format in zip(tokens, expected):
            formatted = format_tokens_amount(token_amount)

            self.assert_equals(
                formatted, expected_format, f"Formatted tokens, {expected_format}."
            )

        amount_strs = [
            "10", "100", "100000", "1K", "1k", "3B", "3.5b",
            "7.2M", "132.213M", "4T", "12.321312572T", "1.2345K"
        ]
        expected = [
            10, 100, 100000, 1000, 1000, 3000000000, 3500000000,
            7200000, 132213000, int(4e12), 12321312572000, 1234
        ]

        for amount_str, expected_format in zip(amount_strs, expected):
            formatted = bet_handler.parse_bet_amount(amount_str)

            self.assert_equals(
                formatted, expected_format, f"Betting amount success - {expected_format}."
            )
