from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from api.user import User
from api.game_api_client import GameAPIClient

@dataclass
class PlayerStats(ABC):
    """
    Dataclass representing parsed stats for each player from a finished match.
    The base class contains shared player stats for all games supported by Int-Far.
    """
    game_id: int
    disc_id: int
    player_id: str
    kills: int
    deaths: int
    assists: int
    doinks: str = None
    kda: str = None
    kp: str = None

    @classmethod
    def stats_to_save(cls) -> list[str]:
        """
        Defines which fields from this class should be saved in the database
        """
        return [
            "game_id",
            "player_id",
            "doinks",
            "kills",
            "deaths",
            "assists",
            "kda",
            "kp"
        ]

    @classmethod
    def stat_quantity_desc(cls) -> dict[str, tuple[str, str]]:
        """
        Get a dictionary mapping stats to a tuple of the relevant words describing
        the best/worst quantity for that stat. Fx. "kills" -> ("most", "fewest")
        """
        return {
            "kills": ("most", "fewest"),
            "deaths": ("fewest", "most"),
            "assists": ("most", "fewest"),
            "kda": ("highest", "lowest"),
            "kp": ("highest", "lowest")
        }

    @classmethod
    def formatted_stat_names(cls) -> dict[str, str]:
        formatted = {}
        for stat in PlayerStats.stats_to_save():
            if stat in ("kda", "kp"):
                fmt_stat = stat.upper()
            else:
                fmt_stat = stat.capitalize()

            formatted[stat] = fmt_stat

        return formatted

    @classmethod
    def get_formatted_stat_value(cls, stat, value) -> str:
        if isinstance(value, float):
            fmt_val = f"{value:.2f}"
        elif value is None:
            fmt_val = "0"
        else:
            fmt_val = str(value)

        if stat == "kp":
            fmt_val = f"{fmt_val}%"

        return fmt_val

@dataclass
class GameStats(ABC):
    """
    Dataclass representing parsed stats for a finished match.
    The base class contains shared match stats for all games supported by Int-Far.
    """
    game: str
    game_id: int
    timestamp: int
    duration: int
    win: int
    guild_id: int
    players_in_game: list[dict]
    all_player_stats: list[PlayerStats]
    map_id: int = None
    intfar_id: int = None
    intfar_reason: str = None
    filtered_player_stats: list[PlayerStats] = field(default=None, init=False)

    @classmethod
    def stats_to_save(cls) -> list[str]:
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
    def get_stats_from_db(cls, database, player_stats_cls: PlayerStats, game_id: int = None) -> tuple[list[dict], list[dict]]:
        """
        Load stats from the database for all games or a single game
        as well as stats for players in the game(s).
        """
        game_stats_to_save = cls.stats_to_save()
        player_stats_to_save = player_stats_cls.stats_to_save()

        game_stats = database.get_game_stats(game_stats_to_save, game_id)
        player_stats = database.get_player_stats(player_stats_to_save, game_id)

        game_stats_dicts = [dict(zip(game_stats_to_save, stats)) for stats in game_stats]

        player_stats_by_game_id = {}
        for tup in player_stats:
            game_id = tup[0]
            disc_id = int(tup[1])
            if game_id not in player_stats_by_game_id:
                player_stats_by_game_id[game_id] = {}

            player_stats_by_game_id[game_id][disc_id] = dict(zip(player_stats_to_save, tup))

        player_stats_dicts = list(player_stats_by_game_id.values())

        return game_stats_dicts, player_stats_dicts

    @classmethod
    def find_player_stats(cls, disc_id: int, player_list: list[PlayerStats]) -> PlayerStats:
        """
        Find the stats for a player given their disc_id and a list of player_stats.
        """
        for player_stats in player_list:
            if player_stats.disc_id == disc_id:
                return player_stats

        return None

    @abstractmethod
    def get_finished_game_summary(self, disc_id: int) -> str:
        """
        Get a brief text that summarizes a player's performance in a finished game.

        ### Parameters
        :param disc_id: Discord ID of the player for whom to get the summary for

        ### Returns
        String describing how the given player performed in the game.
        """
        ...

    def __post_init__(self):
        self.filtered_player_stats = list(filter(lambda x: x.disc_id is not None, self.all_player_stats))

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
    def get_active_game_summary(self, active_id) -> str:
        ...

    @abstractmethod
    def parse_from_database(self, database, game_id: int = None) -> list[GameStats]:
        """
        Get data for a given game, or all games if `game_id` is None, from the database
        and return a list of GameStats objects with the game data.
        """
        ...

@dataclass
class PostGameStats:
    game: str
    status_code: int
    guild_id: int
    parsed_game_stats: GameStats = None
    intfar_data: tuple[int, list[tuple], bool, str] = None
    intfar_streak_data: tuple[int, int] = None
    doinks_data: tuple[dict[int, list[tuple]], dict[int, str]] = None
    ranks_data: dict[int, tuple[int, int]] = None
    winstreak_data: tuple[dict[int, list[int]], dict[int, list[int]]] = None
    timeline_data: list[tuple] = None
    cool_stats_data: dict[int, list[tuple[int, int | str, int]]] = None
    beaten_records_data: tuple[list[tuple[str, int, int, int, int]], list[tuple[str, int, int, int, int]]] = None
    lifetime_data: dict[int, tuple[int, int]] = None

def get_outlier(
    player_stats_list: list[PlayerStats],
    stat: str,
    asc=True,
    include_ties=False
) -> list[PlayerStats] | PlayerStats | None:
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
        return None

    sorted_data = sorted(filtered_data, key=outlier_func_short, reverse=not asc)

    if include_ties: # Determine whether there are tied outliers.
        outlier = outlier_func_short(sorted_data[0])
        ties_data = []
        index = 0

        while index < len(sorted_data) and outlier_func_short(sorted_data[index]) == outlier:
            ties_data.append(sorted_data[index])
            index += 1

        return ties_data

    return sorted_data[0]

def get_outlier_stat(
    player_stats_list: list[PlayerStats],
    stat: str,
    reverse_order=False
) -> tuple[int, int, int, int]:
    """
    Get data about the outlier (both good and bad)
    for a specific stat in a finished game.

    :param stat:            Name of the stat to find the outlier for
    :param reverse_order    Whether to reverse the order in order to find the outliers
                            Fx. for kills, most are best, for deaths, fewest is best
    """
    most = get_outlier(player_stats_list, stat, asc=not reverse_order)
    least = get_outlier(player_stats_list, stat, asc=reverse_order)

    most_id, most_val = None, None
    if most is not None:
        most_id = most.disc_id
        most_val = getattr(most, stat)

    least_id, least_val = None, None
    if least is not None:
        least_id = least.disc_id
        least_val = getattr(least, stat)

    return most_id, most_val, least_id, least_val

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
