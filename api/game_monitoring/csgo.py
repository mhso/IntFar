from typing import Coroutine
from api.config import Config
from api.database import Database
from api.game_monitor import GameMonitor
from api.game_api.csgo import SteamAPIClient

class CSGOGameMonitor(GameMonitor):
    def __init__(self, game: str, config: Config, database: Database, game_over_callback: Coroutine, steam_api: SteamAPIClient):
        super().__init__(game, config, database, game_over_callback, steam_api)

    async def get_active_game_info(self, guild_id):
        steam_id_map = {}
        for disc_id in self.database.users_by_game.get(self.game, {}):
            for steam_id in self.database.users_by_game[self.game][disc_id].ingame_id:
                steam_id_map[int(steam_id)] = disc_id

        # Get a dictionary of information about friends who are in-game
        friends_in_game = self.api_client.get_active_game(steam_id_map)

    async def get_finished_game_info(self, guild_id):
        pass
