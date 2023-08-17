from typing import Coroutine
from api.config import Config
from api.database import Database
from api.game_monitor import GameMonitor
from api.game_api.csgo import SteamAPIClient

class CSGOGameMonitor(GameMonitor):
    def __init__(self, game: str, config: Config, database: Database, game_over_callback: Coroutine, steam_api: SteamAPIClient):
        super().__init__(game, config, database, game_over_callback, steam_api)

    async def get_active_game_info(self, guild_id):
        pass

    async def get_finished_game_info(self, guild_id):
        pass