from abc import ABC, abstractmethod
import random

from api.game_stats import GameStats
from api.config import Config
from api.database import Database
from api.util import load_flavor_texts

class AwardQualifiers(ABC):
    def __init__(self, config: Config, parsed_game_stats: GameStats):
        self.game = parsed_game_stats.game
        self.guild_id = parsed_game_stats.guild_id
        self.config = config
        self.parsed_game_stats = parsed_game_stats
        self.flavor_texts = self._load_flavor_texts()

    @property
    def all_flavor_texts(self) -> list[str]:
        return [
            "intfar",
            "no_intfar",
            "lifetime_events",
            "intfar_streak",
            "win_streak",
            "loss_streak",
            "broken_win_streak",
            "broken_loss_streak",
            "ifotm"
        ]

    @property
    @abstractmethod
    def intfar_reasons(self) -> list[str]:
        ...

    @property
    @abstractmethod
    def intfar_flavor_texts(self) -> list[str]:
        ...

    @property
    @abstractmethod
    def honorable_mentions_flavor_texts(self) -> list[str]:
        ...

    @property
    @abstractmethod
    def cool_stats_flavor_texts(self) -> list[str]:
        ...

    @property
    @abstractmethod
    def doinks_flavor_texts(self) -> list[str]:
        ...

    @property
    def game_specific_flavors(self) -> list[str]:
        return {
            "intfar": self.intfar_flavor_texts,
            "doinks": self.intfar_flavor_texts,
            "honorable": self.intfar_flavor_texts,
            "stats": self.intfar_flavor_texts,
        }

    def get_flavor_text(self, flavor: str, outer_index, inner_index=None, **params_to_replace) -> str:
        if inner_index is not None:
            flavor = self.game_specific_flavors[flavor]
            outer_index = inner_index

        flavor_choices = self.flavor_texts[flavor]

        if outer_index == "random":
            flavor_text = flavor_choices[random.randint(0, len(flavor_choices)-1)]
        else:
            flavor_text = flavor_choices[outer_index]

        for key in params_to_replace:
            if params_to_replace[key] is not None:
                flavor_text = flavor_text.replace("{" + key + "}", str(params_to_replace[key]))

        return flavor_text

    def _load_flavor_texts(self) -> dict[str, str]:
        flavor_text_dict = {}
        for filename in self.all_flavor_texts:
            flavor_text_dict[filename] = load_flavor_texts(filename, self.game)

        return flavor_text_dict

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
