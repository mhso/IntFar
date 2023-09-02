from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from api.user import User
from api.game_api_client import GameAPIClient

@dataclass
class PlayerStats(ABC):
    game_id: int
    disc_id: int
    kills: int
    deaths: int
    assists: int
    doinks: str = None
    kda: str = None
    kp: str = None

    @classmethod
    def STATS_TO_SAVE(cls) -> list[str]:
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

    @classmethod
    def STAT_QUANTITY_DESC(cls) -> dict[str, tuple[str, str]]:
        return {
            "kills": ("most", "fewest"),
            "deaths": ("most", "fewest"),
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
    win: int
    guild_id: int
    players_in_game: list[dict]
    all_player_stats: list[PlayerStats]
    intfar_id: int = None
    intfar_reason: str = None
    filtered_player_stats: list[PlayerStats] = field(default=None, init=False)

    @classmethod
    def STATS_TO_SAVE(cls) -> list[str]:
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

    @classmethod
    def get_stats_from_db(cls, game: str, game_id: int, database, player_stats_cls: PlayerStats):
        game_stats_to_save = cls.STATS_TO_SAVE()
        player_stats_to_save = player_stats_cls.STATS_TO_SAVE()

        game_stats = database.get_game_stats(game, game_stats_to_save, game_id)
        player_stats = database.get_player_stats(game, player_stats_to_save, game_id)

        game_stats_dict = dict(zip(game_stats_to_save, game_stats[0]))
        player_stats_dict = {tup[0]: dict(zip(player_stats_to_save, tup)) for tup in player_stats}

        return game_stats_dict, player_stats_dict

    @abstractmethod
    def get_finished_game_summary(self, disc_id: int) -> str:
        """
        Get a brief text that summaries a player's performance in a finished game.

        :param disc_id: Discord ID of the player for whom to get the summary for
        """
        ...

    def __post_init__(self):
        self.filtered_player_stats = list(filter(lambda x: x.disc_id is not None, self.all_player_stats))

    def find_player_stats(self, disc_id: int, player_list: list[PlayerStats]):
        for player_stats in player_list:
            if player_stats.disc_id == disc_id:
                return player_stats

        return None

class GameStatsParser(ABC):
    def __init__(self, game: str, raw_data: dict, api_client: GameAPIClient, all_users: dict[int, User], guild_id: int):
        self.game = game
        self.raw_data = raw_data
        self.api_client = api_client
        self.all_users = all_users
        self.guild_id = guild_id

    @abstractmethod
    def parse_data(self) -> GameStats:
        ...

    @abstractmethod
    def get_active_game_summary(self, active_id, api_client) -> str:
        ...

    @abstractmethod
    def parse_from_database(self, database, game_id: int) -> GameStats:
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

    filtered_data = list(filter(lambda p: outlier_func_short(p) is not None, player_stats_list))

    if filtered_data == []:
        return None, None

    sorted_data = sorted(filtered_data, key=outlier_func_short, reverse=not asc)

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
