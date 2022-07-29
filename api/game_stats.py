from datetime import datetime
from time import time

from api.util import format_duration
from api.riot_api import RiotAPIClient

def calc_kda(stats: dict):
    """
    Calculate kill/death/assist ratio.

    :param stats:   Stats data for a player in a finished game,
                    fetched from Riot API
    """
    if stats["deaths"] == 0:
        return stats["kills"] + stats["assists"]

    return (stats["kills"] + stats["assists"]) / stats["deaths"]

def calc_kill_participation(stats: dict, total_kills: int):
    """
    Calculate kill participation.

    :param stats:       Stats data for a player in a finished game,
                        fetched from Riot API
    :param total_kills: Total kills by the team that the player was on
    """
    if total_kills == 0:
        return 100

    return int((float(stats["kills"] + stats["assists"]) / float(total_kills)) * 100.0)

def get_stat_value(stats: dict, stat: str, total_kills: int):
    """
    Get the value of a stat for a player in a finished game.

    :param stats:       Stats data for a player in a finished game,
                        fetched from Riot API
    :param stat         Name of the stat, fx. 'kills', 'gold', etc.
    :param total_kills: Total kills by the team that the player was on
    """
    if stat == "kda":
        return calc_kda(stats)

    if stat == "kp":
        return calc_kill_participation(stats, total_kills)

    return stats[stat]

def get_outlier(
    data: list[tuple(int, dict)],
    stat: str,
    asc=True,
    total_kills=0,
    include_ties=False
):
    """
    Get the best or worse stat for a player in a finished game, fx.
    the player with most kills, and how many kills that was.

    :param data:            List containing a tuple of (discord_id, stats_data)
                            for each Int-Far registered player in the game
    :param stat:            Name of the stat to find the outlier for
    :param asc:             Whether to sort the data in ascending or descending order
                            to find an outlier
    :param total_kills:     Total kills by the team that the players were on
    :param include_ties:    Whether to return a list of potentially tied outliers
                            or just return one person as an outlier, ignoring ties
    """
    def outlier_func_short(x):
        return get_stat_value(x[1], stat, total_kills)

    sorted_data = sorted(data, key=outlier_func_short, reverse=not asc)

    if include_ties: # Determine whether there are tied outliers.
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

def get_outlier_stat(
    data: list[tuple(int, dict)],
    stat: str,
    reverse_order=False,
    total_kills=0
):
    """
    Get data about the outlier (both good and bad)
    for a specific stat in a finished game.

    :param stat:            Name of the stat to find the outlier for
    :param data:            List containing a tuple of (discord_id, game_stats)
                            for each Int-Far registered player in the game
    :param reverse_order    Whether to reverse the order in order to find the outliers
                            Fx. for kills, most are best, for deaths, fewest is best.
    :param total_kills      Total kills by the team that the players were on
    """
    most_id, stats = get_outlier(data, stat, asc=not reverse_order, total_kills=total_kills)
    most = get_stat_value(stats, stat, total_kills)
    least_id, stats = get_outlier(data, stat, asc=reverse_order, total_kills=total_kills)
    least = get_stat_value(stats, stat, total_kills)

    return most_id, most, least_id, least

def get_player_stats(data, summ_ids):
    """
    Get a specific player's stats from a dictionary of game data

    :param data:        Dictionary containing un-filtered data about a finished
                        game fetched from Riot League API
    :param summ_ids:    List of summoner ids belonging to a player,
                        for which to extract stats for
    """
    if "participantIdentities" in data:
        # We have to do this to handle /match/v4 stuff...
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

def get_finished_game_summary(
    data: dict,
    summ_ids: list[str],
    riot_api: RiotAPIClient
):
    """
    Get a brief text that summaries a player's performance in a finished game.

    :param data:        Dictionary containing un-filtered data about a finished
                        game fetched from Riot League API
    :param summ_ids:    List of summoner ids belonging to a player,
                        for which to get the summary for
    :parma riot_api:    Riot API client instance
    """
    stats = get_player_stats(data, summ_ids)

    champ_played = riot_api.get_champ_name(stats["championId"])
    if champ_played is None:
        champ_played = "Unknown Champ (Rito pls)"

    date = datetime.fromtimestamp(data["gameCreation"] / 1000.0).strftime("%Y/%m/%d")
    duration = data["gameDuration"]
    dt_1 = datetime.fromtimestamp(time())
    dt_2 = datetime.fromtimestamp(time() + duration)
    fmt_duration = format_duration(dt_1, dt_2)

    return (
        f"{champ_played} with a score of {stats['kills']}/" +
        f"{stats['deaths']}/{stats['assists']} on {date} in a {fmt_duration} long game"
    )

def get_active_game_summary(data, summ_id, summoners, riot_api):
    """
    Extract data about a currently active game.

    :param data:    Data aquired from Riot's API about an active game
    :summ_id:       The summoner ID that we should extract data for in the game
    :summoners:     List of summoners/users that are registered with Int-Far.
                    Any summoners in the game not part of this list is filtered out
    :riot_api       Riot API Client instance. Used to get champion name of the player
    """
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
        fmt_duration = format_duration(dt_1, dt_2) + " "
    else:
        fmt_duration = ""
    game_mode = data["gameMode"]

    response = f"{fmt_duration}in a {game_mode} game, playing {champions[summ_id][1]}.\n"
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

    This method is used for Riot's older Match API v4, where data is formatted
    differently from v5. This method is only used to get data from older games,
    before Riot migrated to Match API v5.
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

    This method is used for Riot's newer Match API v5. This is now the standard
    for all new League of Legends games (until a new one comes along).
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
                combined_stats["lane"] = participant_data["teamPosition"]
                combined_stats["timestamp"] = game_info["gameCreation"]
                combined_stats["mapId"] = game_info["mapId"]
                combined_stats["gameDuration"] = int(game_info["gameDuration"])
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

def get_filtered_timeline_stats(filtered_game_stats, timeline_data):
    """
    Get interesting timeline related data. This pertains to data that
    changes during the game, such as maximum gold deficit/lead of a team
    during the course of the game.
    """
    puuid_map = {}

    our_team_lower = True

    for disc_id, stats in filtered_game_stats:
        puuid = stats["puuid"]
        for participant_data in timeline_data["participants"]:
            if participant_data["puuid"] == puuid:
                our_team_lower = participant_data["participantId"] <= 5
                puuid_map[puuid] = disc_id
                break

    timeline_data["puuid_map"] = puuid_map
    timeline_data["gameWon"] = filtered_game_stats[0][1]["gameWon"]
    timeline_data["ourTeamLower"] = our_team_lower

    return timeline_data
