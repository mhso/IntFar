from api.util import find_subclasses_in_dir
from api.game_api_client import GameAPIClient

_GAME_API_CLIENTS: dict[str, GameAPIClient] = find_subclasses_in_dir("api/game_api", GameAPIClient)

def get_api_client(game, config) -> GameAPIClient:
    return _GAME_API_CLIENTS[game](game, config)
