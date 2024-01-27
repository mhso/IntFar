from shutil import copy
from os import remove
from time import time
from test.runner import TestRunner, test
from api.config import Config
from api.meta_database import MetaDatabase
from api.game_database import GameDatabase
from api.game_databases import get_database_client
from api.util import MAIN_GUILD_ID, SUPPORTED_GAMES

MY_DISC_ID = 267401734513491969
GAME = "lol"

class TestWrapper(TestRunner):
    def __init__(self):
        super().__init__()
        conf = Config()
        remove(f"{conf.database_folder}/test/meta.db")
        copy(f"{conf.database_folder}/meta.db", f"{conf.database_folder}/test/meta.db")
        for game in SUPPORTED_GAMES:
            remove(f"{conf.database_folder}/test/{game}.db")
            copy(f"{conf.database_folder}/{game}.db", f"{conf.database_folder}/test/{game}.db")

        conf.database_folder = f"{conf.database_folder}/test"
        meta_database = MetaDatabase(conf)
        game_databases = {game: get_database_client(game, conf) for game in SUPPORTED_GAMES}

        self.before_all(meta_database=meta_database, game_databases=game_databases)

    @test
    def test_user_queries(self):
        meta_database: MetaDatabase = self.meta_database

        for game in SUPPORTED_GAMES:
            game_database: GameDatabase = self.game_databases[game]
            game_users_before = len(game_database.game_users)
            all_users_before = len(meta_database.all_users)
            def add_user():
                status, _ = game_database.add_user(123, ingame_name="name", ingame_id="id")
                if status == 1:
                    meta_database.add_user(123)
                    all_users_after = len(meta_database.all_users)
                    self.assert_equals(all_users_after, all_users_before + 1, "User was added.")

            self.assert_no_exception(add_user, f"Add user {game}")

            game_users_after = len(game_database.game_users)
            self.assert_equals(game_users_after, game_users_before + 1, "Game user was added.")

            self.assert_no_exception(game_database.discord_id_from_ingame_info, "User from ingame info", ingame_name="name")

            game_users_before = len(game_database.game_users)
            self.assert_no_exception(game_database.add_user, "Add Smurf.", 123, ingame_name="name", ingame_id="id2")
            game_users_after = len(game_database.game_users)

            self.assert_equals(game_users_after, game_users_before, "Smurf was added.")

            self.assert_no_exception(game_database.remove_user, "Remove User.", 123)
            game_users_after = len(game_database.game_users)

            self.assert_equals(game_users_after, game_users_before - 1, "User was removed.")

            game_users_before = len(game_database.game_users)
            self.assert_no_exception(game_database.add_user, "Re-add User.", 123, ingame_name="name", ingame_id="id")
            game_users_after = len(game_database.game_users)

            self.assert_equals(game_users_after, game_users_before + 1, "User was re-added.")

        self.assert_no_exception(meta_database.get_reports, "Get reports.", MY_DISC_ID)
        self.assert_no_exception(meta_database.get_max_reports_details, "Get max reports.")
        self.assert_no_exception(meta_database.report_user, "Report user.", MY_DISC_ID)
        self.assert_no_exception(meta_database.get_client_secret, "Get client secret.", MY_DISC_ID)

        def get_user_from_secret_func():
            secret = meta_database.get_client_secret(MY_DISC_ID)
            meta_database.get_user_from_secret(secret)

        self.assert_no_exception(get_user_from_secret_func, "Get client from secret.")

    @test
    def test_game_queries(self):
        test_game_ids = {
            "lol": 5163331322,
            "cs2": "CSGO-8VPTQ-vMjZq-K5ZAB-bVPPQ-PRqmJ"
        }

        for game in SUPPORTED_GAMES:
            database: GameDatabase = self.game_databases[game]
            test_game_id = test_game_ids[game]

            self.assert_no_exception(database.game_exists, "Game exists.", test_game_id)
            self.assert_true(database.game_exists(test_game_id), "Game exists before delete.")

            self.assert_no_exception(database.delete_game, "Delete game.", test_game_id)
            self.assert_false(database.game_exists(test_game_id), "Game doesn't exist after delete.")

            self.assert_no_exception(database.get_latest_game, "Get latest game.")

            self.assert_no_exception(database.get_game_ids, "Get game ids.")

            self.assert_no_exception(database.get_games_count, "Get games counts.")
            self.assert_no_exception(database.get_longest_game, "Get longest game")

            self.assert_no_exception(database.get_games_results, "Get games results")

            self.assert_no_exception(database.get_missed_games, "Get missed games")

    @test
    def test_stat_queries(self):
        test_game_ids = {
            "lol": 5163331322,
            "cs2": "CSGO-8VPTQ-vMjZq-K5ZAB-bVPPQ-PRqmJ"
        }

        for game in SUPPORTED_GAMES:
            database: GameDatabase = self.game_databases[game]

            self.assert_no_exception(database.get_most_extreme_stat, "Get most extreme stat.", "kills", True)
            if game == "lol":
                self.assert_no_exception(database.get_most_extreme_stat, "Get most extreme stat.", "first_blood", True)

            def get_best_or_worst_stat(*args):
                return database.get_best_or_worst_stat(*args)()

            self.assert_no_exception(get_best_or_worst_stat, "Get stat.", "kills", MY_DISC_ID, True)
            if game == "lol":
                self.assert_no_exception(get_best_or_worst_stat, "Get stat.", "first_blood", MY_DISC_ID, True)

            self.assert_no_exception(database.get_total_winrate, "Get total winrate.", MY_DISC_ID)

            self.assert_no_exception(database.get_played_winrate, "Get played winrate.", MY_DISC_ID, 4)
            self.assert_no_exception(database.get_played_count_for_stat, "Get played count for stat", "kda", True, MY_DISC_ID)
            self.assert_no_exception(database.get_played_count_for_stat, "Get played count for stat", "kda", False, MY_DISC_ID)

            def get_average_stat(*args):
                return database.get_average_stat(*args)()

            self.assert_no_exception(get_average_stat, "Get average stat", "kills")
            self.assert_no_exception(get_average_stat, "Get average stat", "kills", MY_DISC_ID)
            self.assert_no_exception(get_average_stat, "Get average stat", "kills", 4)
            self.assert_no_exception(get_average_stat, "Get average stat", "kills", MY_DISC_ID, 4)

            self.assert_no_exception(database.get_min_or_max_winrate_played, "Get min or max winrate played best.", MY_DISC_ID, True)
            self.assert_no_exception(database.get_min_or_max_winrate_played, "Get min or max winrate played worst.", MY_DISC_ID, False)

            self.assert_no_exception(database.get_played_ids, "Get champs played")
            self.assert_no_exception(database.get_played_ids, "Get champs played", MY_DISC_ID)

            self.assert_no_exception(database.get_winrate_relation, "Get winrate relation", MY_DISC_ID, True)
            self.assert_no_exception(database.get_winrate_relation, "Get winrate relation", MY_DISC_ID, False)

            self.assert_no_exception(database.get_longest_win_or_loss_streak, "Get longest win or loss streak", MY_DISC_ID, 1)
            self.assert_no_exception(database.get_longest_win_or_loss_streak, "Get longest win or loss streak", MY_DISC_ID, 0)

            self.assert_no_exception(database.get_current_win_or_loss_streak, "Get current win or loss streak", MY_DISC_ID, 1)
            self.assert_no_exception(database.get_current_win_or_loss_streak, "Get current win or loss streak", MY_DISC_ID, 0)

            test_game_id = test_game_ids[game]
            game_stats_to_get = ["timestamp", "duration", "game_id"]
            self.assert_no_exception(database.get_game_stats, "Get game stats", game_stats_to_get)
            self.assert_no_exception(database.get_game_stats, "Get game stats", game_stats_to_get, test_game_id)

            player_stats_to_get = ["kills", "deaths", "game_id"]
            self.assert_no_exception(database.get_player_stats, "Get player stats", player_stats_to_get)
            self.assert_no_exception(database.get_player_stats, "Get player stats", player_stats_to_get, test_game_id)
            self.assert_no_exception(database.get_player_stats, "Get player stats", player_stats_to_get, None, MY_DISC_ID)
            self.assert_no_exception(database.get_player_stats, "Get player stats", player_stats_to_get, test_game_id, MY_DISC_ID)

    @test
    def test_doinks_queries(self):
        for game in SUPPORTED_GAMES:
            database: GameDatabase = self.game_databases[game]

            self.assert_no_exception(database.get_doinks_count, "Get doinks counts.")
            self.assert_no_exception(database.get_doinks_count, "Get doinks counts filtered.", MY_DISC_ID)

            self.assert_no_exception(database.get_max_doinks_details, "Get max doinks details.")

            self.assert_no_exception(database.get_doinks_reason_counts, "Get doinks reason counts.")

            self.assert_no_exception(database.get_recent_intfars_and_doinks, "Get recent intfars and doinks.")

            self.assert_no_exception(database.get_doinks_stats, "Get doinks stats.")
            self.assert_no_exception(database.get_doinks_stats, "Get doinks stats filtered.", MY_DISC_ID)

            self.assert_no_exception(database.get_doinks_relations, "Get doinks relations.", MY_DISC_ID)
    
            self.assert_no_exception(database.get_played_with_most_doinks, "Get played with most doinks", MY_DISC_ID)

    @test
    def test_intfar_queries(self):
        for game in SUPPORTED_GAMES:
            database: GameDatabase = self.game_databases[game]

            self.assert_no_exception(database.get_intfar_count, "Get intfar counts.")
            self.assert_no_exception(database.get_intfar_count, "Get intfar counts filtered.", MY_DISC_ID)

            self.assert_no_exception(database.get_intfar_reason_counts, "Get intfar reason counts.")
            self.assert_no_exception(database.get_intfars_of_the_month, "Get intfars of the month.")
            self.assert_no_exception(database.get_longest_intfar_streak, "Get longest intfar streak.", MY_DISC_ID)
            self.assert_no_exception(database.get_longest_no_intfar_streak, "Get longest no intfar streak.", MY_DISC_ID)

            self.assert_no_exception(database.get_current_intfar_streak, "Get current intfar streak.")

            self.assert_no_exception(database.get_max_intfar_details, "Get max intfar details.")

            self.assert_no_exception(database.get_intfar_stats, "Get intfar stats.", MY_DISC_ID)
            self.assert_no_exception(database.get_intfar_stats, "Get intfar stats.", 331082926475182081, monthly=True)

            self.assert_no_exception(database.get_intfar_relations, "Get intfar relations.", MY_DISC_ID)

            self.assert_no_exception(database.get_played_with_most_intfars, "Get played with most intfars", MY_DISC_ID)

    @test
    def test_betting_queries(self):
        meta_database: MetaDatabase = self.meta_database

        self.assert_no_exception(meta_database.get_token_balance, "Get token balance.")
        self.assert_no_exception(meta_database.get_token_balance, "Get token balance.", MY_DISC_ID)

        self.assert_no_exception(meta_database.get_max_tokens_details, "Get max token details.")

        self.assert_no_exception(meta_database.update_token_balance, "Update token balance.", MY_DISC_ID, 10, True)
        self.assert_no_exception(meta_database.update_token_balance, "Update token balance.", MY_DISC_ID, 10, False)

        self.assert_no_exception(meta_database.get_max_tokens_details, "Get max token balance ID.")

        for game in SUPPORTED_GAMES:
            database: GameDatabase = self.game_databases[game]

            self.assert_no_exception(database.generate_ticket_id, "Generate ticket.", MY_DISC_ID)

            self.assert_no_exception(database.get_bets, "Get bets.", True)
            self.assert_no_exception(database.get_bets, "Get bets.", False)
            self.assert_no_exception(database.get_bets, "Get bets.", True, MY_DISC_ID)
            self.assert_no_exception(database.get_bets, "Get bets.", False, MY_DISC_ID)
            self.assert_no_exception(database.get_bets, "Get bets.", True, guild_id=MAIN_GUILD_ID)
            self.assert_no_exception(database.get_bets, "Get bets.", False, guild_id=MAIN_GUILD_ID)
            self.assert_no_exception(database.get_bets, "Get bets.", True, MY_DISC_ID, guild_id=MAIN_GUILD_ID)
            self.assert_no_exception(database.get_bets, "Get bets.", False, MY_DISC_ID, guild_id=MAIN_GUILD_ID)

            self.assert_no_exception(database.get_bet_id, "Get bet ID.", MY_DISC_ID, MAIN_GUILD_ID, 0, MY_DISC_ID, 0)
            self.assert_no_exception(database.get_bet_id, "Get bet ID.", MY_DISC_ID, MAIN_GUILD_ID, 0, ticket=0)
            self.assert_no_exception(database.get_bet_id, "Get bet ID.", MY_DISC_ID, MAIN_GUILD_ID, 0, MY_DISC_ID)
            self.assert_no_exception(database.get_bet_id, "Get bet ID.", MY_DISC_ID, MAIN_GUILD_ID, 0)

            self.assert_no_exception(database.get_better_id, "Get better ID.", 30)

            with database:
                self.assert_no_exception(database.make_bet, "Make bet.", MY_DISC_ID, MAIN_GUILD_ID, "game_win", 10, 0, int(time()))
                self.assert_no_exception(database.make_bet, "Make bet.", MY_DISC_ID, MAIN_GUILD_ID, "intfar", 10, 0, int(time()), MY_DISC_ID)

    @test
    def test_shop_queries(self):
        database: MetaDatabase = self.meta_database

        def add_items_to_shop_func():
            items = [
                ("Item 1", 50),
                ("Item 2", 1337)
            ]
            database.add_items_to_shop(items)
        self.assert_no_exception(add_items_to_shop_func, "Add shop items.")

        def buy_items_func():
            items = database.get_items_matching_price("Item 1", 50, 1)
            database.buy_item(MY_DISC_ID, items, 50, "Item 1")
        self.assert_no_exception(buy_items_func, "Buy shop item.")

        def get_item_by_name_func():
            database.get_item_by_name("Item 2", "buy")
            database.get_item_by_name("Item 2", "cancel")
            database.get_item_by_name("Item 1", "sell")
        self.assert_no_exception(get_item_by_name_func, "Get shop item by name.")

        def get_items_for_user_func():
             database.get_items_for_user(MY_DISC_ID)
        self.assert_no_exception(get_items_for_user_func, "Get shop items for user.")

        self.assert_no_exception(database.get_items_in_shop, "Get shop items.")

        def sell_item_func():
            items = database.get_matching_items_for_user(MY_DISC_ID, "Item 1", 1)
            database.sell_item(MY_DISC_ID, items, "Item 1", 500)
        self.assert_no_exception(sell_item_func, "Sell shop items.")

        def get_items_matching_price_func():
            database.get_items_matching_price("Item 2", 1337, 1)
            database.get_items_matching_price("Item 1", 500, 1, MY_DISC_ID)
        self.assert_no_exception(get_items_matching_price_func, "Get shop items matching price.")

        def cancel_listings_func():
            items = database.get_items_matching_price("Item 1", 500, 1, MY_DISC_ID)
            database.cancel_listings([item[0] for item in items], "Item 1", MY_DISC_ID)
        self.assert_no_exception(cancel_listings_func, "Cancel shop listings.")

    @test
    def test_sound_queries(self):
        for game in SUPPORTED_GAMES:
            database: GameDatabase = self.game_databases[game]

            self.assert_no_exception(database.get_event_sound, "Get event sound.", MY_DISC_ID, "intfar")
            self.assert_no_exception(database.get_event_sound, "Get event sound.", MY_DISC_ID, "doinks")

            self.assert_no_exception(database.set_event_sound, "Set event sound.", MY_DISC_ID, "sound", "intfar")
            self.assert_no_exception(database.set_event_sound, "Set event sound.", MY_DISC_ID, "sound", "doinks")

            self.assert_no_exception(database.remove_event_sound, "Remove event sound.", MY_DISC_ID, "intfar")
            self.assert_no_exception(database.remove_event_sound, "Remove event sound.", MY_DISC_ID, "doinks")

    @test
    def test_list_queries(self):
        database: MetaDatabase = self.game_databases["lol"]

        def create_list_func():
            database.create_list(MY_DISC_ID, "test_list1")
            database.create_list(MY_DISC_ID, "test_list2")
        self.assert_no_exception(create_list_func, "Create list.")

        def get_lists_func():
            database.get_lists()
            database.get_lists(MY_DISC_ID)
        self.assert_no_exception(get_lists_func, "Get lists.")
        
        def get_list_by_name_func():
            database.get_list_by_name("test_list1")
        self.assert_no_exception(get_list_by_name_func, "Get list by name.")

        def rename_list_func():
            list_id = database.get_list_by_name("test_list1")[0]
            database.rename_list(list_id, "new_list_name")
        self.assert_no_exception(rename_list_func, "Rename list.")

        def get_list_data_func():
            list_id = database.get_list_by_name("new_list_name")[0]
            database.get_list_data(list_id)
        self.assert_no_exception(get_list_data_func, "Get list data.")
        
        def add_items_to_list_func():
            list_id = database.get_list_by_name("new_list_name")[0]
            database.add_item_to_list(42, list_id)
            items = [
                (420, list_id),
                (1337, list_id)
            ]
            database.add_items_to_list(items)
        self.assert_no_exception(add_items_to_list_func, "Add items to list.")

        def get_list_items_func():
            list_id = database.get_list_by_name("new_list_name")[0]
            database.get_list_items(list_id)
        self.assert_no_exception(get_list_items_func, "Get items from list.")
        
        def get_list_from_item_id_func():
            list_id = database.get_list_by_name("new_list_name")[0]
            item_ids = database.get_list_items(list_id)
            database.get_list_from_item_id(item_ids[0][0])
        self.assert_no_exception(get_list_from_item_id_func, "Get list from list item.")
        
        def delete_item_from_list_func():
            list_id = database.get_list_by_name("new_list_name")[0]
            item_ids = database.get_list_items(list_id)
            database.delete_item_from_list(item_ids[0][0])
            database.delete_items_from_list([(item[0],) for item in item_ids[1:]])
        self.assert_no_exception(delete_item_from_list_func, "Delete items from list.")

    @test
    def test_misc_queries(self):
        for game in SUPPORTED_GAMES:
            database: GameDatabase = self.game_databases[game]

            self.assert_no_exception(database.get_meta_stats, "Get meta stats.")

            def get_performance_score(*args):
                return database.get_performance_score(*args)()

            self.assert_no_exception(get_performance_score, "Get performance score")
            self.assert_no_exception(get_performance_score, "Get performance score", MY_DISC_ID)
