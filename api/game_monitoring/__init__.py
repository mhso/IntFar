from api.util import find_subclasses_in_dir
from api.game_monitor import GameMonitor

_GAME_MONITORS: dict[str, GameMonitor] = find_subclasses_in_dir("api/game_monitoring", GameMonitor)

def get_game_monitor(game, config, database, callback, api_client) -> GameMonitor:
    return _GAME_MONITORS[game](game, config, database, callback, api_client)
