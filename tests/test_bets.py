from time import time
from test.runner import TestRunner, test
from api.bets import get_betting_handler
from api.betting import BettingHandler, MAX_BETTING_THRESHOLD
from api.meta_database import Database
from api.config import Config
from api.util import format_tokens_amount, SUPPORTED_GAMES
from api.game_data.lol import LoLGameStats, LoLPlayerStats
from api.game_data.cs2 import CS2GameStats, CS2PlayerStats

LOUD = False

class TestWrapper(TestRunner):
    def __init__(self):
        super().__init__()
        conf = Config()
        conf.database = f"{conf.resources_folder}/test.db"
        database_client = Database(conf)
        bet_handlers = {
            game: get_betting_handler(game, conf, database_client)
            for game in SUPPORTED_GAMES
        }
        self.before_all(bet_handlers=bet_handlers, db_client=database_client)

    def before_test(self):
        self.db_client.reset_bets()

    @test
    def test_game_won_success(self):
        disc_id = 267401734513491969
        guild_id = 619073595561213953
        bet_amount = ["20"]
        game_timestamp = None
        bet_str = ["game_win"]
        bet_targets = [None]
        target_names = [None]

        for game in SUPPORTED_GAMES:
            self.db_client.reset_bets()
            cls = LoLGameStats if game == "lol" else CS2GameStats
            game_data = cls(game, 0, game_timestamp, 0, 1, guild_id, [], [])
            bet_handler: BettingHandler = self.bet_handlers[game]

            balance = self.db_client.get_token_balance(disc_id)
            self.assert_equals(balance, 100, "Token balance before bet placed.")

            success, response, _ = bet_handler.place_bet(
                disc_id, guild_id, bet_amount, game_timestamp, bet_str, bet_targets, target_names
            )

            if LOUD:
                print(response)

            balance = self.db_client.get_token_balance(disc_id)

            self.assert_true(success, "Bet placed.")
            self.assert_equals(balance, 100 - int(bet_amount[0]), "Token balance after bet placed.")

            active_bets = self.db_client.get_bets(game, True, disc_id)

            self.assert_equals(len(active_bets), 1, "# Active bets after bet placed.")

            bet_ids, g_id, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

            bet = bet_handler.get_bet(bet_str[0])

            self.assert_equals(guild_id, g_id, "Guild ID.")
            self.assert_equals(amounts[0], int(bet_amount[0]), "Bet amount.")
            self.assert_equals(event_ids[0], bet.event_id, "Bet event ID.")
            self.assert_equals(bet_timestamp, 0, "Bet timestamp.")
            self.assert_equals(targets[0], None, "Bet target.")

            success, bet_value = bet_handler.resolve_bet(
                disc_id,
                bet_ids,
                amounts,
                bet_timestamp,
                event_ids,
                targets,
                game_data,
                1
            )

            self.assert_equals(bet_value, int(bet_amount[0]) * bet.base_return, "Bet value.")
            self.assert_true(success, "Bet was won.")

            new_balance = self.db_client.get_token_balance(disc_id)

            self.assert_equals(new_balance, 100 - int(bet_amount[0]) + bet_value, "Token balance after win.")

            active_bets = self.db_client.get_bets(game, True, disc_id)

            self.assert_equals(active_bets, None, "No active bets after bet resolved.")

    @test
    def test_game_won_fail(self):
        disc_id = 267401734513491969
        guild_id = 619073595561213953
        bet_amounts = ["30"]
        game_timestamp = None
        bet_strs = ["game_win"]
        bet_targets = [None]
        target_names = [None]
        for game in SUPPORTED_GAMES:
            self.db_client.reset_bets()
            cls = LoLGameStats if game == "lol" else CS2GameStats
            game_data = cls(game, 0, game_timestamp, 0, -1, guild_id, [], [])
            bet_handler: BettingHandler = self.bet_handlers[game]

            success, response, _ = bet_handler.place_bet(
                disc_id, guild_id, bet_amounts, game_timestamp,
                ["whew"], bet_targets, target_names
            )

            if LOUD:
                print(response)

            self.assert_false(success, "Bet not placed - Invalid event.")

            balance = self.db_client.get_token_balance(disc_id)

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

            timestamp_late = 60 * MAX_BETTING_THRESHOLD
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

            balance = self.db_client.get_token_balance(disc_id)

            self.assert_true(success, "Bet placed.")
            self.assert_equals(balance, 100 - int(bet_amounts[0]), "Token balance after bet placed.")

            active_bets = self.db_client.get_bets(game, True, disc_id)

            self.assert_equals(len(active_bets), 1, "# Active bets after bet placed.")

            bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

            success, bet_value = bet_handler.resolve_bet(
                disc_id,
                bet_ids,
                amounts,
                bet_timestamp,
                event_ids,
                targets,
                game_data
            )

            self.assert_equals(bet_value, 0, "Bet value.")
            self.assert_false(success, "Bet was lost.")

            new_balance = self.db_client.get_token_balance(disc_id)

            self.assert_equals(new_balance, 100 - int(bet_amounts[0]), "Token balance after loss.")

            active_bets = self.db_client.get_bets(game, True, disc_id)

            self.assert_equals(active_bets, None, "No active bets after bet resolved.")

    @test
    def test_no_intfar(self):
        disc_id = 267401734513491969
        guild_id = 619073595561213953
        bet_amount = ["30"]
        game_timestamp = None
        bet_str = ["no_intfar"]
        bet_targets = [None]
        target_names = [None]
    
        for game in SUPPORTED_GAMES:
            self.db_client.reset_bets()
            cls = LoLGameStats if game == "lol" else CS2GameStats
            game_data = cls(game, 0, game_timestamp, 0, 1, guild_id, [], [])
            bet_handler: BettingHandler = self.bet_handlers[game]

            success, response, _ = bet_handler.place_bet(
                disc_id, guild_id, bet_amount, game_timestamp,
                bet_str, bet_targets, target_names
            )

            if LOUD:
                print(response)

            self.assert_true(success, "Bet placed.")

            active_bets = self.db_client.get_bets(game, True, disc_id)

            self.assert_equals(len(active_bets), 1, "# Active bets after bet placed.")

            bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

            success, _ = bet_handler.resolve_bet(
                disc_id,
                bet_ids,
                amounts,
                bet_timestamp,
                event_ids,
                targets,
                game_data
            )

            self.assert_true(success, "Bet was won.")

            game_data = cls(game, 0, game_timestamp, 0, 1, guild_id, [], [], intfar_id=disc_id)

            bet_handler.place_bet(
                disc_id, guild_id, bet_amount, game_timestamp,
                bet_str, bet_targets, target_names
            )

            active_bets = self.db_client.get_bets(game, True, disc_id)

            bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

            success, _ = bet_handler.resolve_bet(
                disc_id,
                bet_ids,
                amounts,
                bet_timestamp,
                event_ids,
                targets,
                game_data
            )

            self.assert_false(success, "Bet was lost.")

    @test
    def test_award_tokens_for_game(self):
        disc_id = 267401734513491969

        for game in SUPPORTED_GAMES:
            self.db_client.reset_bets()
            balance = self.db_client.get_token_balance(disc_id)
            self.assert_equals(balance, 100, "Token balance before game won.")
            bet_handler: BettingHandler = self.bet_handlers[game]

            token_gain = bet_handler.betting_tokens_for_win
            bet_handler.award_tokens_for_playing(disc_id, token_gain)

            balance = self.db_client.get_token_balance(disc_id)
            self.assert_equals(balance, 100 + token_gain, "Token balance after game won.")

            self.db_client.update_token_balance(disc_id, token_gain, False)
            balance = self.db_client.get_token_balance(disc_id)

            self.assert_equals(balance, 100, "Token balance before game lost.")

            token_gain = bet_handler.betting_tokens_for_loss
            bet_handler.award_tokens_for_playing(disc_id, token_gain)

            balance = self.db_client.get_token_balance(disc_id)
            self.assert_equals(balance, 100 + token_gain, "Token balance after game lost.")

    @test
    def test_multi_bet_success(self):
        disc_id = 267401734513491969
        guild_id = 619073595561213953

        for game in SUPPORTED_GAMES:
            bet_amount = ["30", "20"]
            game_timestamp = None
            bet_str = ["no_intfar", "game_win"]
            bet_target = [None, None]
            target_name = [None, None]

            self.db_client.reset_bets()
            cls = LoLGameStats if game == "lol" else CS2GameStats
            game_data = cls(game, 0, game_timestamp, 0, 1, guild_id, [], [])
            bet_handler: BettingHandler = self.bet_handlers[game]

            success, response, _ = bet_handler.place_bet(
                disc_id, guild_id, bet_amount, game_timestamp,
                bet_str, bet_target, target_name
            )

            if LOUD:
                print(response)

            self.assert_true(success, "Bet placed.")

            active_bets = self.db_client.get_bets(game, True, disc_id)

            self.assert_equals(len(active_bets), 1, "# Active bets after bet placed.")

            bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

            success, _ = bet_handler.resolve_bet(
                disc_id,
                bet_ids,
                amounts,
                bet_timestamp,
                event_ids,
                targets,
                game_data
            )

            self.assert_true(success, "Bet was won.")

            game_data = cls(game, 0, game_timestamp, 0, 1, guild_id, [], [], intfar_id=disc_id)

            bet_handler.place_bet(
                disc_id, guild_id, bet_amount, game_timestamp,
                bet_str, bet_target, target_name
            )

            active_bets = self.db_client.get_bets(game, True, disc_id)

            bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

            success, _ = bet_handler.resolve_bet(
                disc_id,
                bet_ids,
                amounts,
                bet_timestamp,
                event_ids,
                targets,
                game_data
            )

            self.assert_false(success, "Bet was lost (there was an Int-Far).")

            game_data = cls(game, 0, game_timestamp, 0, -1, guild_id, [], [])

            bet_handler.place_bet(
                disc_id, guild_id, bet_amount, game_timestamp,
                bet_str, bet_target, target_name
            )

            active_bets = self.db_client.get_bets(game, True, disc_id)

            bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

            success, _ = bet_handler.resolve_bet(
                disc_id,
                bet_ids,
                amounts,
                bet_timestamp,
                event_ids,
                targets,
                game_data
            )

            self.assert_false(success, "Bet was lost (game lost).")

            # Intfar and most kills
            bet_amount = ["30", "20"]
            game_timestamp = None
            bet_str = ["intfar", "most_kills"]
            bet_target = [115142485579137029, 267401734513491969]
            target_name = ["Dave", "Gual"]
            disc_id_2 = 115142485579137029
            game_id = 1

            player_cls = LoLPlayerStats if game == "lol" else CS2PlayerStats
            players = [
                player_cls(game_id, disc_id_2, 10, 1, 0),
                player_cls(game_id, disc_id, 20, 1, 0)
            ]
            game_data = cls(game, game_id, game_timestamp, 0, 1, guild_id, [], players, intfar_id=disc_id_2)

            success, response, _ = bet_handler.place_bet(
                disc_id, guild_id, bet_amount, game_timestamp,
                bet_str, bet_target, target_name
            )

            if LOUD:
                print(response)

            active_bets = self.db_client.get_bets(game, True, disc_id)

            bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

            success, _ = bet_handler.resolve_bet(
                disc_id,
                bet_ids,
                amounts,
                bet_timestamp,
                event_ids,
                targets,
                game_data
            )

            self.assert_true(success, "Bet was won.")

            # Game win and doinks
            bet_amount = ["30", "20"]
            game_timestamp = None
            bet_str = ["game_win", "doinks"]
            bet_target = [None, None]
            target_name = [None, None]
            game_id = 1

            player_cls = LoLPlayerStats if game == "lol" else CS2PlayerStats
            players = [
                player_cls(game_id, disc_id, 20, 1, 0, "11000000")
            ]
            game_data = cls(game, game_id, game_timestamp, 0, 1, guild_id, [], players)

            success, response, _ = bet_handler.place_bet(
                disc_id, guild_id, bet_amount, game_timestamp,
                bet_str, bet_target, target_name
            )

            if LOUD:
                print(response)

            active_bets = self.db_client.get_bets(game, True, disc_id)

            bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

            success, _ = bet_handler.resolve_bet(
                disc_id,
                bet_ids,
                amounts,
                bet_timestamp,
                event_ids,
                targets,
                game_data
            )

            self.assert_true(success, "Bet was won.")

            # Game win and doinks
            bet_amount = ["30", "20"]
            game_timestamp = None
            bet_str = ["game_win", "doinks"]
            bet_target = [None, None]
            target_name = [None, None]
            game_id = 1

            player_cls = LoLPlayerStats if game == "lol" else CS2PlayerStats
            players = [
                player_cls(game_id, disc_id, 20, -1, 0)
            ]
            game_data = cls(game, game_id, game_timestamp, 0, 1, guild_id, [], players)

            success, response, _ = bet_handler.place_bet(
                disc_id, guild_id, bet_amount, game_timestamp,
                bet_str, bet_target, target_name
            )

            if LOUD:
                print(response)

            active_bets = self.db_client.get_bets(game, True, disc_id)

            bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

            success, _ = bet_handler.resolve_bet(
                disc_id,
                bet_ids,
                amounts,
                bet_timestamp,
                event_ids,
                targets,
                game_data
            )

            self.assert_false(success, "Bet was lost.")

            success, response, _ = bet_handler.place_bet(
                disc_id, guild_id, bet_amount, game_timestamp,
                bet_str, bet_target, target_name
            )

            if LOUD:
                print(response)

            balance_before = self.db_client.get_token_balance(disc_id)

            success, response, _ = bet_handler.place_bet(
                disc_id, guild_id, bet_amount, game_timestamp,
                bet_str, bet_target, target_name
            )

            active_bets = self.db_client.get_bets(game, True, disc_id)

            bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, ticket, _ = active_bets[0]

            success, response = bet_handler.cancel_bet(
                disc_id, guild_id, ticket, game_timestamp, None, None
            )

            if LOUD:
                print(response)

            self.assert_true(success, "Bet was cancelled.")

            balance_after = self.db_client.get_token_balance(disc_id)

            self.assert_equals(balance_after, balance_before, "Tokens were refunded.")

    @test
    def test_many(self):
        disc_id = 267401734513491969
        guild_id = 619073595561213953

        all_bet_amounts = ["10", "20", "30", "15", "25", "7"]
        all_game_timestamp = [None, time()-30, time()-10000]
        all_bet_strs = list(betting.BETTING_IDS.keys()) + ["game_win", "game_loss", "no_intfar"]
        all_bet_targets = []
        all_target_names = []
        for event_id in betting.BETTING_IDS.values():
            if event_id < 3:
                all_bet_targets.append([None])
                all_target_names.append([None])
            elif event_id < 17:
                all_bet_targets.append([None, 115142485579137029])
                all_target_names.append([None, "Dave"])
            else:
                all_bet_targets.append([115142485579137029])
                all_target_names.append(["Dave"])

        all_bet_targets.extend([[None], [None], [None]])
        all_target_names.extend([[None], [None], [None]])

        with self.db_client:
            self.db_client.execute_query(
                "UPDATE betting_balance SET tokens=100000000 WHERE disc_id=?",
                disc_id,
            )

            count = 1
            for multi_count in range(1, 4):
                for amount_index in range(0, len(all_bet_amounts), multi_count):
                    bet_amounts = all_bet_amounts[amount_index:amount_index+multi_count]
                    bet_strs = all_bet_strs[amount_index:amount_index+multi_count]
                    for game_timestamp in all_game_timestamp:
                        for target_ids, target_names in zip(all_bet_targets, all_target_names):
                            success, _, _ = self.bet_handler.place_bet(
                                disc_id, guild_id, bet_amounts, game_timestamp,
                                bet_strs, target_ids, target_names
                            )

                            test_name = f"Many Bets #{count} - Bet Placed."
                            if game_timestamp is not None and time() - game_timestamp > 5 * 60:
                                self.assert_false(success, test_name)
                            else:
                                self.assert_true(success, test_name)
                            count += 1

    @test
    def test_multi_bet_fail(self):
        disc_id = 267401734513491969
        guild_id = 619073595561213953

        bet_amounts = ["30", "20"]
        game_timestamp = None
        bet_strs = ["no_intfar", "game_win"]
        bet_targets = [None, None]
        target_names = [None, None]

        success, response, _ = self.bet_handler.place_bet(
            disc_id, guild_id, bet_amounts, game_timestamp,
            ["no_intfar", "whew"], bet_targets, target_names)

        if LOUD:
            print(response)

        self.assert_false(success, "Bet not placed - Invalid event.")

        balance = self.db_client.get_token_balance(disc_id)

        self.assert_equals(balance, 100, "Token balance not affected.")

        success, response, _  = self.bet_handler.place_bet(
            disc_id, guild_id, ["20", "no"], game_timestamp,
            bet_strs, bet_targets, target_names
        )

        if LOUD:
            print(response)

        self.assert_false(success, "Bet not placed - Invalid amount str.")

        success, response, _  = self.bet_handler.place_bet(
            disc_id, guild_id, ["20", "90"], game_timestamp,
            bet_strs, bet_targets, target_names
        )

        if LOUD:
            print(response)

        self.assert_false(success, "Bet not placed - Not enough tokens 1.")

        success, response, _  = self.bet_handler.place_bet(
            disc_id, guild_id, ["all", "5"], game_timestamp,
            bet_strs, bet_targets, target_names
        )

        if LOUD:
            print(response)

        self.assert_false(success, "Bet not placed - Not enough tokens 2.")

    @test
    def test_bet_placed_fail(self):
        disc_id = 267401734513491969
        guild_id = 619073595561213953

        bet_amounts = ["10"]
        game_timestamp = None
        bet_strs = ["game_win"]
        bet_targets = [None]
        target_names = [None]

        success, response, _ = self.bet_handler.place_bet(
            disc_id, guild_id, bet_amounts, game_timestamp,
            bet_strs, bet_targets, target_names
        )

        self.assert_true(success, "Bet placed")

        success, response, _ = self.bet_handler.place_bet(
            disc_id, guild_id, bet_amounts, game_timestamp,
            bet_strs, bet_targets, target_names
        )

        self.assert_false(success, "Duplicate bet placed")

        bet_amounts = ["50", "20", "10"]
        bet_strs = ["game_win", "no_intfar", "no_intfar"]
        bet_targets = [None, None, None]
        target_names = [None, None, None]

        success, response, _ = self.bet_handler.place_bet(
            disc_id, guild_id, bet_amounts, game_timestamp,
            bet_strs, bet_targets, target_names
        )

        self.assert_false(success, "Duplicate multi-bet placed")

    @test
    def test_misc(self):
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
            formatted = self.bet_handler.parse_bet_amount(amount_str)

            self.assert_equals(
                formatted, expected_format, f"Betting amount success - {expected_format}."
            )
