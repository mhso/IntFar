from abc import ABC, abstractmethod
import random

from api.game_stats import GameStats, PlayerStats
from api.config import Config
from api.game_database import GameDatabase
from api.util import load_flavor_texts, SUPPORTED_GAMES

class AwardQualifiers(ABC):
    def __init__(self, config: Config, parsed_game_stats: GameStats):
        self.game = parsed_game_stats.game
        self.guild_id = parsed_game_stats.guild_id
        self.config = config
        self.parsed_game_stats = parsed_game_stats
        self.flavor_texts = self._load_flavor_texts()

    @classmethod
    @abstractmethod
    def INTFAR_REASONS(cls) -> dict[str, str]:
        """
        Get a dictionary with keys being shorthand reasons for getting Int-Far
        and values being a more descriptive reason.
        """

    @classmethod
    @abstractmethod
    def INTFAR_CRITERIAS(cls) -> dict[str, dict[str, float]]:
        """
        Get a dictionary with keys being shorthand reasons for getting Int-Far
        and values being a dictionary of different criterias needing to be met
        for someone to be awarded Int-Far for that reason.
        """

    @classmethod
    @abstractmethod
    def INTFAR_CRITERIAS_DESC(cls) -> dict[str, list[str]]:
        """
        Get a dictionary with keys being shorthand reasons for getting Int-Far
        and values being a dictionary of list of descriptions of criterias
        needing to be met for someone to be awarded Int-Far for that reason.
        """

    @classmethod
    @abstractmethod
    def DOINKS_REASONS(cls) -> dict[str, str]:
        """
        Get a dictionary with keys being shorthand reasons for getting Doinks
        and values being a more descriptive reason.
        """

    @classmethod
    @abstractmethod
    def INTFAR_FLAVOR_TEXTS(cls) -> list[str]:
        """
        Get a list of filenames for flavor texts related to getting Int-Far.
        """

    @classmethod
    @abstractmethod
    def HONORABLE_MENTIONS_FLAVOR_TEXTS(cls) -> list[str]:
        """
        Get a list of filenames for flavor texts related to honorable mentions.
        """

    @classmethod
    @abstractmethod
    def COOL_STATS_FLAVOR_TEXTS(cls) -> list[str]:
        """
        Get a list of filenames for flavor texts related to cool stats.
        """

    @classmethod
    @abstractmethod
    def DOINKS_FLAVOR_TEXTS(cls) -> list[str]:
        """
        Get a list of filenames for flavor texts related to doinks.
        """

    @classmethod
    @abstractmethod
    def GAME_SPECIFIC_FLAVORS(cls) -> list[str]:
        """
        Get a list of game specific flavor texts that subclasses of this class
        can override.
        """
        return {
            "intfar": cls.INTFAR_FLAVOR_TEXTS(),
            "doinks": cls.DOINKS_FLAVOR_TEXTS(),
            "honorable": cls.HONORABLE_MENTIONS_FLAVOR_TEXTS(),
            "stats": cls.COOL_STATS_FLAVOR_TEXTS(),
        }

    @classmethod
    @abstractmethod
    def ALL_FLAVOR_TEXTS(cls) -> list[str]:
        """
        Get a list of filenames for all flavor texts for the game
        that subclasses this class.
        """
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

    def get_flavor_text(self, flavor: str, outer_index, inner_index=None, **params_to_replace) -> str:
        if inner_index is not None:
            flavor = self.GAME_SPECIFIC_FLAVORS()[flavor][outer_index]
            outer_index = inner_index

        flavor_choices = self.flavor_texts[flavor]

        if outer_index == "random":
            flavor_text = flavor_choices[random.randint(0, len(flavor_choices)-1)]
        else:
            flavor_text = flavor_choices[outer_index]

        for key in params_to_replace:
            if params_to_replace[key] is not None:
                value = params_to_replace[key]
                if key == "kda":
                    value = f"{value:.2f}"
                flavor_text = flavor_text.replace("{" + key + "}", str(value))

        # Replace various placeholder strings with actual values
        if "{game}" in flavor_text: # Replace game name if it is present in the text
            flavor_text = flavor_text.replace("{game}", SUPPORTED_GAMES[self.game])

        if "{quantifier}" in flavor_text:
            quantifier = "s" if params_to_replace["value"] != 1 else ""
            flavor_text = flavor_text.replace("{quantifier}", quantifier)

        return flavor_text

    def _load_flavor_texts(self) -> dict[str, list[str]]:
        flavor_text_dict = {}
        for filename in self.ALL_FLAVOR_TEXTS():
            flavor_text_dict[filename] = load_flavor_texts(self.config, filename, self.game)

        return flavor_text_dict

    def get_lifetime_stats(self, database: GameDatabase):
        """
        Returns a list of lifetime awards for each player.
        These events include:
            - A player having played a multiple of 1000 games
            - A player having won a multiple of 1000 games
            - A player having gotten Int-Far a multiple of 100 times
            - A player having gotten Doinks a multiple of 100 times
        """
        lifetime_mentions = {}

        for stats in self.parsed_game_stats.filtered_player_stats:
            lifetime_mentions[stats.disc_id] = []

            game_data = database.get_games_count(stats.disc_id)
            total_games = game_data[0]
            total_wins = game_data[2]
            total_intfars = database.get_intfar_count(stats.disc_id)
            total_doinks = database.get_doinks_count(stats.disc_id)[1]

            values = [total_games, total_wins, total_intfars, total_doinks]
            moduli = [1000, 1000, 100, 100]
            conditions = [
                None,
                self.parsed_game_stats.win == 1,
                self.parsed_game_stats.intfar_id == stats.disc_id,
                stats.doinks is not None
            ]

            for index, (val, mod, cond) in enumerate(zip(values, moduli, conditions)):
                if val > 0 and val % mod == 0 and cond:
                    lifetime_mentions[stats.disc_id].append((index, val))

        return lifetime_mentions

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

    @abstractmethod
    def get_cool_timeline_events(self) -> list[tuple]:
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

    def get_intfar_candidates(self, intfar_details: list[tuple[str, list[PlayerStats]]]) -> tuple[dict[int, list[tuple[str, PlayerStats]]], int, int]:
        max_intfar_count = 1
        max_count_intfar = None
        intfar_counts = {}
        qualifier_data = {}

        # Look through details for the people qualifying for Int-Far.
        # The one with most criteria met gets chosen.
        for stat, tied_intfars in intfar_details:
            if tied_intfars is not None:
                for stats in tied_intfars:
                    current_intfar_count = intfar_counts.get(stats.player_id, 0) + 1
                    intfar_counts[stats.player_id] = current_intfar_count

                    if current_intfar_count >= max_intfar_count:
                        max_intfar_count = current_intfar_count
                        max_count_intfar = stats.player_id

                    data_list = qualifier_data.get(stats.player_id, [])
                    stat_value = getattr(stats, stat)
                    data_list.append((stat, stat_value))
                    qualifier_data[stats.player_id] = data_list

        return qualifier_data, max_count_intfar, max_intfar_count
