from dataclasses import dataclass
from api.game_stats import GameStats, PlayerStats, GameStatsParser

@dataclass
class CSGOPlayerStats(PlayerStats):
    mvps: int = None
    score: int = None
    hsp: int = None
    adr: float = None
    ud: int = None
    ef: int = None

    @classmethod
    def STATS_TO_SAVE(cls):
        return super().STATS_TO_SAVE() + [
            "mvps",
            "score",
            "hsp",
            "adr",
            "ud",
            "ef",
        ]

    @classmethod
    def STAT_QUANTITY_DESC(cls):
        stat_quantities = dict(super().STAT_QUANTITY_DESC())
        stat_quantities.update(
            mvps=("most", "fewest"),
            score=("highest", "lowest"),
            hsp=("highest", "lowest"),
            adr=("highest", "lowest"),
            ud=("most", "least"),
            ef=("most", "fewest"),
        )
        return stat_quantities

@dataclass
class CSGOGameStats(GameStats):
    map_name: str = None
    team_t: bool = None
    long_match: bool = None

    @classmethod
    def STATS_TO_SAVE(cls):
        return super().STATS_TO_SAVE() + [
            "map_name",
            "team_t",
            "long_match",
        ]

class CSGOGameStatsParser(GameStatsParser):
    pass
