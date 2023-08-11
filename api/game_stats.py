from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from api.user import User

@dataclass
class PlayerStats(ABC):
    game_id: int
    disc_id: int
    kills: int
    deaths: int
    assists: int
    doinks: int = field(init=False)
    kills_by_team: int = field(init=False)

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

    @property
    def stats_to_save(self) -> list[str]:
        """
        Defines which fields from this class should be saved in the database
        """
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
    
    @property
    def stat_quantity_desc(self) -> dict[str, tuple[str, str]]:
        return {
            "kills": ("most", "fewest"),
            "deaths": ("fewest", "most"),
            "deaths": ("most", "fewest"),
            "kda": ("highest", "lowest"),
            "kp": ("highest", "lowest")
        }

@dataclass
class GameStats(ABC):
    game: str
    game_id: int
    timestamp: int
    duration: int
    intfar_id: int = field(init=False)
    intfar_reason: str = field(init=False)
    win: int
    kills_by_our_team: int
    guild_id: int
    players_in_game: list[tuple]
    all_player_stats: list[PlayerStats]
    filtered_player_stats: list[PlayerStats] = field(init=False)

    @property
    def stats_to_save(self) -> list[str]:
        """
        Defines which fields from this class should be saved in the database
        """
        return [
            "game_id",
            "timestamp",
            "duration",
            "intfar_id",
            "intfar_reason",
            "win",
            "guild_id"
        ]

    def __post_init__(self):
        for stat in self.all_player_stats:
            stat.kills_by_team = self.kills_by_our_team

        self.filtered_player_stats = list(filter(lambda x: x[0] is not None, self.all_player_stats))

class GameStatsParser(ABC):
    def __init__(self, game:str,  raw_data: dict, all_users: dict[int, User], guild_id: int):
        self.game = game
        self.raw_data = raw_data
        self.all_users = all_users
        self.guild_id = guild_id

    @abstractmethod
    def parse_data(self) -> GameStats:
        ...

def get_outlier(
    player_stats_list: list[PlayerStats],
    stat: str,
    asc=True,
    include_ties=False
):
    """
    Get the best or worse stat for a player in a finished game, fx.
    the player with most kills, and how many kills that was.

    :param stat:            Name of the stat to find the outlier for
    :param asc:             Whether to sort the data in ascending or descending order
                            to find an outlier
    :param include_ties:    Whether to return a list of potentially tied outliers
                            or just return one person as an outlier, ignoring ties
    """
    def outlier_func_short(x: PlayerStats):
        return getattr(x, stat)

    sorted_data = sorted(player_stats_list, key=outlier_func_short, reverse=not asc)

    if include_ties: # Determine whether there are tied outliers.
        outlier = outlier_func_short(sorted_data[0])
        ties_ids = []
        ties_data = []
        index = 0

        while index < len(sorted_data) and outlier_func_short(sorted_data[index]) == outlier:
            ties_ids.append(sorted_data[index].disc_id)
            ties_data.append(sorted_data[index])
            index += 1

        return ties_ids, ties_data

    return (sorted_data[0].disc_id, getattr(sorted_data[0], stat))

def get_outlier_stat(
    player_stats_list: list[PlayerStats],
    stat: str,
    reverse_order=False
):
    """
    Get data about the outlier (both good and bad)
    for a specific stat in a finished game.

    :param stat:            Name of the stat to find the outlier for
    :param reverse_order    Whether to reverse the order in order to find the outliers
                            Fx. for kills, most are best, for deaths, fewest is best
    """
    most_id, most = get_outlier(player_stats_list, stat, asc=not reverse_order)
    least_id, least = get_outlier(player_stats_list, stat, asc=reverse_order)

    return most_id, most, least_id, least

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
