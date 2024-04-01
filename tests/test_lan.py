import json

from api import game_stats
from api.meta_database import Database
from api.config import Config
from api.lan import get_tilt_value
from test.runner import TestRunner, test

TEST_ID = 5452408885

class TestWrapper(TestRunner):
    def __init__(self):
        super().__init__()
        conf = Config()
        database = Database(conf)
        self.before_all(config=conf, database=database)

    def before_test(self):
        auth = json.load(open(f"{self.config.resources_folder}/auth.json"))
        self.config.riot_key = auth["riotDevKey"] if self.config.use_dev_token else auth["riotAPIKey"]

        # shutil.copy("resources/database.db", "resources/database_test.db")
        # self.config.database = "resources/database_test.db"
        # self.database = Database(self.config)
        # self.database.delete_game(TEST_ID)

    # def after_test(self):
    #     os.remove("resources/database_test.db")

    @test
    def test_stats(self):
        with open("misc/test_data.json", "r", encoding="utf-8") as fp:
            data = json.load(fp)

        data["gameDuration"] /= 1000

        filtered_stats, _ = game_stats.get_filtered_stats(self.database.summoners, [], data)

        #self.database.save_lan_stats(TEST_ID, filtered_stats)

        saved_stats_all = self.database.get_player_stats()

        self.assert_true(saved_stats_all is not None, "Saved LAN stats all not None.")

        saved_stats_single = self.database.get_player_stats(disc_id=267401734513491969)
        print(saved_stats_all)
        print(saved_stats_single)

        self.assert_true(saved_stats_single is not None, "Saved LAN stats single not None.")

    @test
    def test_roo(self):
        game_ids = [
            5458345617, 5458428373, 5458462421, 5458594158,
            5461270696, 5461365032, 5461371619, 5461416747, 5461511463
        ]

        for game_id in game_ids:
            filename = f"{self.config.resources_folder}/data/game_{game_id}.json"
            with open(filename, "r", encoding="utf-8") as fp:
                data = json.load(fp)
                data["gameDuration"] /= 1000
                relevant, users = game_stats.get_relevant_stats(self.database.summoners, [], data)
                filtered = game_stats.get_filtered_stats(relevant)

                self.database.save_lan_stats(game_id, filtered)

    @test
    def test_tilt_value(self):
        recent_games = [1, 1, 0, 1, 0, 1, 0, 1, 0]
        tilt_value = get_tilt_value(recent_games)[0]
        print(tilt_value)

