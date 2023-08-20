from shutil import copy
from os import remove
from time import time
from test.runner import TestRunner, test
from api.config import Config
from api.database import Database
from api.util import MAIN_GUILD_ID

MY_DISC_ID = 267401734513491969
GAME = "lol"

class TestWrapper(TestRunner):
    def __init__(self):
        super().__init__()
        conf = Config()
        remove("resources/test.db")
        copy("resources/database.db", "resources/test.db")
        conf.database = "resources/test.db"
        database_client = Database(conf)
        self.before_all(database=database_client)

    @test
    def test_user_queries(self):
        database: Database = self.database

        users_before = len(database.users_by_game[GAME])
        self.assert_no_exception(database.add_user, "Add New User.", GAME, 123, ingame_name="name", ingame_id="id")
        users_after = len(database.users_by_game[GAME])

        self.assert_equals(users_after, users_before + 1, "User was added.")

        self.assert_no_exception(database.discord_id_from_ingame_name, "User from ingame name", GAME, "name")

        users_before = len(database.users_by_game[GAME])
        self.assert_no_exception(database.add_user, "Add Smurf.", GAME, 123, ingame_name="name", ingame_id="id2")
        users_after = len(database.users_by_game[GAME])

        self.assert_equals(users_after, users_before, "Smurf was added.")

        self.assert_no_exception(database.remove_user, "Remove User.", GAME, 123)
        users_after = len(database.users_by_game[GAME])

        self.assert_equals(users_after, users_before - 1, "User was removed.")

        users_before = len(database.users_by_game[GAME])
        self.assert_no_exception(database.add_user, "Re-add User.", GAME, 123, ingame_name="name", ingame_id="id")
        users_after = len(database.users_by_game[GAME])

        self.assert_equals(users_after, users_before + 1, "User was re-added.")

        self.assert_no_exception(database.get_reports, "Get reports.", MY_DISC_ID)
        self.assert_no_exception(database.get_max_reports_details, "Get max reports.")
        self.assert_no_exception(database.report_user, "Report user.", MY_DISC_ID)

        self.assert_no_exception(database.get_client_secret, "Get client secret.", MY_DISC_ID)

        def get_user_from_secret_func():
            secret = database.get_client_secret(MY_DISC_ID)
            database.get_user_from_secret(secret)

        self.assert_no_exception(get_user_from_secret_func, "Get client from secret.")

    @test
    def test_game_queries(self):
        database: Database = self.database
    
        test_game_id = 5163331322

        self.assert_no_exception(database.game_exists, "Game exists.", GAME, test_game_id)

        self.assert_no_exception(database.delete_game, "Delete game.", GAME, test_game_id)

        self.assert_false(database.game_exists(GAME, test_game_id), "Game doesn't exist after delete.")

        self.assert_no_exception(database.get_latest_game, "Get latest game.", GAME)

        self.assert_no_exception(database.get_game_ids, "Get game ids.", GAME)

        self.assert_no_exception(database.get_games_count, "Get games counts.", GAME)
        self.assert_no_exception(database.get_longest_game, "Get longest game", GAME)

        self.assert_no_exception(database.get_recent_game_results, "Get recent game results", GAME)
        self.assert_no_exception(database.get_games_results, "Get games results", GAME)

    @test
    def test_stat_queries(self):
        database: Database = self.database
    
        self.assert_no_exception(database.get_most_extreme_stat, "Get most extreme stat.", GAME, "kills", True)
        self.assert_no_exception(database.get_most_extreme_stat, "Get most extreme stat.", GAME, "first_blood", True)

        self.assert_no_exception(database.get_best_or_worst_stat, "Get stat.", GAME, "kills", MY_DISC_ID, True)
        self.assert_no_exception(database.get_best_or_worst_stat, "Get stat.", GAME, "first_blood", MY_DISC_ID, True)

        self.assert_no_exception(database.get_total_winrate, "Get total winrate.", GAME, MY_DISC_ID)

        self.assert_no_exception(database.get_league_champ_winrate, "Get champ winrate.", MY_DISC_ID, 4)
        self.assert_no_exception(database.get_league_champ_count_for_stat, "Get champ count for stat", "kda", True, MY_DISC_ID)
        self.assert_no_exception(database.get_league_champ_count_for_stat, "Get champ count for stat", "kda", False, MY_DISC_ID)

        self.assert_no_exception(database.get_average_stat_league, "Get average stat", "kills")
        self.assert_no_exception(database.get_average_stat_league, "Get average stat", "kills", MY_DISC_ID)
        self.assert_no_exception(database.get_average_stat_league, "Get average stat", "kills", 4)
        self.assert_no_exception(database.get_average_stat_league, "Get average stat", "kills", MY_DISC_ID, 4)

        self.assert_no_exception(database.get_min_or_max_league_winrate_champ, "Get min or max winrate champ best.", MY_DISC_ID, True)
        self.assert_no_exception(database.get_min_or_max_league_winrate_champ, "Get min or max winrate champ worst.", MY_DISC_ID, False)

        self.assert_no_exception(database.get_league_champs_played, "Get champs played")
        self.assert_no_exception(database.get_league_champs_played, "Get champs played", MY_DISC_ID)

        self.assert_no_exception(database.get_played_league_champs, "Get played league champs", MY_DISC_ID)

        self.assert_no_exception(database.get_winrate_relation, "Get winrate relation", GAME, MY_DISC_ID, True)
        self.assert_no_exception(database.get_winrate_relation, "Get winrate relation", GAME, MY_DISC_ID, False)

        self.assert_no_exception(database.get_longest_win_or_loss_streak, "Get longest win or loss streak", GAME, MY_DISC_ID, 1)
        self.assert_no_exception(database.get_longest_win_or_loss_streak, "Get longest win or loss streak", GAME, MY_DISC_ID, 0)

        self.assert_no_exception(database.get_current_win_or_loss_streak, "Get current win or loss streak", GAME, MY_DISC_ID, 1)
        self.assert_no_exception(database.get_current_win_or_loss_streak, "Get current win or loss streak", GAME, MY_DISC_ID, 0)

    @test
    def test_doinks_queries(self):
        database: Database = self.database

        self.assert_no_exception(database.get_doinks_count, "Get doinks counts.", GAME)
        self.assert_no_exception(database.get_doinks_count, "Get doinks counts filtered.", GAME, MY_DISC_ID)

        self.assert_no_exception(database.get_league_champ_with_most_doinks, "Get champ with most doinks", MY_DISC_ID)

        self.assert_no_exception(database.get_max_doinks_details, "Get max doinks details.", GAME)

        self.assert_no_exception(database.get_doinks_reason_counts, "Get doinks reason counts.", GAME)

        self.assert_no_exception(database.get_recent_intfars_and_doinks, "Get recent intfars and doinks.", GAME)

        self.assert_no_exception(database.get_doinks_stats, "Get doinks stats.", GAME)
        self.assert_no_exception(database.get_doinks_stats, "Get doinks stats filtered.", GAME, MY_DISC_ID)

        self.assert_no_exception(database.get_doinks_relations, "Get doinks relations.", GAME, MY_DISC_ID)

    @test
    def test_intfar_queries(self):
        database: Database = self.database

        self.assert_no_exception(database.get_intfar_count, "Get intfar counts.", GAME)
        self.assert_no_exception(database.get_intfar_count, "Get intfar counts filtered.", GAME, MY_DISC_ID)

        self.assert_no_exception(database.get_intfar_reason_counts, "Get intfar reason counts.", GAME)
        self.assert_no_exception(database.get_intfars_of_the_month, "Get intfars of the month.", GAME)
        self.assert_no_exception(database.get_longest_intfar_streak, "Get longest intfar streak.", GAME, MY_DISC_ID)
        self.assert_no_exception(database.get_longest_no_intfar_streak, "Get longest no intfar streak.", GAME, MY_DISC_ID)

        self.assert_no_exception(database.get_current_intfar_streak, "Get current intfar streak.", GAME)

        self.assert_no_exception(database.get_max_intfar_details, "Get max intfar details.", GAME)

        self.assert_no_exception(database.get_intfar_stats, "Get intfar stats.", GAME, MY_DISC_ID)
        self.assert_no_exception(database.get_intfar_stats, "Get intfar stats.", GAME, 331082926475182081, monthly=True)

        self.assert_no_exception(database.get_intfar_relations, "Get intfar relations.", GAME, MY_DISC_ID)

        self.assert_no_exception(database.get_champ_with_most_intfars, "Get champ with most intfars", MY_DISC_ID)

    @test
    def test_betting_queries(self):
        database: Database = self.database

        self.assert_no_exception(database.generate_ticket_id, "Generate ticket.", MY_DISC_ID)

        self.assert_no_exception(database.get_bets, "Get bets.", GAME, True)
        self.assert_no_exception(database.get_bets, "Get bets.", GAME, False)
        self.assert_no_exception(database.get_bets, "Get bets.", GAME, True, MY_DISC_ID)
        self.assert_no_exception(database.get_bets, "Get bets.", GAME, False, MY_DISC_ID)
        self.assert_no_exception(database.get_bets, "Get bets.", GAME, True, guild_id=MAIN_GUILD_ID)
        self.assert_no_exception(database.get_bets, "Get bets.", GAME, False, guild_id=MAIN_GUILD_ID)
        self.assert_no_exception(database.get_bets, "Get bets.", GAME, True, MY_DISC_ID, guild_id=MAIN_GUILD_ID)
        self.assert_no_exception(database.get_bets, "Get bets.", GAME, False, MY_DISC_ID, guild_id=MAIN_GUILD_ID)

        self.assert_no_exception(database.get_token_balance, "Get token balance.")
        self.assert_no_exception(database.get_token_balance, "Get token balance.", MY_DISC_ID)

        self.assert_no_exception(database.get_max_tokens_details, "Get max token details.")

        self.assert_no_exception(database.update_token_balance, "Update token balance.", MY_DISC_ID, 10, True)
        self.assert_no_exception(database.update_token_balance, "Update token balance.", MY_DISC_ID, 10, False)

        self.assert_no_exception(database.get_bet_id, "Get bet ID.", GAME, MY_DISC_ID, MAIN_GUILD_ID, 0, MY_DISC_ID, 0)
        self.assert_no_exception(database.get_bet_id, "Get bet ID.", GAME, MY_DISC_ID, MAIN_GUILD_ID, 0, ticket=0)
        self.assert_no_exception(database.get_bet_id, "Get bet ID.", GAME, MY_DISC_ID, MAIN_GUILD_ID, 0, MY_DISC_ID)
        self.assert_no_exception(database.get_bet_id, "Get bet ID.", GAME, MY_DISC_ID, MAIN_GUILD_ID, 0)

        self.assert_no_exception(database.get_better_id, "Get better ID.", 30)

        self.assert_no_exception(database.get_max_tokens_details, "Get max token balance ID.")

        with database:
            self.assert_no_exception(database.make_bet, "Make bet.", GAME, MY_DISC_ID, MAIN_GUILD_ID, "game_win", 10, 0, int(time()))
            self.assert_no_exception(database.make_bet, "Make bet.", GAME, MY_DISC_ID, MAIN_GUILD_ID, "intfar", 10, 0, int(time()), MY_DISC_ID)

    @test
    def test_shop_queries(self):
        database: Database = self.database

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
        database: Database = self.database

        self.assert_no_exception(database.get_event_sound, "Get event sound.", GAME, MY_DISC_ID, "intfar")
        self.assert_no_exception(database.get_event_sound, "Get event sound.", GAME, MY_DISC_ID, "doinks")

        self.assert_no_exception(database.set_event_sound, "Set event sound.", GAME, MY_DISC_ID, "sound", "intfar")
        self.assert_no_exception(database.set_event_sound, "Set event sound.", GAME, MY_DISC_ID, "sound", "doinks")

        self.assert_no_exception(database.remove_event_sound, "Remove event sound.", GAME, MY_DISC_ID, "intfar")
        self.assert_no_exception(database.remove_event_sound, "Remove event sound.", GAME, MY_DISC_ID, "doinks")

    @test
    def test_list_queries(self):
        database: Database = self.database

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
        database: Database = self.database
        self.assert_no_exception(database.get_meta_stats, "Get meta stats.", GAME)

        self.assert_no_exception(database.get_performance_score, "Get performance score", GAME)
        self.assert_no_exception(database.get_performance_score, "Get performance score", GAME, MY_DISC_ID)
