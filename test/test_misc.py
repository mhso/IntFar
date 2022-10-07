from glob import glob
import json
import os
import shutil

from api import game_stats, util
from test.runner import TestRunner, test
from api.config import Config
from api.database import Database
from discbot.discord_bot import DiscordClient
from api.database import Database
from api.riot_api import RiotAPIClient
from api.bets import BettingHandler

class TestWrapper(TestRunner):
    def __init__(self):
        super().__init__()
        conf = Config()
        database = Database(conf)
        self.before_all(config=conf, database=database)

    def before_test(self):
        auth = json.load(open("resources/auth.json"))
        self.config.riot_key = auth["riotDevKey"] if self.config.use_dev_token else auth["riotAPIKey"]

        shutil.copy("resources/database.db", "resources/database_test.db")
        self.config.database = "resources/database_test.db"

    def after_test(self):
        os.remove("resources/database_test.db")

    @test
    def test_stat_record(self):
        with open("misc/test_data.json", "r", encoding="utf-8") as fp:
            data = json.load(fp)

        users_in_game = [
            (172757468814770176, 'Stirred Martini', 'JaCbP2pIag8CVn3ERfvVP7QS6-OjNA-LInKW3gMkTytMO0Q'),
            (267401734513491969, 'Senile Felines', 'LRjsmujd76mwUe5ki-cOhcfrpAVsMpsLeA9BZqSl6bMiOI0'),
            (331082926475182081, 'Dumbledonger', 'z6svwF0nkD_TY5SLXAOEW3MaDLqJh1ziqOsE9lbqPQavp3o')
        ]

        relevant_stats, users_in_game = game_stats.get_relevant_stats(users_in_game, users_in_game, data)
        filtered_stats = game_stats.get_filtered_stats(relevant_stats)

        guild_id = util.MAIN_GUILD_ID
        game_id = 5452408885

        database = Database(self.config)
        database.delete_game(game_id)

        riot_api = RiotAPIClient(self.config)
        betting_handler = BettingHandler(self.config, database)

        client = DiscordClient(self.config, database, betting_handler, riot_api, None, None)
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

        intfar, intfar_reason, intfar_response = client.get_intfar_data(relevant_stats, filtered_stats, guild_id)
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
            response = records_response + "\n" + response
        
        print(intfar_response)
        print(response)

    @test
    def test_match_v5(self):
        with open("misc/game_5448295599_old.json") as fp:
            old_data = json.load(fp)

        with open("misc/game_5448295599_new.json") as fp:
            new_data = json.load(fp)["info"]

        users_in_game = [
            (267401734513491969, None, None, 202),
            (172757468814770176, None, None, 154),
            (115142485579137029, None, None, 412),
            (331082926475182081, None, None, 3)
        ]

        relevant_old = game_stats.get_relevant_stats_v4(self.database.summoners, users_in_game, old_data)[0]
        relevant_new = game_stats.get_relevant_stats(self.database.summoners, users_in_game, old_data)[0]

        filtered_old = game_stats.get_filtered_stats(relevant_old)
        filtered_new = game_stats.get_filtered_stats(relevant_new)

        mappings = {"magicalDamageTaken": "magicDamageTaken", "totalTimeCrowdControlDealt": "totalTimeCCDealt"}
        exceptions = [
            "neutralMinionsKilledTeamJungle", "neutralMinionsKilledEnemyJungle",
            "firstInhibitorKill", "firstInhibitorAssist", "combatPlayerScore", "objectivePlayerScore",
            "totalPlayerScore", "totalScoreRank", "playerScore0", "playerScore1",
            "playerScore2", "playerScore3", "playerScore4", "playerScore5",
            "playerScore6", "playerScore7", "playerScore8", "playerScore9"
        ]

        same_keys = True
        for disc_id, stats in filtered_old:
            for other_disc, other_stats in filtered_new:
                if disc_id == other_disc:
                    for key in stats:
                        mapped_key = mappings.get(key, key)
                        if "perk" not in mapped_key.lower() and mapped_key not in exceptions and mapped_key not in other_stats:
                            same_keys = False
                            print(key)
                            break

        self.assert_true(same_keys, "Same keys compared to match v4.")

    @test
    def test_role_info(self):
        all_none = True
        for game_file in glob("resources/data/game_*.json"):
            with open(game_file) as fp:
                data = json.load(fp)
                for participant_data in data["participants"]:
                    if participant_data["timeline"]["lane"] == "JUNGLE" and participant_data["timeline"]["role"] != "NONE":
                        all_none = False
                        print(game_file)
                        break

        self.assert_true(all_none, "All jungle lane roles are NONE.")

    @test
    def test_cool_stats(self):
        game_id = 5438872497
        with open(f"resources/data/game_{game_id}.json", "r", encoding="utf-8") as fp:
            data = json.load(fp)

        relevant_stats, users_in_game = game_stats.get_relevant_stats(self.database.summoners, [], data)
        filtered_stats = game_stats.get_filtered_stats(relevant_stats)

        guild_id = util.MAIN_GUILD_ID

        database = Database(self.config)
        database.delete_game(game_id)

        riot_api = RiotAPIClient(self.config)
        betting_handler = BettingHandler(self.config, database)

        client = DiscordClient(self.config, database, betting_handler, riot_api, None, None)
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

        intfar, intfar_reason, intfar_response = client.get_intfar_data(
            relevant_stats,
            filtered_stats,
            guild_id
        )
        doinks, doinks_response = client.get_doinks_data(filtered_stats, guild_id)

        if doinks_response is not None:
            intfar_response += "\n" + doinks_response

        response, _, _ = client.resolve_bets(
            filtered_stats, intfar, intfar_reason, doinks, guild_id
        )

        cool_stats_response = client.get_cool_stats_data(filtered_stats, guild_id)
        if cool_stats_response is not None:
            response = cool_stats_response + "\n" + response

        best_records, worst_records = client.save_stats(
            filtered_stats, intfar, intfar_reason, doinks, guild_id
        )

        if best_records != [] or worst_records != []:
            records_response = client.get_beaten_records_msg(
                best_records, worst_records, guild_id
            )
            response = records_response + "\n" + response

        print(intfar_response)
        print(response)

    @test
    def test_current_game_streak(self):
        disc_id = 267401734513491969

        def insert_game(database, game_id, win):
            query_games = f"""
                INSERT INTO games (game_id, win)
                VALUES (?, ?)
            """
            query_participants = f"""
                INSERT INTO participants (game_id, disc_id, champ_id)
                VALUES (?, ?, 202)
            """

            database.execute_query(query_games, game_id, win)
            database.execute_query(query_participants, game_id, disc_id)

        with Database(self.config) as database:
            database.clear_tables()

            streak = database.get_current_win_or_loss_streak(1, disc_id)
            self.assert_equals(streak, 1, "Win streak is 1 at start")
    
            query_summoners = f"""
                INSERT INTO registered_summoners (disc_id, summ_name, summ_id, secret)
                VALUES (?, 'Senile Felines', '1337', '42')
            """
            database.execute_query(query_summoners, disc_id)

            game_id = 0

            # Test a 3 game win streak
            for _ in range(2):
                insert_game(database, game_id, 1)
                game_id += 1

            streak = database.get_current_win_or_loss_streak(disc_id, True)
            self.assert_equals(streak, 3, "Win streak is 3")

            # Test 4 game win streak
            insert_game(database, game_id, 1)
            streak = database.get_current_win_or_loss_streak(disc_id, True)
            self.assert_equals(streak, 4, "Win streak is 4")

            game_id += 1

            # Insert loss, test 1 game win streak
            insert_game(database, game_id, 0)
            streak = database.get_current_win_or_loss_streak(disc_id, True)
            self.assert_equals(streak, 1, "Win streak is 1 after loss")

            streak = database.get_current_win_or_loss_streak(disc_id, False)
            self.assert_equals(streak, 2, "Loss streak is 2")

            game_id += 1

            for _ in range(3):
                insert_game(database, game_id, 0)
                game_id += 1

            streak = database.get_current_win_or_loss_streak(disc_id, False)
            self.assert_equals(streak, 5, "Loss streak is 5")
