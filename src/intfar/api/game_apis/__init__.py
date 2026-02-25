from intfar.api.util import find_subclasses_in_dir
from intfar.api.game_api_client import GameAPIClient

_GAME_API_CLIENTS: dict[str, type[GameAPIClient]] = find_subclasses_in_dir("intfar/api/game_apis", GameAPIClient)

def get_api_client(game, config) -> GameAPIClient:
    return _GAME_API_CLIENTS[game](game, config)
