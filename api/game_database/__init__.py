from api.util import find_subclasses_in_dir
from api.database import Database

_DATABASE_CLIENTS: dict[str, Database] = find_subclasses_in_dir("api/game_database", Database)

def get_database_client(game, config) -> Database:
    return _DATABASE_CLIENTS[game](game, config)
