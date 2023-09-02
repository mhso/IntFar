from abc import ABC, abstractmethod
from api.config import Config

class GameAPIClient(ABC):
    def __init__(self, game: str, config: Config):
        self.game = game
        self.config = config

    @abstractmethod
    def get_active_game(self, user_id) -> dict:
        ...

    @abstractmethod
    def get_game_details(self, match_id) -> dict:
        ...

    @abstractmethod
    def get_map_name(self, map_id):
        ...

    @abstractmethod
    def try_find_played(self, played_name):
        ...
