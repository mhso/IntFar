from api.config import Config
from api.database import Database

class LoLDatabase(Database):
    def __init__(self, game: str, config: Config, schema_file: str):
        super().__init__(game, config, schema_file)

