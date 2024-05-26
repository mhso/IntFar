from abc import ABC, abstractmethod

from api.config import Config
from api.user import User

class GameAPIClient(ABC):
    def __init__(self, game: str, config: Config):
        self.game = game
        self.config = config

    @property
    @abstractmethod
    def playable_count(self):
        ...

    @abstractmethod
    def get_active_game(self, user_id) -> dict:
        ...

    @abstractmethod
    def get_active_game_for_user(self, user: User) -> tuple[dict, str]:
        ...

    @abstractmethod
    def get_game_details(self, match_id) -> dict:
        ...

    @abstractmethod
    def get_playable_name(self, played_id) -> str:
        ...

    @abstractmethod
    def get_map_name(self, map_id) -> str:
        ...

    @abstractmethod
    def try_find_playable_id(self, played_name):
        ...

    @abstractmethod
    def get_player_name(self, player_id) -> str:
        ...

    @abstractmethod
    def get_player_names_for_user(self, user: User) -> list[str]:
        ...
