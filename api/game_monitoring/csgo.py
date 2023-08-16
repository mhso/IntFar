from typing import Coroutine
from api.config import Config
from api.database import Database
from api.game_monitor import GameMonitor
from api.steam_api import SteamAPIClient

class CSGOGameMonitor(GameMonitor):
    def __init__(self, config: Config, database: Database, game: str, game_over_callback: Coroutine, steam_api: SteamAPIClient):
        super().__init__(config, database, game, game_over_callback, steam_api)
