from abc import ABC, abstractmethod
from api.config import Config

class GameAPIClient(ABC):
    def __init__(self, game: str, config: Config):
        self.game = game
        self.config = config
