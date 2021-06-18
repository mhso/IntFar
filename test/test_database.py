from shutil import copy
from os import remove
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
        self.before_all(database_client)

    @test
    def test_user_queries(self, database):
        def add_new_user_func():
            database.add_user("summ_name", "summ_id", 123)

        users_before = len(database.summoners)
        self.assert_no_exception(add_new_user_func, "Add New User.")
        users_after = len(database.summoners)

        self.assert_equals(users_after, users_before + 1, "User was added.")

        def add_smurf_func():
            database.add_user("summ_name", "summ_id", MY_DISC_ID)

        users_before = len(database.summoners)
        self.assert_no_exception(add_smurf_func, "Add Smurf.")
        users_after = len(database.summoners)

        self.assert_equals(users_after, users_before, "Smurf was added.")

        def remove_user_func():
            database.remove_user(MY_DISC_ID)

        users_before = len(database.summoners)
        self.assert_no_exception(remove_user_func, "Remove User.")
        users_after = len(database.summoners)

        self.assert_equals(users_after, users_before - 1, "User was removed.")

        def re_add_user_func():
            database.add_user("summ_name", "summ_id", MY_DISC_ID)

        users_before = len(database.summoners)
        self.assert_no_exception(re_add_user_func, "Re-add User.")
        users_after = len(database.summoners)

        self.assert_equals(users_after, users_before + 1, "User was re-added.")

        def get_reports_func():
            database.get_reports(MY_DISC_ID)

        self.assert_no_exception(get_reports_func, "Get reports.")
        
        self.assert_no_exception(database.get_max_reports_details, "Get max reports.")

        def report_user_func():
            database.report_user(MY_DISC_ID)
        self.assert_no_exception(report_user_func, "Report user.")

    @test
    def test_game_queries(self, database):
        test_game_id = 5163331322

        def get_game_func():
            database.game_exists(test_game_id)

        self.assert_no_exception(get_game_func, "Game exists.")

        def delete_game_func():
            database.delete_game(test_game_id)

        self.assert_no_exception(delete_game_func, "Delete game.")

        self.assert_false(database.game_exists(test_game_id), "Game exists after delete.")

        self.assert_no_exception(database.get_game_ids, "Get game ids.")

        self.assert_no_exception(database.get_games_count, "Get games counts.")

    @test
    def test_stat_queries(self, database):
        def most_extreme_stat_func():
            database.get_most_extreme_stat("kills", True, True)
            database.get_most_extreme_stat("first_blood", True, True)

        self.assert_no_exception(most_extreme_stat_func, "Get most extreme stat.")

        def get_stat_func():
            database.get_stat("kills", True, MY_DISC_ID, True)
            database.get_stat("first_blood", True, MY_DISC_ID, True)

        self.assert_no_exception(get_stat_func, "Get stat.")

    @test
    def test_doinks_queries(self, database):
        self.assert_no_exception(database.get_doinks_count, "Get doinks counts.")

        self.assert_no_exception(database.get_max_doinks_details, "Get max doinks details.")

        self.assert_no_exception(database.get_doinks_reason_counts, "Get doinks reason counts.")

        self.assert_no_exception(database.get_recent_intfars_and_doinks, "Get recent intfars and doinks.")

        def get_doinks_stats_func():
            database.get_doinks_stats()
            database.get_doinks_stats(MY_DISC_ID)

        self.assert_no_exception(get_doinks_stats_func, "Get doinks stats.")

        def get_doinks_relations_func():
            database.get_doinks_relations(MY_DISC_ID)

        self.assert_no_exception(get_doinks_relations_func, "Get doinks relations.")

    @test
    def test_intfar_queries(self, database):
        self.assert_no_exception(database.get_intfar_count, "Get intfar counts.")

        self.assert_no_exception(database.get_intfar_reason_counts, "Get intfar reason counts.")

        self.assert_no_exception(database.get_intfars_of_the_month, "Get intfars of the month.")

        def longest_intfar_streak_func():
            database.get_longest_intfar_streak(MY_DISC_ID)

        self.assert_no_exception(longest_intfar_streak_func, "Get longest intfar streak.")

        def longest_no_intfar_streak_func():
            database.get_longest_no_intfar_streak(MY_DISC_ID)

        self.assert_no_exception(longest_no_intfar_streak_func, "Get longest no intfar streak.")

        self.assert_no_exception(database.get_current_intfar_streak, "Get current intfar streak.")

        self.assert_no_exception(database.get_max_intfar_details, "Get max intfar details.")

        def get_intfar_stats_func():
            database.get_intfar_stats(MY_DISC_ID)
            database.get_intfar_stats(331082926475182081, monthly=True)
        self.assert_no_exception(get_intfar_stats_func, "Get intfar stats.")

        def get_intfar_relations_func():
            database.get_intfar_relations(MY_DISC_ID)
        self.assert_no_exception(get_intfar_relations_func, "Get intfar relations.")

    @test
    def test_betting_queries(self, database):
        def generate_ticket_func():
            database.generate_ticket_id(MY_DISC_ID)
        self.assert_no_exception(generate_ticket_func, "Generate ticket.")

        def get_bets_func():
            database.get_bets(True)
            database.get_bets(False)
            database.get_bets(True, MY_DISC_ID)
            database.get_bets(False, MY_DISC_ID)
            database.get_bets(True, guild_id=MAIN_GUILD_ID)
            database.get_bets(False, guild_id=MAIN_GUILD_ID)
            database.get_bets(True, MY_DISC_ID, guild_id=MAIN_GUILD_ID)
            database.get_bets(False, MY_DISC_ID, guild_id=MAIN_GUILD_ID)
        self.assert_no_exception(get_bets_func, "Get bets.")

        def get_token_balance_func():
            database.get_token_balance()
            database.get_token_balance(MY_DISC_ID)
        self.assert_no_exception(get_token_balance_func, "Get token balance.")

        self.assert_no_exception(database.get_max_tokens_details, "Get max token details.")

        def update_token_balance_func():
            database.update_token_balance(MY_DISC_ID, 10, True)
            database.update_token_balance(MY_DISC_ID, 10, False)
        self.assert_no_exception(update_token_balance_func, "Update token balance.")

        def get_bet_id_func():
            database.get_bet_id(MY_DISC_ID, MAIN_GUILD_ID, 0, MY_DISC_ID, 0)
            database.get_bet_id(MY_DISC_ID, MAIN_GUILD_ID, 0, ticket=0)
            database.get_bet_id(MY_DISC_ID, MAIN_GUILD_ID, 0, MY_DISC_ID)
            database.get_bet_id(MY_DISC_ID, MAIN_GUILD_ID, 0)
        self.assert_no_exception(get_bet_id_func, "Get bet ID.")

        def get_better_id_func():
            database.get_better_id(30)
        self.assert_no_exception(get_better_id_func, "Get better ID.")

    @test
    def test_misc_queries(self, database):
        self.assert_no_exception(database.get_meta_stats, "Get meta stats.")
