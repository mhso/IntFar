from datetime import datetime
from time import time
from api.util import format_duration, STAT_COMMANDS

def calc_kda(stats):
    if stats["deaths"] == 0:
        return stats["kills"] + stats["assists"]
    return (stats["kills"] + stats["assists"]) / stats["deaths"]

def calc_kill_participation(stats, total_kills):
    if total_kills == 0:
        return 100
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
    now = time()
    dt_1 = datetime.fromtimestamp(game_start)
    dt_2 = datetime.fromtimestamp(now)
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

def are_unfiltered_stats_well_formed(game_info):
    game_keys = [
        "gameId", "gameDuration", "gameCreation", "gameMode", "mapId", "queueId",
        "participantIdentities", "teams", "participants"
    ]
    participant_keys = [
        "championId", "stats"
    ]
    stat_keys = [
        "goldEarned", "neutralMinionsKilled", "totalMinionsKilled", "deaths",
        "pentaKills", "totalDamageDealtToChampions", "visionWardsBoughtInGame",
        "kills", "inhibitorKills", "turretKills", "participantId", "assists", "win",
        "visionScore", "firstBloodKill"
    ]
    timeline_keys = [
        "participantId", "role", "lane"
    ]
    team_stat_keys = [
        "riftHeraldKills", "firstBlood", "dragonKills", "baronKills", "teamId", "win"
    ]
    player_keys = ["summonerName", "summonerId"]

    all_keys = [
        ("Game key", game_keys, []), ("Participant key", participant_keys, ["participants", 0]),
        ("Stat key", stat_keys, ["participants", 0, "stats"]),
        ("Timeline key", timeline_keys, ["participants", 0, "timeline"]),
        ("Team Stat key", team_stat_keys, ["teams", 0]),
        ("Player key", player_keys, ["participantIdentities", 0, "player"])
    ]

    keys_not_present = []
    for key_type, keys, dict_keys in all_keys:
        container = game_info
        for dict_key in dict_keys:
            if container is None:
                break
            container = container[dict_key]

        for key in keys:
            if container is None or not key in container:
                keys_not_present.append((key_type, key))

    return keys_not_present

def are_filtered_stats_well_formed(filtered_info):
    stat_keys = [
        "championId", "timestamp", "mapId", "gameDuration", "totalCs", "csPerMin"
    ]
    # for disc_id, stats in game_info:
    #     pass

def get_filtered_stats(database, users_in_game, game_info):
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
                for disc_id, _, summ_ids in database.summoners:
                    if part_info["player"]["summonerId"] in summ_ids:
                        our_team = participant["teamId"]
                        combined_stats = participant["stats"]
                        combined_stats["championId"] = participant["championId"]
                        combined_stats["timestamp"] = game_info["gameCreation"]
                        combined_stats["mapId"] = game_info["mapId"]
                        combined_stats["gameDuration"] = int(game_info["gameDuration"])
                        combined_stats["totalCs"] = combined_stats["neutralMinionsKilled"] + combined_stats["totalMinionsKilled"]
                        combined_stats["csPerMin"] = (combined_stats["totalCs"] / game_info["gameDuration"]) * 60
                        combined_stats.update(participant["timeline"])
                        filtered_stats.append((disc_id, combined_stats))

                        if users_in_game is not None:
                            user_in_list = False
                            for user_disc_id, _, _ in users_in_game:
                                if user_disc_id == disc_id:
                                    user_in_list = True
                                    break
                            if not user_in_list:
                                summ_data = (disc_id, part_info["player"]["summonerName"],
                                             part_info["player"]["summonerId"])
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
