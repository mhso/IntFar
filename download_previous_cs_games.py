import traceback
from argparse import ArgumentParser
from datetime import datetime
from glob import glob
from uuid import uuid4
from time import sleep
import os
import json

from api.game_api.csgo import SteamAPIClient
from api.game_data.csgo import CSGOGameStats, CSGOPlayerStats, CSGOGameStatsParser
from api.config import Config
from api.database import Database, DBException

"""
Array.from(document.getElementsByClassName("csgo_scoreboard_btn_gotv")).forEach((x) => console.log(x.parentNode.href));
"""

_GUILD_ID = 619073595561213953

def group_data(data) -> list[CSGOGameStats]:
    # Group duplicate game data by timestamp
    grouped_by_date = {}
    for entry in data:
        grouped_by_date[entry.timestamp] = entry

    merged = [entry for entry in grouped_by_date.values()]
    merged.sort(key=lambda x: x.timestamp)

    return merged

def get_data_from_sharecode(database: Database, steam_api: SteamAPIClient) -> list[CSGOGameStats]:
    all_data = []
    for disc_id in database.users_by_game["csgo"]:
        steam_id = database.users_by_game["csgo"][disc_id].ingame_id[0]
        auth_code = database.users_by_game["csgo"][disc_id].match_auth_code[0]
        curr_sharecode = database.users_by_game["csgo"][disc_id].latest_match_token[0]
        print(f"Progress for {disc_id}:")
        while curr_sharecode is not None:
            print("Sharecode:", curr_sharecode)

            data = steam_api.get_game_details(curr_sharecode)

            with open(f"{curr_sharecode}.json", "w", encoding="utf-8") as fp:
                json.dump(data, fp)

            stats_parser = CSGOGameStatsParser("csgo", data, steam_api, database.users_by_game["csgo"], _GUILD_ID)
            parsed_data: CSGOGameStats = stats_parser.parse_data()
            max_rounds = max(parsed_data.rounds_us, parsed_data.rounds_them)
            cs2 = not data["demo_parsed"] and (max_rounds == 13 or parsed_data.map_id is None)
            if cs2:
                print(f"Game {curr_sharecode} seems to be a CS2 game...")
            if len(parsed_data.filtered_player_stats) > 1 and not cs2 and max_rounds > 9:
                all_data.append(parsed_data)
    
            curr_sharecode = steam_api.get_next_sharecode(steam_id, auth_code, curr_sharecode)

            sleep(1)

    return group_data(all_data)

def parse_demo(steam_api: SteamAPIClient, database: Database, demo_url):
    data = steam_api.parse_demo(demo_url)
    stats_parser = CSGOGameStatsParser("csgo", data, steam_api, database.users_by_game["csgo"], _GUILD_ID)

    return stats_parser.parse_data()

def get_data_from_file(database: Database, steam_api: SteamAPIClient) -> list[CSGOGameStats]:
    folder = "misc/old_csgo_games"
    all_match_files = glob(f"{folder}/csgo_matches*")
    all_demo_files = glob(f"{folder}/gotv_demos*")

    match_files_by_name = {
        os.path.basename(filename).split(".")[0].split("_")[-1]: filename
        for filename in all_match_files
    }
    demo_files_by_name = {
        os.path.basename(filename).split(".")[0].split("_")[-1]: filename
        for filename in all_demo_files
    }

    all_data = []
    for name in match_files_by_name:
        match_file = match_files_by_name[name]
        demo_file = demo_files_by_name[name]
        matches_for_name = 0
        url_demos = []#[line.strip() for line in open(demo_file, "r", encoding="utf-8")]

        with open(match_file, "r", encoding="utf-8") as fp:
            first_line = True

            print(f"Parsing {match_file}...")

            count_lines = 0
            for line in fp:
                count_lines += 1

                try:
                    if line.startswith("Competitive") or line == ">EOF<": # Map name line or end of file
                        if not first_line and len(players_in_game) > 1 and (score_team_1 > 9 or score_team_2 > 9):
                            # Only save data if more than 1 registered player was in the game
                            rounds_us = score_team_2 if our_team_t else score_team_1
                            rounds_them = score_team_1 if our_team_t else score_team_2
                            win_score = 1 if rounds_us > rounds_them else -1
                            if rounds_us == rounds_them:
                                win_score = 0

                            kills_by_our_team = sum(stats.kills for stats in player_stats)

                            # Parse the N most recent matches as demos
                            if matches_for_name < len(url_demos):
                                demo_url = url_demos[len(all_data)]
                                parsed_data = parse_demo(steam_api, database, demo_url)
                                sleep(2)
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
                                for stats in player_stats:
                                    stats.kp = (
                                        100 if kills_by_our_team == 0
                                        else int((float(stats.kills + stats.assists) / float(kills_by_our_team)) * 100.0)
                                    )

                                all_data.append(
                                    CSGOGameStats(
                                        "csgo",
                                        match_id,
                                        timestamp,
                                        duration,
                                        win_score,
                                        _GUILD_ID,
                                        players_in_game,
                                        player_stats,
                                        map_id=map_id,
                                        map_name=map_name,
                                        started_t=our_team_t,
                                        rounds_us=rounds_us,
                                        rounds_them=rounds_them,
                                    )
                                )

                            if len(players_in_game) < 2 and url_demos != []:
                                url_demos.pop(0)

                            matches_for_name += 1
    
                        if line != ">EOF<":
                            first_line = False
                            player_stats = []
                            players_in_game = []
                            map_raw_name = " ".join(line.split(" ")[1:])
                            if "_" in map_raw_name:
                                map_raw_name = map_raw_name.split("_")[1]
                            map_id = steam_api.try_find_played(map_raw_name)
                            map_name = line.strip()
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
                    elif map_id is not None and timestamp is None: # Line after map name
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

                            kills = int(kills)
                            deaths = int(deaths)
                            assists = int(assists)

                            hsp = hsp[:-1]
                            kda =  (
                                kills + assists
                                if deaths == 0
                                else (kills + assists) / deaths
                            )

                            player_stats.append(
                                CSGOPlayerStats(
                                    match_id,
                                    disc_id,
                                    kills,
                                    deaths,
                                    assists,
                                    kda=kda,
                                    mvps=int(mvps),
                                    score=int(score),
                                    headshot_pct=int(hsp),
                                )
                            )

                        table_lines += 1

                except Exception:
                    print(f"Exception on line {count_lines}:", flush=True)
                    traceback.print_exc()
                    exit(1)

    # Group duplicate game data by timestamp
    return group_data(all_data)

def run(source: str, database: Database, steam_api: SteamAPIClient):
    if source == "file":
        data = get_data_from_file(database, steam_api)
    elif source == "sharecode":
        data = get_data_from_sharecode(database, steam_api)

    print("Saving to database...")

    with database:
        for entry in data:
            try:
                database.record_stats(entry)
            except DBException:
                print(f"Could not save data for {entry.game_id}, probably a duplicate.")

    if source == "sharecode":
        # Update newest match token for players
        for disc_id in database.users_by_game["csgo"]:
            newest_code = None
            for entry in data:
                if entry.find_player_stats(disc_id, entry.filtered_player_stats) is not None:
                    newest_code = entry.game_id

            database.set_new_csgo_sharecode(disc_id, newest_code)

    print(f"DONE! Saved data for {len(data)} games")

if __name__ == "__main__":
    parser = ArgumentParser()

    parser.add_argument("source", choices=("file", "sharecode"))
    parser.add_argument("--steam_2fa_code", type=str)

    args = parser.parse_args()

    config = Config()
    config.steam_2fa_code = args.steam_2fa_code
    database = Database(config)
    steam_api = SteamAPIClient("csgo", config)

    run(args.source, database, steam_api)
