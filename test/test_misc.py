import json
import os
import shutil

from api import game_stats, util
from test.runner import TestRunner, test
from api.config import Config
from discbot.discord_bot import DiscordClient
from api.database import Database
from api.riot_api import APIClient
from api.bets import BettingHandler

class TestWrapper(TestRunner):
    def __init__(self):
        super().__init__()
        conf = Config()
        self.before_all(conf)

    def after_test(self):
        os.remove("resources/database_test.db")

    @test
    def test_stat_record(self, config):
        with open("misc/test_data.json", "r", encoding="utf-8") as fp:
            data = json.load(fp)

        auth = json.load(open("discbot/auth.json"))
        config.riot_key = auth["riotDevKey"] if config.use_dev_token else auth["riotAPIKey"]

        shutil.copy("resources/database.db", "resources/database_test.db")
        config.database = "resources/database_test.db"

        users_in_game = [
            (115142485579137029, 'Prince Jarvan lV', 'a8acI9mAGm3mxTNPEqJPZmQ9LYkPnL5BNYG_tRWVMv_u-5E'),
            (235831136733888512, 'h4xz0rguy', 'BMnWFGQJLiPrCS_WeVj0ksaH_G2rXcqL6PwHEBHFOtI'),
            (219497453374668815, 'Zapiens', 'uXbAPtnVfu7PNiOc_U_Z9jU5S1DPGee9YpJKWRjFNalqfLs'),
            (267401734513491969, 'Senile Felines', 'LRjsmujd76mwUe5ki-cOhcfrpAVsMpsLeA9BZqSl6bMiOI0'),
            (176012701217062912, 'thewulff', 'fLe2bhX9JQtDVtCFtmwM9PtYc-dLFU11EC9pE6wb7eiAa4c')
        ]

        filtered_stats, users_in_game = game_stats.get_filtered_stats(users_in_game, users_in_game, data)

        guild_id = util.MAIN_GUILD_ID
        game_id = 5375289609

        database = Database(config)
        riot_api = APIClient(config)
        betting_handler = BettingHandler(config, database)

        client = DiscordClient(config, database, betting_handler, riot_api, None)
        client.active_game[guild_id] = {
            "id": data["gameId"],
            "start": 0,
            "map_id": data["mapId"],
            "map_name": riot_api.get_map_name(data["mapId"]),
            "game_mode": data["gameMode"],
            "game_guild_name": "guild_name",
            "queue_id": data["queueId"]
        }
        client.users_in_game[guild_id] = users_in_game

        intfar, intfar_reason, intfar_response = client.get_intfar_data(filtered_stats, guild_id)
        doinks, doinks_response = client.get_doinks_data(filtered_stats, guild_id)

        if doinks_response is not None:
            intfar_response += "\n" + doinks_response

        response, max_tokens_id, new_max_tokens_id = client.resolve_bets(
            filtered_stats, intfar, intfar_reason, doinks, guild_id
        )

        best_records, worst_records = database.record_stats(
            intfar, intfar_reason, doinks,
            game_id, filtered_stats,
            users_in_game, guild_id
        )

        print(best_records)
        print(worst_records)

        if best_records != [] or worst_records != []:
            records_response = client.get_beaten_records_msg(
                best_records, worst_records, guild_id
            )
            response = records_response + response
        
        print(intfar_response)
        print(response)
