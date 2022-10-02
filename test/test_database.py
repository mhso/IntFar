from shutil import copy
from os import remove
from time import time
from test.runner import TestRunner, test
from api.config import Config
from api.database import Database
from api.util import MAIN_GUILD_ID

MY_DISC_ID = 267401734513491969

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
        def add_new_user_func():
            self.database.add_user("summ_name", "summ_id", 123)

        users_before = len(self.database.summoners)
        self.assert_no_exception(add_new_user_func, "Add New User.")
        users_after = len(self.database.summoners)

        self.assert_equals(users_after, users_before + 1, "User was added.")

        def add_smurf_func():
            self.database.add_user("summ_name2", "summ_id2", MY_DISC_ID)

        users_before = len(self.database.summoners)
        self.assert_no_exception(add_smurf_func, "Add Smurf.")
        users_after = len(self.database.summoners)

        self.assert_equals(users_after, users_before, "Smurf was added.")

        def remove_user_func():
            self.database.remove_user(MY_DISC_ID)

        users_before = len(self.database.summoners)
        self.assert_no_exception(remove_user_func, "Remove User.")
        users_after = len(self.database.summoners)

        self.assert_equals(users_after, users_before - 1, "User was removed.")

        def re_add_user_func():
            self.database.add_user("summ_name", "summ_id", MY_DISC_ID)

        users_before = len(self.database.summoners)
        self.assert_no_exception(re_add_user_func, "Re-add User.")
        users_after = len(self.database.summoners)

        self.assert_equals(users_after, users_before + 1, "User was re-added.")

        def get_reports_func():
            self.database.get_reports(MY_DISC_ID)

        self.assert_no_exception(get_reports_func, "Get reports.")
        
        self.assert_no_exception(self.database.get_max_reports_details, "Get max reports.")

        def report_user_func():
            self.database.report_user(MY_DISC_ID)
        self.assert_no_exception(report_user_func, "Report user.")

    @test
    def test_game_queries(self):
        test_game_id = 5163331322

        def get_game_func():
            self.database.game_exists(test_game_id)

        self.assert_no_exception(get_game_func, "Game exists.")

        def delete_game_func():
            self.database.delete_game(test_game_id)

        self.assert_no_exception(delete_game_func, "Delete game.")

        self.assert_false(self.database.game_exists(test_game_id), "Game exists after delete.")

        self.assert_no_exception(self.database.get_game_ids, "Get game ids.")

        self.assert_no_exception(self.database.get_games_count, "Get games counts.")

    @test
    def test_stat_queries(self):
        def most_extreme_stat_func():
            self.database.get_most_extreme_stat("kills", True)
            self.database.get_most_extreme_stat("first_blood", True)
        self.assert_no_exception(most_extreme_stat_func, "Get most extreme stat.")

        def get_stat_func():
            self.database.get_best_or_worst_stat("kills", MY_DISC_ID, True)
            self.database.get_best_or_worst_stat("first_blood", MY_DISC_ID, True)
        self.assert_no_exception(get_stat_func, "Get stat.")

        def get_total_winrate_func():
            self.database.get_total_winrate(MY_DISC_ID)
        self.assert_no_exception(get_total_winrate_func, "Get total winrate.")

        def get_champ_winrate_func():
            self.database.get_champ_winrate(MY_DISC_ID, 4)
        self.assert_no_exception(get_champ_winrate_func, "Get champ winrate.")

        def get_min_or_max_winrate_champ_func():
            self.database.get_min_or_max_winrate_champ(MY_DISC_ID, True)
            self.database.get_min_or_max_winrate_champ(MY_DISC_ID, False)
        self.assert_no_exception(get_min_or_max_winrate_champ_func, "Get min or max winrate champ.")


    @test
    def test_doinks_queries(self):
        self.assert_no_exception(self.database.get_doinks_count, "Get doinks counts.")

        self.assert_no_exception(self.database.get_max_doinks_details, "Get max doinks details.")

        self.assert_no_exception(self.database.get_doinks_reason_counts, "Get doinks reason counts.")

        self.assert_no_exception(self.database.get_recent_intfars_and_doinks, "Get recent intfars and doinks.")

        def get_doinks_stats_func():
            self.database.get_doinks_stats()
            self.database.get_doinks_stats(MY_DISC_ID)

        self.assert_no_exception(get_doinks_stats_func, "Get doinks stats.")

        def get_doinks_relations_func():
            self.database.get_doinks_relations(MY_DISC_ID)

        self.assert_no_exception(get_doinks_relations_func, "Get doinks relations.")

    @test
    def test_intfar_queries(self):
        def get_intfar_counts_func():
            self.database.get_intfar_count(MY_DISC_ID)
            self.database.get_intfar_count()

        self.assert_no_exception(get_intfar_counts_func, "Get intfar counts.")

        self.assert_no_exception(self.database.get_intfar_reason_counts, "Get intfar reason counts.")

        self.assert_no_exception(self.database.get_intfars_of_the_month, "Get intfars of the month.")

        def longest_intfar_streak_func():
            self.database.get_longest_intfar_streak(MY_DISC_ID)

        self.assert_no_exception(longest_intfar_streak_func, "Get longest intfar streak.")

        def longest_no_intfar_streak_func():
            self.database.get_longest_no_intfar_streak(MY_DISC_ID)

        self.assert_no_exception(longest_no_intfar_streak_func, "Get longest no intfar streak.")

        self.assert_no_exception(self.database.get_current_intfar_streak, "Get current intfar streak.")

        self.assert_no_exception(self.database.get_max_intfar_details, "Get max intfar details.")

        def get_intfar_stats_func():
            self.database.get_intfar_stats(MY_DISC_ID)
            self.database.get_intfar_stats(331082926475182081, monthly=True)
        self.assert_no_exception(get_intfar_stats_func, "Get intfar stats.")

        def get_intfar_relations_func():
            self.database.get_intfar_relations(MY_DISC_ID)
        self.assert_no_exception(get_intfar_relations_func, "Get intfar relations.")

    @test
    def test_betting_queries(self):
        def generate_ticket_func():
            self.database.generate_ticket_id(MY_DISC_ID)
        self.assert_no_exception(generate_ticket_func, "Generate ticket.")

        def get_bets_func():
            self.database.get_bets(True)
            self.database.get_bets(False)
            self.database.get_bets(True, MY_DISC_ID)
            self.database.get_bets(False, MY_DISC_ID)
            self.database.get_bets(True, guild_id=MAIN_GUILD_ID)
            self.database.get_bets(False, guild_id=MAIN_GUILD_ID)
            self.database.get_bets(True, MY_DISC_ID, guild_id=MAIN_GUILD_ID)
            self.database.get_bets(False, MY_DISC_ID, guild_id=MAIN_GUILD_ID)
        self.assert_no_exception(get_bets_func, "Get bets.")

        def get_token_balance_func():
            self.database.get_token_balance()
            self.database.get_token_balance(MY_DISC_ID)
        self.assert_no_exception(get_token_balance_func, "Get token balance.")

        self.assert_no_exception(self.database.get_max_tokens_details, "Get max token details.")

        def update_token_balance_func():
            self.database.update_token_balance(MY_DISC_ID, 10, True)
            self.database.update_token_balance(MY_DISC_ID, 10, False)
        self.assert_no_exception(update_token_balance_func, "Update token balance.")

        def get_bet_id_func():
            self.database.get_bet_id(MY_DISC_ID, MAIN_GUILD_ID, 0, MY_DISC_ID, 0)
            self.database.get_bet_id(MY_DISC_ID, MAIN_GUILD_ID, 0, ticket=0)
            self.database.get_bet_id(MY_DISC_ID, MAIN_GUILD_ID, 0, MY_DISC_ID)
            self.database.get_bet_id(MY_DISC_ID, MAIN_GUILD_ID, 0)
        self.assert_no_exception(get_bet_id_func, "Get bet ID.")

        def get_better_id_func():
            self.database.get_better_id(30)
        self.assert_no_exception(get_better_id_func, "Get better ID.")

        self.assert_no_exception(self.database.get_max_tokens_details, "Get max token balance ID.")

        def make_bet_func():
            self.database.make_bet(MY_DISC_ID, MAIN_GUILD_ID, 0, 10, 0, int(time()))
            self.database.make_bet(MY_DISC_ID, MAIN_GUILD_ID, 3, 10, 0, int(time()), MY_DISC_ID)

        with self.database:
            self.assert_no_exception(make_bet_func, "Make bet.")
        

    @test
    def test_shop_queries(self):
        def add_items_to_shop_func():
            items = [
                ("Item 1", 50),
                ("Item 2", 1337)
            ]
            self.database.add_items_to_shop(items)
        self.assert_no_exception(add_items_to_shop_func, "Add shop items.")

        def buy_items_func():
            items = self.database.get_items_matching_price("Item 1", 50, 1)
            self.database.buy_item(MY_DISC_ID, items, 50, "Item 1")
        self.assert_no_exception(buy_items_func, "Buy shop item.")

        def get_item_by_name_func():
            self.database.get_item_by_name("Item 2", "buy")
            self.database.get_item_by_name("Item 2", "cancel")
            self.database.get_item_by_name("Item 1", "sell")
        self.assert_no_exception(get_item_by_name_func, "Get shop item by name.")

        def get_items_for_user_func():
             self.database.get_items_for_user(MY_DISC_ID)
        self.assert_no_exception(get_items_for_user_func, "Get shop items for user.")

        self.assert_no_exception(self.database.get_items_in_shop, "Get shop items.")

        def sell_item_func():
            items = self.database.get_matching_items_for_user(MY_DISC_ID, "Item 1", 1)
            self.database.sell_item(MY_DISC_ID, items, "Item 1", 500)
        self.assert_no_exception(sell_item_func, "Sell shop items.")

        def get_items_matching_price_func():
            self.database.get_items_matching_price("Item 2", 1337, 1)
            self.database.get_items_matching_price("Item 1", 500, 1, MY_DISC_ID)
        self.assert_no_exception(get_items_matching_price_func, "Get shop items matching price.")

        def cancel_listings_func():
            items = self.database.get_items_matching_price("Item 1", 500, 1, MY_DISC_ID)
            self.database.cancel_listings([item[0] for item in items], "Item 1", MY_DISC_ID)
        self.assert_no_exception(cancel_listings_func, "Cancel shop listings.")

    @test
    def test_sound_queries(self):
        def get_event_sound_func():
            self.database.get_event_sound(MY_DISC_ID, "intfar")
            self.database.get_event_sound(MY_DISC_ID, "doinks")
        self.assert_no_exception(get_event_sound_func, "Get event sound.")

        def set_event_sound_func():
            self.database.set_event_sound(MY_DISC_ID, "sound", "intfar")
            self.database.set_event_sound(MY_DISC_ID, "sound", "doinks")
        self.assert_no_exception(set_event_sound_func, "Set event sound.")
        
        def remove_event_sound_func():
            self.database.remove_event_sound(MY_DISC_ID, "intfar")
            self.database.remove_event_sound(MY_DISC_ID, "doinks")
        self.assert_no_exception(remove_event_sound_func, "Remove event sound.")

    @test
    def test_list_queries(self):
        def create_list_func():
            self.database.create_list(MY_DISC_ID, "test_list1")
            self.database.create_list(MY_DISC_ID, "test_list2")
        self.assert_no_exception(create_list_func, "Create list.")

        def get_lists_func():
            self.database.get_lists()
            self.database.get_lists(MY_DISC_ID)
        self.assert_no_exception(get_lists_func, "Get lists.")
        
        def get_list_by_name_func():
            self.database.get_list_by_name("test_list1")
        self.assert_no_exception(get_list_by_name_func, "Get list by name.")

        def rename_list_func():
            list_id = self.database.get_list_by_name("test_list1")[0]
            self.database.rename_list(list_id, "new_list_name")
        self.assert_no_exception(rename_list_func, "Rename list.")

        def get_list_data_func():
            list_id = self.database.get_list_by_name("new_list_name")[0]
            self.database.get_list_data(list_id)
        self.assert_no_exception(get_list_data_func, "Get list data.")
        
        def add_items_to_list_func():
            list_id = self.database.get_list_by_name("new_list_name")[0]
            self.database.add_item_to_list(42, list_id)
            items = [
                (420, list_id),
                (1337, list_id)
            ]
            self.database.add_items_to_list(items)
        self.assert_no_exception(add_items_to_list_func, "Add items to list.")

        def get_list_items_func():
            list_id = self.database.get_list_by_name("new_list_name")[0]
            self.database.get_list_items(list_id)
        self.assert_no_exception(get_list_items_func, "Get items from list.")
        
        def get_list_from_item_id_func():
            list_id = self.database.get_list_by_name("new_list_name")[0]
            item_ids = self.database.get_list_items(list_id)
            self.database.get_list_from_item_id(item_ids[0][0])
        self.assert_no_exception(get_list_from_item_id_func, "Get list from list item.")
        
        def delete_item_from_list_func():
            list_id = self.database.get_list_by_name("new_list_name")[0]
            item_ids = self.database.get_list_items(list_id)
            self.database.delete_item_from_list(item_ids[0][0])
            self.database.delete_items_from_list([(item[0],) for item in item_ids[1:]])
        self.assert_no_exception(delete_item_from_list_func, "Delete items from list.")

    @test
    def test_misc_queries(self):
        self.assert_no_exception(self.database.get_meta_stats, "Get meta stats.")
