from datetime import datetime
from time import time
from api.util import format_duration

def calc_kda(stats):
    if stats["deaths"] == 0:
        return stats["kills"] + stats["assists"]
    return (stats["kills"] + stats["assists"]) / stats["deaths"]

def calc_kill_participation(stats, total_kills):
    if total_kills == 0:
        return 100
    return int((float(stats["kills"] + stats["assists"]) / float(total_kills)) * 100.0)

def outlier_func(x, key, total_kills):
    if key == "kda":
        return calc_kda(x)
    if key == "kp":
        return calc_kill_participation(x, total_kills)
    return x[key]

def get_outlier(data, key, asc=True, total_kills=0, include_ties=False):
    def outlier_func_short(x):
        return outlier_func(x[1], key, total_kills)

    sorted_data = sorted(data, key=outlier_func_short, reverse=not asc)

    if include_ties:
        outlier = outlier_func_short(sorted_data[0])
        ties_ids = []
        ties_data = []
        index = 0
        while index < len(sorted_data) and outlier_func_short(sorted_data[index]) == outlier:
            ties_ids.append(sorted_data[index][0])
            ties_data.append(sorted_data[index][1])
            index += 1
        return ties_ids, ties_data

    return sorted_data[0]

def get_outlier_stat(stat, data, reverse_order=False, total_kills=0):
    most_id, stats = get_outlier(data, stat, asc=not reverse_order, total_kills=total_kills)
    most = outlier_func(stats, stat, total_kills)
    least_id, stats = get_outlier(data, stat, asc=reverse_order, total_kills=total_kills)
    least = outlier_func(stats, stat, total_kills)
    return most_id, most, least_id, least

def get_player_stats(data, summ_ids):
    # We have to do this to handle /match/v4 stuff...
    if "participantIdentities" in data:
        for part_info in data["participantIdentities"]:
            if part_info["player"]["summonerId"] in summ_ids:
                for participant in data["participants"]:
                    if part_info["participantId"] == participant["participantId"]:
                        stats = participant["stats"]
                        stats["championId"] = participant["championId"]
                        return stats
    else:
        for participant_data in data["participants"]:
            if participant_data["summonerId"] in summ_ids:
                return participant_data
    return None

def get_finished_game_summary(data, summ_ids, riot_api):
    stats = get_player_stats(data, summ_ids)

    champ_played = riot_api.get_champ_name(stats["championId"])
    if champ_played is None:
        champ_played = "Unknown Champ (Rito pls)"
    date = datetime.fromtimestamp(data["gameCreation"] / 1000.0).strftime("%Y/%m/%d")
    duration = data["gameDuration"]
    if "participantIdentities" not in data:
        duration = duration / 1000
    dt_1 = datetime.fromtimestamp(time())
    dt_2 = datetime.fromtimestamp(time() + duration)
    fmt_duration = format_duration(dt_1, dt_2)

    return (
        f"{champ_played} with a score of {stats['kills']}/" +
        f"{stats['deaths']}/{stats['assists']} on {date} in a {fmt_duration} long game"
    )

def get_active_game_summary(data, summ_id, summoners, riot_api):
    champions = {}
    users_in_game = []
    for participant in data["participants"]:
        for disc_id, _, summoner_ids in summoners:
            if participant["summonerId"] in summoner_ids:
                champ_id = participant["championId"]
                champ_played = riot_api.get_champ_name(champ_id)
                if champ_played is None:
                    champ_played = "Unknown Champ (Rito pls)"
                champions[participant["summonerId"]] = (participant["summonerName"], champ_played)
                users_in_game.append((disc_id, champ_id))

    game_start = data["gameStartTime"] / 1000
    if game_start > 0:
        now = time()
        dt_1 = datetime.fromtimestamp(game_start)
        dt_2 = datetime.fromtimestamp(now)
        fmt_duration = format_duration(dt_1, dt_2)
    else:
        fmt_duration = "Unknown Duration (Rito pls)"
    game_mode = data["gameMode"]

    response = f"{fmt_duration} in a {game_mode} game, playing {champions[summ_id][1]}.\n"
    if len(champions) > 1:
        response += "He is playing with:"
        for other_id in champions:
            if other_id != summ_id:
                name, champ = champions[other_id]
                response += f"\n - {name} ({champ})"

    return response, users_in_game

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
            try:
                container = container[dict_key]
            except KeyError:
                keys_not_present.append((key_type, dict_key))
                break

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

def get_filtered_stats_v4(all_users, users_in_game, game_info):
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
                        combined_stats.update(participant["timeline"])
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
                stats["teamId"] = team["teamId"]
            else:
                stats["enemyBaronKills"] = team["baronKills"]
                stats["enemyDragonKills"] = team["dragonKills"]
                stats["enemyHeraldKills"] = team["riftHeraldKills"]

    return filtered_stats, active_users

def get_filtered_stats(all_users, users_in_game, game_info):
    """
    Get relevant stats from the given game data and filter the data
    that is relevant for the Discord users that participated in the game.
    """
    if "participantIdentities" in game_info: # Old match v4 data.
        return get_filtered_stats_v4(all_users, users_in_game, game_info)

    kills_per_team = {100: 0, 200: 0}
    damage_per_team = {100: 0, 200: 0}
    our_team = 100
    filtered_stats = []
    active_users = users_in_game
    for participant_data in game_info["participants"]:
        kills_per_team[participant_data["teamId"]] += participant_data["kills"]
        damage_per_team[participant_data["teamId"]] += participant_data["totalDamageDealtToChampions"]

        for disc_id, _, summ_ids in all_users:
            if participant_data["summonerId"] in summ_ids:
                our_team = participant_data["teamId"]
                combined_stats = participant_data
                combined_stats["championId"] = participant_data["championId"]
                combined_stats["timestamp"] = game_info["gameCreation"]
                combined_stats["mapId"] = game_info["mapId"]
                combined_stats["gameDuration"] = int(game_info["gameDuration"] / 1000)
                combined_stats["totalCs"] = combined_stats["neutralMinionsKilled"] + combined_stats["totalMinionsKilled"]
                combined_stats["csPerMin"] = (combined_stats["totalCs"] / combined_stats["gameDuration"]) * 60
                filtered_stats.append((disc_id, combined_stats))

                if users_in_game is not None:
                    user_in_list = False
                    for user_data in users_in_game:
                        if user_data[0] == disc_id:
                            user_in_list = True
                            break
                    if not user_in_list:
                        summ_data = (
                            disc_id, participant_data["summonerName"],
                            participant_data["summonerId"], participant_data["championId"]
                        )
                        active_users.append(summ_data)

    for _, stats in filtered_stats:
        stats["kills_by_team"] = kills_per_team[our_team]
        stats["damage_by_team"] = damage_per_team[our_team]
        for team in game_info["teams"]:
            objectives = team["objectives"]
            if team["teamId"] == our_team:
                stats["baronKills"] = objectives["baron"]["kills"]
                stats["dragonKills"] = objectives["dragon"]["kills"]
                stats["heraldKills"] = objectives["riftHerald"]["kills"]
                stats["gameWon"] = team["win"]
                stats["teamId"] = team["teamId"]
            else:
                stats["enemyBaronKills"] = objectives["baron"]["kills"]
                stats["enemyDragonKills"] = objectives["dragon"]["kills"]
                stats["enemyHeraldKills"] = objectives["riftHerald"]["kills"]

    return filtered_stats, active_users
