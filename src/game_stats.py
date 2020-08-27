from datetime import datetime
from time import time
from util import format_duration

def calc_kda(stats):
    if stats["deaths"] == 0:
        return stats["kills"] + stats["assists"]
    return (stats["kills"] + stats["assists"]) / stats["deaths"]

def calc_kill_participation(stats, total_kills):
    return int((float(stats["kills"] + stats["assists"]) / float(total_kills)) * 100.0)

def get_outlier(data, key, asc=True, total_kills=0, include_ties=False):
    sorted_data = None
    if key == "kda":
        sorted_data = sorted(data, key=lambda x: calc_kda(x[1]), reverse=not asc)
        if include_ties:
            outlier = calc_kda(sorted_data[0][1])
            ties = []
            index = 0
            while index < len(sorted_data) and calc_kda(sorted_data[index][1]) == outlier:
                ties.append(sorted_data[index][0])
                index += 1
            return ties, sorted_data[0][1]
    elif key == "kp":
        sorted_data = sorted(data, key=lambda x: calc_kill_participation(x[1], total_kills),
                             reverse=not asc)
        if include_ties:
            outlier = calc_kill_participation(sorted_data[0][1], total_kills)
            ties = []
            index = 0
            while (index < len(sorted_data)
                   and calc_kill_participation(sorted_data[index][1], total_kills) == outlier):
                ties.append(sorted_data[index][0])
                index += 1
            return ties, sorted_data[0][1]
    else:
        sorted_data = sorted(data, key=lambda entry: entry[1][key], reverse=not asc)
        if include_ties:
            outlier = sorted_data[0][1][key]
            ties = []
            index = 0
            while index < len(sorted_data) and sorted_data[index][1][key] == outlier:
                ties.append(sorted_data[index][0])
                index += 1
            return ties, sorted_data[0][1]

    return sorted_data[0]

def get_outlier_stat(stat, data):
    most_id, stats = get_outlier(data, stat, asc=True)
    most = stats[stat]
    least_id, stats = get_outlier(data, stat, asc=False)
    least = stats[stat]
    return most_id, most, least_id, least

def get_finished_game_summary(data, summ_ids, riot_api):
    stats = None
    champ_id = 0
    for part_info in data["participantIdentities"]:
        if part_info["player"]["summonerId"] in summ_ids:
            for participant in data["participants"]:
                if part_info["participantId"] == participant["participantId"]:
                    stats = participant["stats"]
                    champ_id = participant["championId"]
                    break
            break

    champ_played = riot_api.get_champ_name(champ_id)
    if champ_played is None:
        champ_played = "Unknown Champ (Rito pls)"
    date = datetime.fromtimestamp(data["gameCreation"] / 1000.0).strftime("%Y/%m/%d")
    duration = data["gameDuration"]
    dt_1 = datetime.fromtimestamp(time())
    dt_2 = datetime.fromtimestamp(time() + duration)
    fmt_duration = format_duration(dt_1, dt_2)

    return (f"{champ_played} with a score of {stats['kills']}/" +
            f"{stats['deaths']}/{stats['assists']} on {date} in a {fmt_duration} long game")

def get_active_game_summary(data, summ_id, summoners, riot_api):
    champions = {}
    for participant in data["participants"]:
        for _, _, summoner_ids in summoners:
            if participant["summonerId"] in summoner_ids:
                champ_id = participant["championId"]
                champ_played = riot_api.get_champ_name(champ_id)
                if champ_played is None:
                    champ_played = "Unknown Champ (Rito pls)"
                champions[participant["summonerId"]] = (participant["summonerName"], champ_played)

    game_start = data["gameStartTime"] / 1000
    duration = data["gameLength"]
    dt_1 = datetime.fromtimestamp(game_start)
    dt_2 = datetime.fromtimestamp(game_start + duration)
    fmt_duration = format_duration(dt_1, dt_2)
    game_mode = data["gameMode"]

    response = f"{fmt_duration} in a {game_mode} game, playing {champions[summ_id][1]}.\n"
    if len(champions) > 1:
        response += "He is playing with:"
        for other_id in champions:
            if other_id != summ_id:
                name, champ = champions[other_id]
                response += f"\n - {name} ({champ})"

    return response
