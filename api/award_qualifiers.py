from abc import ABC, abstractmethod

from api.game_stats import GameStats
from api.config import Config
from api.database import Database

class AwardQualifiers(ABC):
    def __init__(self, game: str, config: Config, parsed_game_stats: GameStats):
        self.game = game
        self.config = config
        self.parsed_game_stats = parsed_game_stats

    @abstractmethod
    def get_big_doinks(self) -> tuple[dict[int, list[tuple]], dict[int, str]]:
        ...

    @abstractmethod
    def get_honorable_mentions(self) -> dict[int, list[tuple]]:
        ...

    @abstractmethod
    def get_cool_stats(self) -> dict[int, list[tuple]]:
        """
        Returns a list of miscellaneous interesting stats for each player in the game.
        """
        ...

    @abstractmethod
    def get_lifetime_stats(self, database: Database) -> dict[int, list[tuple]]:
        ...

    @abstractmethod
    def get_intfar_qualifiers(self) -> list[tuple]:
        ...

    @abstractmethod
    def resolve_intfar_ties(self, intfar_data: dict[int, list[tuple]], max_count: int) -> int:
        ...

    @abstractmethod
    def get_intfar(self) -> tuple[int, list[tuple], list[int], str]:
        ... 

    def get_intfar_candidates(self, intfar_details: list[tuple]) -> tuple[dict[int, list[tuple]], int, int]:
        max_intfar_count = 1
        intfar_counts = {}
        max_count_intfar = None
        qualifier_data = {}

        # Look through details for the people qualifying for Int-Far.
        # The one with most criteria met gets chosen.
        for (index, (tied_intfars, stat_value)) in enumerate(intfar_details):
            if tied_intfars is not None:
                for intfar_disc_id in tied_intfars:
                    current_intfar_count = intfar_counts.get(intfar_disc_id, 0) + 1
                    intfar_counts[intfar_disc_id] = current_intfar_count

                    if current_intfar_count >= max_intfar_count:
                        max_intfar_count = current_intfar_count
                        max_count_intfar = intfar_disc_id

                    data_list = qualifier_data.get(intfar_disc_id, [])
                    data_list.append((index, stat_value))
                    qualifier_data[intfar_disc_id] = data_list

        return qualifier_data, max_count_intfar, max_intfar_count
