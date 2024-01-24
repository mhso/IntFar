from api.game_database import GameDatabase

class LoLDatabase(GameDatabase):
    def __init__(self, config):
        super().__init__(config)
