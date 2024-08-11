import os
from time import time
from unittest import TestCase

from src.api.config import Config
from src.api.meta_database import MetaDatabase, DEFAULT_GAME
from src.api.game_database import GameDatabase
from src.api.game_databases import get_database_client
from src.api.util import MAIN_GUILD_ID, SUPPORTED_GAMES

MY_DISC_ID = 267401734513491969
GAME = "lol"

class TestWrapper(TestCase):
    def setUp(self):
        meta_database = MetaDatabase(self.config)
        game_databases = {game: get_database_client(game, self.config) for game in SUPPORTED_GAMES}

        self.meta_database = meta_database
        self.game_databases = game_databases

    def _assert_no_exception(self, func, message, *args, **kwargs):
        try:
            func(*args, **kwargs)
        except Exception as exc:
            self.fail(f"Failed: {message}, {type(exc)} was raised")

    def _add_user(self, game, disc_id, player_name, player_id):
        kwargs = {"player_name": player_name, "player_id": player_id}

        for param in self.game_databases[game].game_user_params:
            kwargs[param] = param

        status, msg = self.game_databases[game].add_user(disc_id, **kwargs)
        if status > 0:
            self.meta_database.add_user(disc_id)

        return status, msg

    def test_add_user(self):
        all_users_before = len(self.meta_database.all_users)

        for game in SUPPORTED_GAMES:
            game_database = self.game_databases[game]

            game_users_before = len(game_database.game_users)

            status, msg = self._add_user(game, 123, "name", "id")
            self.assertEqual(status, 1, msg)

            all_users_after = len(self.meta_database.all_users)
            self.assertEqual(all_users_after, all_users_before + 1, "User was added.")

            game_users_after = len(game_database.game_users)
            self.assertEqual(game_users_after, game_users_before + 1, "Game user was added.")

            disc_id = game_database.discord_id_from_ingame_info(player_name="name")
            self.assertEqual(disc_id, 123, "User from ingame info exact match correct")

            disc_id = game_database.discord_id_from_ingame_info(exact_match=False, player_name="name")
            self.assertEqual(disc_id, 123, "User from ingame info fuzzy match correct")

            game_users_before = len(game_database.game_users)
            self._add_user(game, 123, "name", "id2")
            game_users_after = len(game_database.game_users)

            self.assertEqual(game_users_after, game_users_before, "Smurf was added.")

            game_database.remove_user(123)
            game_users_after = len(game_database.game_users)

            self.assertEqual(game_users_after, game_users_before - 1, "User was removed.")

            game_users_before = len(game_database.game_users)
            self._add_user(game, 123, "name", "id")
            game_users_after = len(game_database.game_users)

            self.assertEqual(game_users_after, game_users_before + 1, "User was re-added.")

    def test_user_queries(self):
        self._add_user(DEFAULT_GAME, MY_DISC_ID, "my_id", "my_name")

        reports_before = self.meta_database.get_reports(MY_DISC_ID)[0][1]
        self.assertEqual(reports_before, 0, "Test reports before")

        self.meta_database.report_user(MY_DISC_ID)

        reports_after = self.meta_database.get_reports(MY_DISC_ID)[0][1]
        self.assertEqual(reports_after, 1, "Test reports after")

        # Add another user to test getting user with most reports
        self._add_user(DEFAULT_GAME, 123, "other_id", "other_name")

        self.meta_database.report_user(123)
        self.meta_database.report_user(123)

        max_reports, max_reports_user = self.meta_database.get_max_reports_details()

        self.assertEqual(max_reports, 2, "Test max reports")
        self.assertEqual(max_reports_user, 123, "Test max reports user")

        # Test client secret queries
        client_secret = self.meta_database.get_client_secret(MY_DISC_ID)
        self.assertEqual(len(client_secret), 64, "Test client secret length")

        user_from_secret = self.meta_database.get_user_from_secret(client_secret)
        self.assertEqual(user_from_secret, MY_DISC_ID, "Get client from secret.")

    def test_game_queries(self):
        test_game_ids = {
            "lol": 5163331322,
            "cs2": "CSGO-8VPTQ-vMjZq-K5ZAB-bVPPQ-PRqmJ"
        }

        for game in SUPPORTED_GAMES:
            database: GameDatabase = self.game_databases[game]
            test_game_id = test_game_ids[game]

            self.assertTrue(database.game_exists(test_game_id), "Game exists before delete.")

            database.delete_game("Delete game.", test_game_id)
            self.assertFalse(database.game_exists(test_game_id), "Game doesn't exist after delete.")

            self._assert_no_exception(database.get_latest_game, "Get latest game.")

            self._assert_no_exception(database.get_game_ids, "Get game ids.")

            self._assert_no_exception(database.get_games_count, "Get games counts.")
            self._assert_no_exception(database.get_longest_game, "Get longest game")

            self._assert_no_exception(database.get_games_results, "Get games results")

            self._assert_no_exception(database.get_missed_games, "Get missed games")

    def test_stat_queries(self):
        test_game_ids = {
            "lol": 5163331322,
            "cs2": "CSGO-8VPTQ-vMjZq-K5ZAB-bVPPQ-PRqmJ"
        }

        for game in SUPPORTED_GAMES:
            database: GameDatabase = self.game_databases[game]

            self._assert_no_exception(database.get_most_extreme_stat, "Get most extreme stat.", "kills", True)
            if game == "lol":
                self._assert_no_exception(database.get_most_extreme_stat, "Get most extreme stat.", "first_blood", True)

            def get_best_or_worst_stat(*args):
                return database.get_best_or_worst_stat(*args)()

            self._assert_no_exception(get_best_or_worst_stat, "Get stat.", "kills", MY_DISC_ID, True)
            if game == "lol":
                self._assert_no_exception(get_best_or_worst_stat, "Get stat.", "first_blood", MY_DISC_ID, True)

            self._assert_no_exception(database.get_total_winrate, "Get total winrate.", MY_DISC_ID)

            self._assert_no_exception(database.get_played_winrate, "Get played winrate.", MY_DISC_ID, 4)
            self._assert_no_exception(database.get_played_count_for_stat, "Get played count for stat", "kda", True, MY_DISC_ID)
            self._assert_no_exception(database.get_played_count_for_stat, "Get played count for stat", "kda", False, MY_DISC_ID)

            def get_average_stat(*args):
                return database.get_average_stat(*args)()

            self._assert_no_exception(get_average_stat, "Get average stat", "kills")
            self._assert_no_exception(get_average_stat, "Get average stat", "kills", MY_DISC_ID)
            self._assert_no_exception(get_average_stat, "Get average stat", "kills", 4)
            self._assert_no_exception(get_average_stat, "Get average stat", "kills", MY_DISC_ID, 4)

            self._assert_no_exception(database.get_min_or_max_winrate_played, "Get min or max winrate played best.", MY_DISC_ID, True)
            self._assert_no_exception(database.get_min_or_max_winrate_played, "Get min or max winrate played worst.", MY_DISC_ID, False)

            self._assert_no_exception(database.get_played_ids, "Get champs played")
            self._assert_no_exception(database.get_played_ids, "Get champs played", MY_DISC_ID)

            self._assert_no_exception(database.get_winrate_relation, "Get winrate relation", MY_DISC_ID, True)
            self._assert_no_exception(database.get_winrate_relation, "Get winrate relation", MY_DISC_ID, False)

            self._assert_no_exception(database.get_longest_win_or_loss_streak, "Get longest win or loss streak", MY_DISC_ID, 1)
            self._assert_no_exception(database.get_longest_win_or_loss_streak, "Get longest win or loss streak", MY_DISC_ID, 0)

            self._assert_no_exception(database.get_current_win_or_loss_streak, "Get current win or loss streak", MY_DISC_ID, 1)
            self._assert_no_exception(database.get_current_win_or_loss_streak, "Get current win or loss streak", MY_DISC_ID, 0)

            test_game_id = test_game_ids[game]
            game_stats_to_get = ["timestamp", "duration", "game_id"]
            self._assert_no_exception(database.get_game_stats, "Get game stats", game_stats_to_get)
            self._assert_no_exception(database.get_game_stats, "Get game stats", game_stats_to_get, test_game_id)

            player_stats_to_get = ["kills", "deaths", "game_id"]
            self._assert_no_exception(database.get_player_stats, "Get player stats", player_stats_to_get)
            self._assert_no_exception(database.get_player_stats, "Get player stats", player_stats_to_get, test_game_id)
            self._assert_no_exception(database.get_player_stats, "Get player stats", player_stats_to_get, None, MY_DISC_ID)
            self._assert_no_exception(database.get_player_stats, "Get player stats", player_stats_to_get, test_game_id, MY_DISC_ID)

    def test_doinks_queries(self):
        for game in SUPPORTED_GAMES:
            database: GameDatabase = self.game_databases[game]

            self._assert_no_exception(database.get_doinks_count, "Get doinks counts.")
            self._assert_no_exception(database.get_doinks_count, "Get doinks counts filtered.", MY_DISC_ID)

            self._assert_no_exception(database.get_max_doinks_details, "Get max doinks details.")

            self._assert_no_exception(database.get_doinks_reason_counts, "Get doinks reason counts.")

            self._assert_no_exception(database.get_recent_intfars_and_doinks, "Get recent intfars and doinks.")

            self._assert_no_exception(database.get_doinks_stats, "Get doinks stats.")
            self._assert_no_exception(database.get_doinks_stats, "Get doinks stats filtered.", MY_DISC_ID)

            self._assert_no_exception(database.get_doinks_relations, "Get doinks relations.", MY_DISC_ID)
    
            def get_played_doinks(*args):
                return database.get_played_doinks_count(*args)
            self._assert_no_exception(get_played_doinks, "Get played doinks", MY_DISC_ID)

            def get_played_with_most_doinks(*args):
                return database.get_played_with_most_doinks(*args)

            self._assert_no_exception(get_played_with_most_doinks, "Get played with most doinks", MY_DISC_ID)

    def test_intfar_queries(self):
        for game in SUPPORTED_GAMES:
            database: GameDatabase = self.game_databases[game]

            self._assert_no_exception(database.get_intfar_count, "Get intfar counts.")
            self._assert_no_exception(database.get_intfar_count, "Get intfar counts filtered.", MY_DISC_ID)

            self._assert_no_exception(database.get_intfar_reason_counts, "Get intfar reason counts.")
            self._assert_no_exception(database.get_intfars_of_the_month, "Get intfars of the month.")
            self._assert_no_exception(database.get_longest_intfar_streak, "Get longest intfar streak.", MY_DISC_ID)
            self._assert_no_exception(database.get_longest_no_intfar_streak, "Get longest no intfar streak.", MY_DISC_ID)

            self._assert_no_exception(database.get_current_intfar_streak, "Get current intfar streak.")

            self._assert_no_exception(database.get_max_intfar_details, "Get max intfar details.")

            self._assert_no_exception(database.get_intfar_stats, "Get intfar stats.", MY_DISC_ID)
            self._assert_no_exception(database.get_intfar_stats, "Get intfar stats.", 331082926475182081, monthly=True)

            self._assert_no_exception(database.get_intfar_relations, "Get intfar relations.", MY_DISC_ID)

            def get_played_intfars(*args):
                return database.get_played_intfar_count(*args)
            self._assert_no_exception(get_played_intfars, "Get played intfars", MY_DISC_ID)

            def get_played_with_most_intfars(*args):
                return database.get_played_with_most_intfars(*args)
            self._assert_no_exception(get_played_with_most_intfars, "Get played with most intfars", MY_DISC_ID)

    def test_betting_queries(self):
        meta_database: MetaDatabase = self.meta_database

        self._assert_no_exception(meta_database.get_token_balance, "Get token balance.")
        self._assert_no_exception(meta_database.get_token_balance, "Get token balance.", MY_DISC_ID)

        self._assert_no_exception(meta_database.get_max_tokens_details, "Get max token details.")

        self._assert_no_exception(meta_database.update_token_balance, "Update token balance.", MY_DISC_ID, 10, True)
        self._assert_no_exception(meta_database.update_token_balance, "Update token balance.", MY_DISC_ID, 10, False)

        self._assert_no_exception(meta_database.get_max_tokens_details, "Get max token balance ID.")

        for game in SUPPORTED_GAMES:
            database: GameDatabase = self.game_databases[game]

            self._assert_no_exception(database.generate_ticket_id, "Generate ticket.", MY_DISC_ID)

            self._assert_no_exception(database.get_bets, "Get bets.", True)
            self._assert_no_exception(database.get_bets, "Get bets.", False)
            self._assert_no_exception(database.get_bets, "Get bets.", True, MY_DISC_ID)
            self._assert_no_exception(database.get_bets, "Get bets.", False, MY_DISC_ID)
            self._assert_no_exception(database.get_bets, "Get bets.", True, guild_id=MAIN_GUILD_ID)
            self._assert_no_exception(database.get_bets, "Get bets.", False, guild_id=MAIN_GUILD_ID)
            self._assert_no_exception(database.get_bets, "Get bets.", True, MY_DISC_ID, guild_id=MAIN_GUILD_ID)
            self._assert_no_exception(database.get_bets, "Get bets.", False, MY_DISC_ID, guild_id=MAIN_GUILD_ID)

            self._assert_no_exception(database.get_bet_id, "Get bet ID.", MY_DISC_ID, MAIN_GUILD_ID, 0, MY_DISC_ID, 0)
            self._assert_no_exception(database.get_bet_id, "Get bet ID.", MY_DISC_ID, MAIN_GUILD_ID, 0, ticket=0)
            self._assert_no_exception(database.get_bet_id, "Get bet ID.", MY_DISC_ID, MAIN_GUILD_ID, 0, MY_DISC_ID)
            self._assert_no_exception(database.get_bet_id, "Get bet ID.", MY_DISC_ID, MAIN_GUILD_ID, 0)

            self._assert_no_exception(database.get_better_id, "Get better ID.", 30)

            with database:
                self._assert_no_exception(database.make_bet, "Make bet.", MY_DISC_ID, MAIN_GUILD_ID, "game_win", 10, 0, int(time()))
                self._assert_no_exception(database.make_bet, "Make bet.", MY_DISC_ID, MAIN_GUILD_ID, "intfar", 10, 0, int(time()), MY_DISC_ID)

    def test_shop_queries(self):
        database: MetaDatabase = self.meta_database

        def add_items_to_shop_func():
            items = [
                ("Item 1", 50),
                ("Item 2", 1337)
            ]
            database.add_items_to_shop(items)
        self._assert_no_exception(add_items_to_shop_func, "Add shop items.")

        def buy_items_func():
            items = database.get_items_matching_price("Item 1", 50, 1)
            database.buy_item(MY_DISC_ID, items, 50, "Item 1")
        self._assert_no_exception(buy_items_func, "Buy shop item.")

        def get_item_by_name_func():
            database.get_item_by_name("Item 2", "buy")
            database.get_item_by_name("Item 2", "cancel")
            database.get_item_by_name("Item 1", "sell")
        self._assert_no_exception(get_item_by_name_func, "Get shop item by name.")

        def get_items_for_user_func():
             database.get_items_for_user(MY_DISC_ID)
        self._assert_no_exception(get_items_for_user_func, "Get shop items for user.")

        self._assert_no_exception(database.get_items_in_shop, "Get shop items.")

        def sell_item_func():
            items = database.get_matching_items_for_user(MY_DISC_ID, "Item 1", 1)
            database.sell_item(MY_DISC_ID, items, "Item 1", 500)
        self._assert_no_exception(sell_item_func, "Sell shop items.")

        def get_items_matching_price_func():
            database.get_items_matching_price("Item 2", 1337, 1)
            database.get_items_matching_price("Item 1", 500, 1, MY_DISC_ID)
        self._assert_no_exception(get_items_matching_price_func, "Get shop items matching price.")

        def cancel_listings_func():
            items = database.get_items_matching_price("Item 1", 500, 1, MY_DISC_ID)
            database.cancel_listings([item[0] for item in items], "Item 1", MY_DISC_ID)
        self._assert_no_exception(cancel_listings_func, "Cancel shop listings.")

    def test_sound_queries(self):
        for game in SUPPORTED_GAMES:
            database: GameDatabase = self.game_databases[game]

            self._assert_no_exception(database.get_event_sound, "Get event sound.", MY_DISC_ID, "intfar")
            self._assert_no_exception(database.get_event_sound, "Get event sound.", MY_DISC_ID, "doinks")

            self._assert_no_exception(database.set_event_sound, "Set event sound.", MY_DISC_ID, "sound", "intfar")
            self._assert_no_exception(database.set_event_sound, "Set event sound.", MY_DISC_ID, "sound", "doinks")

            self._assert_no_exception(database.remove_event_sound, "Remove event sound.", MY_DISC_ID, "intfar")
            self._assert_no_exception(database.remove_event_sound, "Remove event sound.", MY_DISC_ID, "doinks")

    def test_list_queries(self):
        database: MetaDatabase = self.game_databases["lol"]

        def create_list_func():
            database.create_list(MY_DISC_ID, "test_list1")
            database.create_list(MY_DISC_ID, "test_list2")
        self._assert_no_exception(create_list_func, "Create list.")

        def get_lists_func():
            database.get_lists()
            database.get_lists(MY_DISC_ID)
        self._assert_no_exception(get_lists_func, "Get lists.")
        
        def get_list_by_name_func():
            database.get_list_by_name("test_list1")
        self._assert_no_exception(get_list_by_name_func, "Get list by name.")

        def rename_list_func():
            list_id = database.get_list_by_name("test_list1")[0]
            database.rename_list(list_id, "new_list_name")
        self._assert_no_exception(rename_list_func, "Rename list.")

        def get_list_data_func():
            list_id = database.get_list_by_name("new_list_name")[0]
            database.get_list_data(list_id)
        self._assert_no_exception(get_list_data_func, "Get list data.")
        
        def add_items_to_list_func():
            list_id = database.get_list_by_name("new_list_name")[0]
            database.add_item_to_list(42, list_id)
            items = [
                (420, list_id),
                (1337, list_id)
            ]
            database.add_items_to_list(items)
        self._assert_no_exception(add_items_to_list_func, "Add items to list.")

        def get_list_items_func():
            list_id = database.get_list_by_name("new_list_name")[0]
            database.get_list_items(list_id)
        self._assert_no_exception(get_list_items_func, "Get items from list.")
        
        def get_list_from_item_id_func():
            list_id = database.get_list_by_name("new_list_name")[0]
            item_ids = database.get_list_items(list_id)
            database.get_list_from_item_id(item_ids[0][0])
        self._assert_no_exception(get_list_from_item_id_func, "Get list from list item.")
        
        def delete_item_from_list_func():
            list_id = database.get_list_by_name("new_list_name")[0]
            item_ids = database.get_list_items(list_id)
            database.delete_item_from_list(item_ids[0][0])
            database.delete_items_from_list([(item[0],) for item in item_ids[1:]])
        self._assert_no_exception(delete_item_from_list_func, "Delete items from list.")

    def test_misc_queries(self):
        for game in SUPPORTED_GAMES:
            database: GameDatabase = self.game_databases[game]

            self._assert_no_exception(database.get_meta_stats, "Get meta stats.")

            def get_performance_score(*args):
                return database.get_performance_score(*args)()

            self._assert_no_exception(get_performance_score, "Get performance score")
            self._assert_no_exception(get_performance_score, "Get performance score", MY_DISC_ID)
