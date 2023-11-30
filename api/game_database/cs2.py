from api.config import Config
from api.database import Database

class CS2Database(Database):
    def __init__(self, game: str, config: Config, schema_file: str):
        super().__init__(game, config, schema_file)
