from api.util import find_subclasses_in_dir
from api.game_monitor import GameMonitor

_GAME_MONITORS: dict[str, GameMonitor] = find_subclasses_in_dir("api/game_monitors", GameMonitor)

def get_game_monitor(game, config, meta_database, game_database, api_client, callback=None) -> GameMonitor:
    return _GAME_MONITORS[game](game, config, meta_database, game_database, api_client, callback)
