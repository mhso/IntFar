from intfar.api.util import find_subclasses_in_dir
from intfar.api.game_database import GameDatabase

_DATABASE_CLIENTS: dict[str, type[GameDatabase]] = find_subclasses_in_dir("intfar/api/game_databases", GameDatabase)

def get_database_client(game, config) -> GameDatabase:
    return _DATABASE_CLIENTS[game](game, config)
