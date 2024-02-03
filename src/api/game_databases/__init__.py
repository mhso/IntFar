from api.util import find_subclasses_in_dir
from api.game_database import GameDatabase

_DATABASE_CLIENTS: dict[str, GameDatabase] = find_subclasses_in_dir("api/game_databases", GameDatabase)

def get_database_client(game, config) -> GameDatabase:
    return _DATABASE_CLIENTS[game](game, config)
