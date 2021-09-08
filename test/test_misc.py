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
from api.riot_api import APIClient
from api.bets import BettingHandler

def get_filtered_stats_old(all_users, users_in_game, game_info):
    """
    Get relevant stats from the given game data and filter the data
    that is relevant for the Discord users that participated in the game.
    """
    kills_per_team = {100: 0, 200: 0}
    damage_per_team = {100: 0, 200: 0}
    our_team = 100
    filtered_stats = []
    active_users = users_in_game
    for part_info in game_info["participantIdentities"]:
        for participant in game_info["participants"]:
            if part_info["participantId"] == participant["participantId"]:
                kills_per_team[participant["teamId"]] += participant["stats"]["kills"]
                damage_per_team[participant["teamId"]] += participant["stats"]["totalDamageDealtToChampions"]

                for disc_id, _, summ_ids in all_users:
                    if part_info["player"]["summonerId"] in summ_ids:
                        our_team = participant["teamId"]
                        combined_stats = participant["stats"]
                        combined_stats["championId"] = participant["championId"]
                        combined_stats["timestamp"] = game_info["gameCreation"]
                        combined_stats["mapId"] = game_info["mapId"]
                        combined_stats["gameDuration"] = int(game_info["gameDuration"])
                        combined_stats["totalCs"] = combined_stats["neutralMinionsKilled"] + combined_stats["totalMinionsKilled"]
                        combined_stats["csPerMin"] = (combined_stats["totalCs"] / game_info["gameDuration"]) * 60
                        filtered_stats.append((disc_id, combined_stats))

                        if users_in_game is not None:
                            user_in_list = False
                            for user_data in users_in_game:
                                if user_data[0] == disc_id:
                                    user_in_list = True
                                    break
                            if not user_in_list:
                                summ_data = (
                                    disc_id, part_info["player"]["summonerName"],
                                    part_info["player"]["summonerId"], participant["championId"]
                                )
                                active_users.append(summ_data)

    for _, stats in filtered_stats:
        stats["kills_by_team"] = kills_per_team[our_team]
        stats["damage_by_team"] = damage_per_team[our_team]
        for team in game_info["teams"]:
            if team["teamId"] == our_team:
                stats["baronKills"] = team["baronKills"]
                stats["dragonKills"] = team["dragonKills"]
                stats["heraldKills"] = team["riftHeraldKills"]
                stats["gameWon"] = team["win"] == "Win"
            else:
                stats["enemyBaronKills"] = team["baronKills"]
                stats["enemyDragonKills"] = team["dragonKills"]
                stats["enemyHeraldKills"] = team["riftHeraldKills"]

    return filtered_stats, active_users

class TestWrapper(TestRunner):
    def __init__(self):
        super().__init__()
        conf = Config()
        database = Database(conf)
        self.before_all(conf, database)

    def before_test(self):
        auth = json.load(open("discbot/auth.json"))
        config = self.test_args[0]
        config.riot_key = auth["riotDevKey"] if config.use_dev_token else auth["riotAPIKey"]

        shutil.copy("resources/database.db", "resources/database_test.db")
        config.database = "resources/database_test.db"

    def after_test(self):
        os.remove("resources/database_test.db")

    @test
    def test_stat_record(self, config, database):
        with open("misc/test_data.json", "r", encoding="utf-8") as fp:
            data = json.load(fp)

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

    @test
    def test_match_v5(self, config, database):
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

        filtered_old = get_filtered_stats_old(database.summoners, users_in_game, old_data)[0]
        filtered_new = game_stats.get_filtered_stats(database.summoners, users_in_game, new_data)[0]

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
    def test_role_info(self, config, database):
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
