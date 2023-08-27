from argparse import ArgumentParser
from datetime import datetime
from uuid import uuid4

from api.game_api.csgo import SteamAPIClient
from api.game_data.csgo import CSGOGameStats, CSGOPlayerStats, CSGOGameStatsParser
from api.config import Config
from api.database import Database

"""
Array.from(document.getElementsByClassName("csgo_scoreboard_btn_gotv")).forEach((x) => console.log(x.parentNode.href));
"""

_GUILD_ID = 619073595561213953

def parse_demo(steam_api: SteamAPIClient, database: Database, demo_url):
    data = steam_api.parse_demo(demo_url)
    stats_parser = CSGOGameStatsParser("csgo", data, steam_api, database.users_by_game["csgo"], _GUILD_ID)

    return stats_parser.parse_data()

def get_data_from_file(folder, database: Database, steam_api: SteamAPIClient):
    url_demos = [line.strip() for line in open(f"{folder}/gotv_demos.txt", "r", encoding="utf-8")]

    all_data = []
    with open(f"{folder}/csgo_matches.txt", "r", encoding="utf-8") as fp:
        first_line = True

        count_lines = 0
        for line in fp:
            count_lines += 1
            if line.startswith("Competitive"): # Map name line
                if not first_line:
                    rounds_us = score_team_2 if our_team_t else score_team_1
                    rounds_them = score_team_1 if our_team_t else score_team_2
                    win_score = 1 if rounds_us > rounds_them else -1
                    if rounds_us == rounds_them:
                        win_score = 0

                    kills_by_our_team = sum(stats.kills for stats in player_stats)

                    # Parse the N most recent matches as demos
                    if len(all_data) < len(url_demos):
                        demo_url = url_demos[len(all_data)]
                        parsed_data = parse_demo(steam_api, database, demo_url)
                        new_player_stats = []
                        for other_player_stats in player_stats:
                            in_filtered = False
                            for demo_player_stats in parsed_data.filtered_player_stats:
                                if other_player_stats.disc_id == demo_player_stats.disc_id:
                                    demo_player_stats.mvps = other_player_stats.mvps
                                    demo_player_stats.score = other_player_stats.score
                                    new_player_stats.append(demo_player_stats)
                                    in_filtered = True
                                    break

                            if not in_filtered:
                                new_player_stats.append(other_player_stats)

                        parsed_data.all_player_stats = new_player_stats
                        parsed_data.timestamp = timestamp
                        parsed_data.duration = duration
                        all_data.append(parsed_data)
                    else:
                        long_match = rounds_us + rounds_them > 16
                        all_data.append(
                            CSGOGameStats(
                                "csgo",
                                match_id,
                                timestamp,
                                duration,
                                win_score,
                                _GUILD_ID,
                                kills_by_our_team,
                                players_in_game,
                                player_stats,
                                map_name,
                                our_team_t,
                                rounds_us,
                                rounds_them,
                                long_match
                            )
                        )

                first_line = False
                player_stats = []
                players_in_game = []
                map_name = line.split(" ")[1].strip().lower()
                timestamp = None
                duration = None
                table_lines = -1
                score_team_1 = None
                score_team_2 = None
                our_team_t = True
                uuid = uuid4().hex
                match_id = "CSGO"
                for index in range(0, 25, 5):
                    match_id += "-" + uuid[index:index+5]
            elif map_name is not None and timestamp is None: # Line after map name
                timestamp = datetime.strptime(line.replace("GMT", "").strip(), "%Y-%m-%d %H:%M:%S").timestamp()
            elif line.startswith("Match Duration"):
                duration_str = line.split(": ")[1].strip()
                mins, secs = duration_str.split(":")
                duration = int(mins) * 60 + int(secs)
            elif line.startswith("Player Name"):
                table_lines = 0
            elif -1 < table_lines < 21:
                if table_lines == 10 and score_team_1 is None:
                    score_team_1, score_team_2 = tuple(map(int, line.split(" : ")))
                    continue

                if table_lines % 2 == 0:
                    name = line.strip()
                    disc_id = database.discord_id_from_ingame_info("csgo", ingame_name=name)
                    if disc_id is not None:
                        game_user_info = database.users_by_game["csgo"][disc_id]
                        our_team_t = table_lines > 9
                        player_info = {
                            "disc_id": disc_id,
                            "steam_name": name,
                            "steam_id": game_user_info.ingame_id[0],
                        }
                        players_in_game.append(player_info)
                else:
                    stats = line.split(None)
                    if len(stats) == 5:
                        _, kills, assists, deaths, score = stats
                        mvps = "0"
                        hsp = "0%"
                    elif len(stats) == 6:
                        _, kills, assists, deaths, hsp, score = stats
                        if "%" in line:
                            mvps = "0"
                        else:
                            hsp = "0%"
                    else:
                        _, kills, assists, deaths, mvps, hsp, score = stats
                        mvps = mvps[1:]
                        if mvps == "":
                            mvps = "1"

                    hsp = hsp[:-1]

                    player_stats.append(
                        CSGOPlayerStats(
                            match_id,
                            disc_id,
                            int(kills),
                            int(deaths),
                            int(assists),
                            int(mvps),
                            int(score),
                            int(hsp),
                        )
                    )

                table_lines += 1

    return all_data

def run(database: Database, steam_api: SteamAPIClient, args):
    data = get_data_from_file(args.folder, database, steam_api)
    
    with database:
        for entry in data:
            database.record_stats(entry)

parser = ArgumentParser()

parser.add_argument("folder")

args = parser.parse_args()

config = Config()
database = Database(config)
steam_api = SteamAPIClient("csgo", config)

run(database, steam_api, args)
