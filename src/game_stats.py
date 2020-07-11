import json
from datetime import datetime

def calc_kda(stats):
    if stats["deaths"] == 0:
        return stats["kills"] + stats["assists"]
    return (stats["kills"] + stats["assists"]) / stats["deaths"]

def calc_kill_participation(stats, total_kills):
    return int((float(stats["kills"] + stats["assists"]) / float(total_kills)) * 100.0)

def get_outlier(data, key, asc=True, total_kills=0):
    if key == "kda":
        sorted_data = sorted(data, key=lambda x: calc_kda(x[1]), reverse=not asc)
        return sorted_data[0]
    elif key == "kp":
        sorted_data = sorted(data, key=lambda x: calc_kill_participation(x[1], total_kills), reverse=not asc)
        return sorted_data[0]

    sorted_data = sorted(data, key=lambda entry: entry[1][key], reverse=not asc)
    return sorted_data[0]

def get_outlier_stat(stat, data):
    most_id, stats = get_outlier(data, stat, asc=True)
    most = stats[stat]
    least_id, stats = get_outlier(data, stat, asc=False)
    least = stats[stat]
    return most_id, most, least_id, least

def get_game_summary(data, summ_id):
    stats = None
    champ_id = 0
    with open("champions.json", encoding="UTF-8") as fp:
        champion_data = json.load(fp)

        for part_info in data["participantIdentities"]:
            if part_info["player"]["summonerId"] == summ_id:
                for participant in data["participants"]:
                    if part_info["participantId"] == participant["participantId"]:
                        stats = participant["stats"]
                        champ_id = participant["championId"]
                        break
                break

        champ_played = None
        for champ_name in champion_data["data"]:
            if int(champion_data["data"][champ_name]["key"]) == champ_id:
                champ_played = champion_data["data"][champ_name]["name"]
                break
        date = datetime.fromtimestamp(data["gameCreation"] / 1000.0).strftime("%Y/%m/%d")

        return (f"{champ_played} with a score of {stats['kills']}/" +
                f"{stats['deaths']}/{stats['assists']} on {date}")
