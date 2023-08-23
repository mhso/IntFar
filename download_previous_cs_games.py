from argparse import ArgumentParser
from datetime import datetime

from api.game_api.csgo import SteamAPIClient
from api.config import Config
from api.database import Database

def get_data_from_file(filename, steam_name):
    with open(filename, "r", encoding="utf-8") as fp:
        all_data = []
        done_with_map = False

        for line in fp:
            if line.startswith("Competitive"): # Map name line
                map_name = line.split(" ")[1].strip().lower()
                timestamp = None
                duration = None
                table_lines = -1
                score_team_1 = None
                score_team_2 = None
                name_found = False
                our_team_1 = True
                done_with_map = False
            elif done_with_map:
                continue
            elif map_name is not None and timestamp is None: # Line after map name
                timestamp = datetime.strptime(line.replace("GMT", "").strip(), "%Y-%m-%d %H:%M:%S").timestamp()
            elif line.startswith("Match Duration"):
                duration_str = line.split(": ")[1].strip()
                mins, secs = duration_str.split(":")
                duration = int(mins) * 60 + int(secs)
            elif line.startswith("Player Name"):
                table_lines = 0
            elif table_lines > -1:
                if table_lines == 10 and score_team_1 is None:
                    score_team_1, score_team_2 = tuple(map(int, line.split(" : ")))
                    continue

                if table_lines % 2 == 0:
                    name = line.strip()
                    if name == steam_name:
                        name_found = True
                        our_team_1 = table_lines < 10
                elif name_found:
                    stats = line.split(None)
                    if len(stats) == 6:
                        _, kills, assists, deaths, hsp, score = stats
                        mvps = "0"
                    else:
                        _, kills, assists, deaths, mvps, hsp, score = stats
                        mvps = mvps[1:]
                        if mvps == "":
                            mvps = "1"
                    hsp = hsp[:-1]

                    done_with_map = True

                    all_data.append({
                        "map": map_name,
                        "timestamp": timestamp,
                        "duration": duration,
                        "score_us": score_team_1 if our_team_1 else score_team_2,
                        "score_them": score_team_2 if our_team_1 else score_team_1,
                        "kills": int(kills),
                        "assists": int(assists),
                        "deaths": int(deaths),
                        "mvps": int(mvps),
                        "hsp": int(hsp),
                        "score": int(score)
                    })
                table_lines += 1

    return all_data

def run(database: Database, args):
    steam_name = args.steam_name
    disc_id = database.discord_id_from_ingame_info("csgo", ingame_name=steam_name)

    if disc_id is None:
        raise ValueError(f"Can't find user with steam name '{steam_name}'")

    data = get_data_from_file(args.filename, args.steam_name)


parser = ArgumentParser()

parser.add_argument("filename")
parser.add_argument("steam_name")

args = parser.parse_args()

config = Config()
database = Database(config)

run(database, steam_api, args)
