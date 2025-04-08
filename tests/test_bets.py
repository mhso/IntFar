from time import time
from src.api.betting import BettingHandler, MAX_BETTING_THRESHOLD
from src.api.meta_database import MetaDatabase
from src.api.game_database import GameDatabase
from src.api.game_data.lol import LoLGameStats, LoLPlayerStats
from src.api.game_data.cs2 import CS2GameStats, CS2PlayerStats
from src.api.util import SUPPORTED_GAMES

def test_game_won_success(
    meta_database: MetaDatabase,
    game_databases: dict[str, GameDatabase],
    betting_handlers: dict[str, BettingHandler]
):
    config = meta_database.config
    disc_id = 267401734513491969
    guild_id = 619073595561213953
    bet_amount = ["20"]
    game_timestamp = None
    bet_str = ["game_win"]
    bet_targets = [None]
    target_names = [None]
    game_stats_cls = {
        "lol": LoLGameStats,
        "cs2": CS2GameStats
    }

    for index, game in enumerate(SUPPORTED_GAMES):
        game_data = game_stats_cls[game](game, 0, game_timestamp, 0, 1, guild_id, [], [])
        game_database = game_databases[game]
        bet_handler: BettingHandler = betting_handlers[game]
        amount = int(bet_amount[0])
        meta_database.update_token_balance(disc_id, amount * index, False)

        balance = meta_database.get_token_balance(disc_id)
        assert balance == config.starting_tokens, "Token balance before bet placed."

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp, bet_str, bet_targets, target_names
        )

        balance = meta_database.get_token_balance(disc_id)
        expected_balance = config.starting_tokens - amount
        expected_response = (
            f"Bet successfully placed: `winning the game` in a {SUPPORTED_GAMES[game]} game "
            f"for **{amount}** {config.betting_tokens}.\nThe return multiplier for that event is **2**.\n"
            "You placed your bet before the game started, you will get the full reward.\n"
            f"Potential winnings:\n{amount} x 2 = **{amount * 2}** {config.betting_tokens}\n"
            f"Your {config.betting_tokens} balance is now `{expected_balance}`."
        )

        assert success, "Bet placed."
        assert balance == expected_balance, "Token balance after bet placed."
        assert expected_response == response, "Correct response"

        active_bets = game_database.get_bets(True, disc_id)

        assert len(active_bets) == 1, "# Active bets after bet placed."

        bet_ids, g_id, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

        bet = bet_handler.get_bet(bet_str[0])

        assert guild_id == g_id, "Guild ID."
        assert amounts[0] == amount, "Bet amount."
        assert event_ids[0] == bet.event_id, "Bet event ID."
        assert bet_timestamp == 0, "Bet timestamp."
        assert targets[0] == None, "Bet target."

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

        assert bet_value == amount * bet.base_return, "Bet value."
        assert success, "Bet was won."

        new_balance = meta_database.get_token_balance(disc_id)

        assert new_balance == config.starting_tokens - amount + bet_value, "Token balance after win."

        active_bets = game_database.get_bets(True, disc_id)

        assert active_bets == None, "No active bets after bet resolved."

def test_game_won_fail(
    meta_database: MetaDatabase,
    game_databases: dict[str, GameDatabase],
    betting_handlers: dict[str, BettingHandler]
):
    config = meta_database.config
    disc_id = 267401734513491969
    guild_id = 619073595561213953
    bet_amounts = ["30"]
    game_timestamp = None
    bet_strs = ["game_win"]
    bet_targets = [None]
    target_names = [None]
    game_stats_cls = {
        "lol": LoLGameStats,
        "cs2": CS2GameStats
    }

    for game in SUPPORTED_GAMES:
        game_data = game_stats_cls[game](game, 0, game_timestamp, 0, -1, guild_id, [], [])
        game_database = game_databases[game]
        bet_handler: BettingHandler = betting_handlers[game]
        balance = meta_database.get_token_balance(disc_id)
        meta_database.update_token_balance(disc_id, config.starting_tokens - balance, True)

        success, response, _ = bet_handler.place_bet(
            disc_id,
            guild_id,
            bet_amounts,
            game_timestamp,
            ["whew"],
            bet_targets,
            target_names
        )

        assert not success, "Bet not placed - Invalid event."

        balance = meta_database.get_token_balance(disc_id)

        assert balance == config.starting_tokens, "Token balance not affected."

        success, response, _ = bet_handler.place_bet(
            disc_id,
            guild_id,
            ["huehuehue"],
            game_timestamp,
            bet_strs,
            bet_targets,
            target_names
        )

        assert not success, "Bet not placed - Invalid amount string."

        success, response, _ = bet_handler.place_bet(
            disc_id,
            guild_id,
            ["-100"],
            game_timestamp,
            bet_strs,
            bet_targets,
            target_names
        )

        assert not success, "Bet not placed - Amount too low."

        timestamp_late = 60 * MAX_BETTING_THRESHOLD
        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amounts, timestamp_late,
            bet_strs, bet_targets, target_names
        )

        assert not success, "Bet not placed - Timestamp too late."

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, ["300"], game_timestamp,
            bet_strs, bet_targets, target_names
        )

        assert not success, "Bet not placed - Too few tokens."

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amounts, game_timestamp,
            bet_strs, bet_targets, target_names
        )

        balance = meta_database.get_token_balance(disc_id)

        assert success, "Bet placed."
        assert balance == config.starting_tokens - int(bet_amounts[0]), "Token balance after bet placed."

        active_bets = game_database.get_bets(True, disc_id)

        assert len(active_bets) == 1, "# Active bets after bet placed."

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

        assert bet_value == 0, "Bet value."
        assert not success, "Bet was lost."

        new_balance = meta_database.get_token_balance(disc_id)

        assert new_balance == config.starting_tokens - int(bet_amounts[0]), "Token balance after loss."

        active_bets = game_database.get_bets(True, disc_id)

        assert active_bets == None, "No active bets after bet resolved."

def test_no_intfar(
    meta_database: MetaDatabase,
    game_databases: dict[str, GameDatabase],
    betting_handlers: dict[str, BettingHandler]
):
    config = meta_database.config
    disc_id = 267401734513491969
    guild_id = 619073595561213953
    bet_amount = ["30"]
    game_timestamp = None
    bet_str = ["no_intfar"]
    bet_targets = [None]
    target_names = [None]
    game_stats_cls = {
        "lol": LoLGameStats,
        "cs2": CS2GameStats
    }

    for game in SUPPORTED_GAMES:
        game_data = game_stats_cls[game](game, 0, game_timestamp, 0, 1, guild_id, [], [])
        bet_handler = betting_handlers[game]
        game_database = game_databases[game]
        balance = meta_database.get_token_balance(disc_id)
        meta_database.update_token_balance(disc_id, config.starting_tokens - balance, True)

        success = bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp,
            bet_str, bet_targets, target_names
        )[0]

        assert success, "Bet placed."

        active_bets = game_database.get_bets(True, disc_id)

        assert len(active_bets) == 1, "# Active bets after bet placed."

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

        assert success, "Bet was won."

        game_data = game_stats_cls[game](game, 0, game_timestamp, 0, 1, guild_id, [], [], intfar_id=disc_id)

        bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp,
            bet_str, bet_targets, target_names
        )

        active_bets = game_database.get_bets(True, disc_id)

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

        assert not success, "Bet was lost."

def test_award_tokens_for_game(
    meta_database: MetaDatabase,
    betting_handlers: dict[str, BettingHandler]
):
    config = meta_database.config
    disc_id = 267401734513491969

    for game in SUPPORTED_GAMES:
        balance = meta_database.get_token_balance(disc_id)
        meta_database.update_token_balance(disc_id, config.starting_tokens - balance, True)
        balance = meta_database.get_token_balance(disc_id)

        assert balance == config.starting_tokens, "Token balance before game won."
        bet_handler = betting_handlers[game]

        token_gain = bet_handler.betting_tokens_for_win
        bet_handler.award_tokens_for_playing(disc_id, token_gain)

        balance = meta_database.get_token_balance(disc_id)
        assert balance == config.starting_tokens + token_gain, "Token balance after game won."

        meta_database.update_token_balance(disc_id, token_gain, False)
        balance = meta_database.get_token_balance(disc_id)

        assert balance == config.starting_tokens, "Token balance before game lost."

        token_gain = bet_handler.betting_tokens_for_loss
        bet_handler.award_tokens_for_playing(disc_id, token_gain)

        balance = meta_database.get_token_balance(disc_id)
        assert balance == config.starting_tokens + token_gain, "Token balance after game lost."

def test_multi_bet_success(
    meta_database: MetaDatabase,
    game_databases: dict[str, GameDatabase],
    betting_handlers: dict[str, BettingHandler]
):
    config = meta_database.config
    disc_id = 267401734513491969
    guild_id = 619073595561213953
    game_stats_cls = {
        "lol": LoLGameStats,
        "cs2": CS2GameStats
    }
    player_stats_cls = {
        "lol": LoLPlayerStats,
        "cs2": CS2PlayerStats
    }

    for game in SUPPORTED_GAMES:
        game_database = game_databases[game]
        bet_handler = betting_handlers[game]

        bet_amount = ["30", "20"]
        game_timestamp = None
        bet_str = ["no_intfar", "game_win"]
        bet_target = [None, None]
        target_name = [None, None]
        
        game_data_cls = game_stats_cls[game]
        player_cls = player_stats_cls[game]
        game_data = game_data_cls(game, 0, game_timestamp, 0, 1, guild_id, [], [])

        balance = meta_database.get_token_balance(disc_id)
        meta_database.update_token_balance(disc_id, config.starting_tokens - balance, True)

        success, response, _ = bet_handler.place_bet(
            disc_id,
            guild_id,
            bet_amount,
            game_timestamp,
            bet_str,
            bet_target,
            target_name
        )

        assert success, "Bet placed."

        active_bets = game_database.get_bets(True, disc_id)

        assert len(active_bets) == 1, "# Active bets after bet placed."

        bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, _, _ = active_bets[0]

        success = bet_handler.resolve_bet(
            disc_id,
            bet_ids,
            amounts,
            bet_timestamp,
            event_ids,
            targets,
            game_data
        )[0]

        assert success, "Bet was won."

        game_data = game_data_cls(game, 0, game_timestamp, 0, 1, guild_id, [], [], intfar_id=disc_id)

        bet_handler.place_bet(
            disc_id,
            guild_id,
            bet_amount,
            game_timestamp,
            bet_str,
            bet_target,
            target_name
        )

        active_bets = game_database.get_bets(True, disc_id)

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

        assert not success, "Bet was lost (there was an Int-Far)."

        game_data = game_data_cls(game, 0, game_timestamp, 0, -1, guild_id, [], [])

        bet_handler.place_bet(
            disc_id,
            guild_id,
            bet_amount,
            game_timestamp,
            bet_str,
            bet_target,
            target_name
        )

        active_bets = game_database.get_bets(True, disc_id)

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

        assert not success, "Bet was lost (game lost)."

        # Intfar and most kills
        bet_amount = ["30", "20"]
        game_timestamp = None
        bet_str = ["intfar", "most_kills"]
        bet_target = [115142485579137029, 267401734513491969]
        target_name = ["Dave", "Gual"]
        disc_id_2 = 115142485579137029
        player_id_1 = "10"
        player_id_2 = "20"
        game_id = 1

        players = [
            player_cls(game_id, disc_id_2, player_id_1, 10, 1, 0),
            player_cls(game_id, disc_id, player_id_2, 20, 1, 0)
        ]
        game_data = game_data_cls(game, game_id, game_timestamp, 0, 1, guild_id, [], players, intfar_id=disc_id_2)

        success = bet_handler.place_bet(
            disc_id,
            guild_id,
            bet_amount,
            game_timestamp,
            bet_str,
            bet_target,
            target_name
        )[0]

        active_bets = game_database.get_bets(True, disc_id)

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

        assert success, "Bet was won."

        # Game win and doinks
        bet_amount = ["30", "20"]
        game_timestamp = None
        bet_str = ["game_win", "doinks"]
        bet_target = [None, None]
        target_name = [None, None]
        game_id = 1

        players = [
            player_cls(game_id, disc_id, player_id_1, 20, 1, 0, "11000000")
        ]
        game_data = game_data_cls(game, game_id, game_timestamp, 0, 1, guild_id, [], players)

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp,
            bet_str, bet_target, target_name
        )

        active_bets = game_database.get_bets(True, disc_id)

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

        assert success, "Bet was won."

        # Game win and doinks
        bet_amount = ["30", "20"]
        game_timestamp = None
        bet_str = ["game_win", "doinks"]
        bet_target = [None, None]
        target_name = [None, None]
        game_id = 1

        players = [
            player_cls(game_id, disc_id, player_id_1, 20, -1, 0)
        ]
        game_data = game_data_cls(game, game_id, game_timestamp, 0, 1, guild_id, [], players)

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amount, game_timestamp,
            bet_str, bet_target, target_name
        )

        active_bets = game_database.get_bets(True, disc_id)

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

        assert not success, "Bet was lost."

        balance_before = meta_database.get_token_balance(disc_id)

        success = bet_handler.place_bet(
            disc_id,
            guild_id,
            bet_amount,
            game_timestamp,
            bet_str,
            bet_target,
            target_name
        )[0]

        active_bets = game_database.get_bets(True, disc_id)

        bet_ids, _, _, amounts, event_ids, targets, bet_timestamp, ticket, _ = active_bets[0]

        success, response = bet_handler.cancel_bet(
            disc_id, guild_id, ticket, game_timestamp, None, None
        )

        assert success, "Bet was cancelled."

        balance_after = meta_database.get_token_balance(disc_id)

        assert balance_after == balance_before, "Tokens were refunded."

def test_many(
    meta_database: MetaDatabase,
    betting_handlers: dict[str, BettingHandler]
):
    game = "lol"
    disc_id = 267401734513491969
    guild_id = 619073595561213953
    bet_handler = betting_handlers[game]

    all_bet_amounts = ["10", "20", "30", "15", "25", "7"]
    all_game_timestamp = [None, time()-30, time()-10000]
    all_bet_strs = list(bet.event_id for bet in bet_handler.all_bets)
    all_bet_targets = [[None], [None], [None]]
    all_target_names = [[None], [None], [None]]
    for index in range(len(all_bet_strs)):
        if index < 3:
            all_bet_targets.append([None])
            all_target_names.append([None])
        elif index < 17:
            all_bet_targets.append([None, 115142485579137029])
            all_target_names.append([None, "Dave"])
        else:
            all_bet_targets.append([115142485579137029])
            all_target_names.append(["Dave"])

    with meta_database:
        meta_database.execute_query(
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
                        success = bet_handler.place_bet(
                            disc_id,
                            guild_id,
                            bet_amounts,
                            game_timestamp,
                            bet_strs,
                            target_ids,
                            target_names
                        )[0]

                        test_name = f"Many Bets #{count} - Bet Placed."
                        if game_timestamp is not None and time() - game_timestamp > MAX_BETTING_THRESHOLD * 60:
                            assert not success, test_name
                        else:
                            assert success, test_name
                        count += 1

def test_multi_bet_fail(
    meta_database: MetaDatabase,
    betting_handlers: dict[str, BettingHandler]
):
    game = "lol"
    disc_id = 267401734513491969
    guild_id = 619073595561213953
    bet_handler = betting_handlers[game]

    bet_amounts = ["30", "20"]
    game_timestamp = None
    bet_strs = ["no_intfar", "game_win"]
    bet_targets = [None, None]
    target_names = [None, None]

    success = bet_handler.place_bet(
        disc_id,
        guild_id,
        bet_amounts,
        game_timestamp,
        ["no_intfar", "whew"],
        bet_targets,
        target_names
    )[0]

    assert success == "Bet not placed - Invalid event."

    balance = meta_database.get_token_balance(disc_id)

    assert balance == meta_database.config.starting_tokens, "Token balance not affected."

    success = bet_handler.place_bet(
        disc_id,
        guild_id,
        ["20", "no"],
        game_timestamp,
        bet_strs,
        bet_targets,
        target_names
    )[0]

    assert success == "Bet not placed - Invalid amount str."

    success = bet_handler.place_bet(
        disc_id,
        guild_id,
        ["20", "90"],
        game_timestamp,
        bet_strs,
        bet_targets,
        target_names
    )[0]

    assert success == "Bet not placed - Not enough tokens 1."

    success  = bet_handler.place_bet(
        disc_id,
        guild_id,
        ["all", "5"],
        game_timestamp,
        bet_strs,
        bet_targets,
        target_names
    )[0]

    assert success == "Bet not placed - Not enough tokens 2."

def test_bet_placed_fail(
    betting_handlers: dict[str, BettingHandler]
):
    disc_id = 267401734513491969
    guild_id = 619073595561213953

    bet_amounts = ["10"]
    game_timestamp = None
    bet_strs = ["game_win"]
    bet_targets = [None]
    target_names = [None]

    for game in SUPPORTED_GAMES:
        bet_handler = betting_handlers[game]

        success = bet_handler.place_bet(
            disc_id, guild_id, bet_amounts, game_timestamp,
            bet_strs, bet_targets, target_names
        )[0]

        assert success, "Bet placed"

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amounts, game_timestamp,
            bet_strs, bet_targets, target_names
        )

        assert not success, "Duplicate bet placed"
        assert response == f"Bet was not placed: `winning the game` - Such a bet has already been made for {SUPPORTED_GAMES[game]}!"

        bet_amounts = ["50", "20", "10"]
        bet_strs = ["game_win", "no_intfar", "no_intfar"]
        bet_targets = [None, None, None]
        target_names = [None, None, None]

        success, response, _ = bet_handler.place_bet(
            disc_id, guild_id, bet_amounts, game_timestamp,
            bet_strs, bet_targets, target_names
        )

        assert not success, "Duplicate multi-bet placed"
        assert response == f"Bet was not placed: `winning the game` Such a bet has already been made for {SUPPORTED_GAMES[game]}!"

# @test
# def test_misc(self):
#     tokens = [
#         6, 100, 1000, 10000, 100000, 1000000000
#     ]
#     expected = [
#         "6", "100", "1.000", "10.000", "100.000", "1.000.000.000"
#     ]

#     for token_amount, expected_format in zip(tokens, expected):
#         formatted = format_tokens_amount(token_amount)

#         self.assert_equals(
#             formatted, expected_format, f"Formatted tokens, {expected_format}."
#         )

#     amount_strs = [
#         "10", "100", "100000", "1K", "1k", "3B", "3.5b",
#         "7.2M", "132.213M", "4T", "12.321312572T", "1.2345K"
#     ]
#     expected = [
#         10, 100, 100000, 1000, 1000, 3000000000, 3500000000,
#         7200000, 132213000, int(4e12), 12321312572000, 1234
#     ]

#     for amount_str, expected_format in zip(amount_strs, expected):
#         formatted = self.bet_handler.parse_bet_amount(amount_str)

#         self.assert_equals(
#             formatted, expected_format, f"Betting amount success - {expected_format}."
#         )
