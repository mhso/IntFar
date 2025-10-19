from api.game_databases.cs2 import CS2GameDatabase
from api.config import Config

class CS2GameDatabase(CS2GameDatabase):
    def __init__(self, game: str, config: Config):
        super().__init__(game, config)
