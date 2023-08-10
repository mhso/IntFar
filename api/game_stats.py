from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from api.user import User

@dataclass
class PlayerStats(ABC):
    game_id: int
    disc_id: int
    doinks: int = None
    kills: int
    deaths: int
    assists: int
    kills_by_team: field(init=False)

    @property
    def kda(self) -> float:
        if self.deaths == 0:
            return self.kills + self.assists

        return (self.kills + self.assists) / self.deaths

    @property
    def kp(self) -> int:
        if self.kills_by_team == 0:
            return 100

        return int((float(self.kills + self.assists) / float(self.kills_by_team)) * 100.0)

    def stats_to_save(self):
        return [
            "game_id",
            "disc_id",
            "doinks",
            "kills",
            "deaths",
            "assists",
            "kda",
            "kp"
        ]

@dataclass
class GameStats(ABC):
    game_id: int
    timestamp: int
    duration: int
    intfar_id: int = None
    intfar_reason: str = None
    win: bool
    kills_by_our_team: int
    guild_id: int
    players_in_game: list[tuple]
    all_player_stats: list[PlayerStats]
    filtered_player_stats: field(init=False)

    def __post_init__(self):
        for stat in self.all_player_stats:
            stat.kills_by_team = self.kills_by_our_team

        self.filtered_player_stats = list(filter(lambda x: x[0] is not None, self.all_player_stats))

    def get_outlier(
        self,
        stat: str,
        asc=True,
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
        :param include_ties:    Whether to return a list of potentially tied outliers
                                or just return one person as an outlier, ignoring ties
        """
        def outlier_func_short(x: PlayerStats):
            return getattr(x, stat)

        sorted_data = sorted(self.filtered_player_stats, key=outlier_func_short, reverse=not asc)

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
        data: list[tuple],
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

    def stats_to_save(self):
        return [
            "game_id",
            "timestamp",
            "duration",
            "intfar_id",
            "intfar_reason",
            "win",
            "guild_id"
        ]

class GameStatsParser(ABC):
    def __init__(self, raw_data: dict, all_users: dict[int, User], guild_id: int):
        self.raw_data = raw_data
        self.all_users = all_users
        self.guild_id = guild_id

    @abstractmethod
    def parse_data(self) -> GameStats:
        ...

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
