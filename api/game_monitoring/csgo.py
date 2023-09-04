import asyncio
from typing import Coroutine

from steam.steamid import SteamID

from mhooge_flask.logging import logger

from api.config import Config
from api.database import Database
from api.user import User
from api.game_monitor import GameMonitor
from api.game_api.csgo import SteamAPIClient

class CSGOGameMonitor(GameMonitor):
    POSTGAME_STATUS_CUSTOM_GAME = 4
    POSTGAME_STATUS_DUPLICATE = 5
    POSTGAME_STATUS_SHORT_MATCH = 6
    POSTGAME_STATUS_SURRENDER = 7

    def __init__(self, game: str, config: Config, database: Database, game_over_callback: Coroutine, steam_api: SteamAPIClient):
        super().__init__(game, config, database, game_over_callback, steam_api)

    @property
    def min_game_minutes(self):
        return 10

    async def get_active_game_info(self, guild_id):
        user_dict = (
            self.users_in_voice.get(guild_id, {})
            if self.users_in_game.get(guild_id) is None
            else self.users_in_game[guild_id]
        )

        steam_id_map = {}
        for disc_id in user_dict:
            for steam_id in user_dict[disc_id].ingame_id:
                steam_id_map[steam_id] = disc_id

        # Get a dictionary of information about friends who are in-game
        account_id_map = {}
        for disc_id in user_dict:
            for steam_id in user_dict[disc_id].ingame_id:
                account_id_map[SteamID(steam_id).account_id] = steam_id

        active_games = self.api_client.get_active_game(steam_id_map)
        # {'requestId': 1, 'accountIds': [10150287], 'watchableMatchInfos': [{'serverIp': 1682023191, 'tvPort': 1, 'tvSpectators': 1, 'tvTime': 661, 'tvWatchPassword': 'JuuR4sOG8GCPWjiQtGT8p6XlPJJVpnZoiD8zBNDYf7U=', 'clDecryptdataKeyPub': '7758645395651441676', 'gameType': 1048584, 'gameMapgroup': 'mg_de_cache', 'gameMap': 'de_cache', 'serverId': '90175702499272731', 'matchId': '3635666711287431410'}]}

        users_in_current_game = {}

        if active_games is None or "watchableMatchInfos" not in active_games or "accountIds" not in active_games:
            return None, users_in_current_game, None # No active game

        logger.info("Len of lists:", len(active_games["accountIds"]), len(active_games["watchableMatchInfos"]))

        game_ids = set()
        active_game = None
        for account_id, game_info in zip(active_games["accountIds"], active_games["watchableMatchInfos"]):
            match_id = game_info["matchId"]
            game_ids.add(match_id)

            if account_id in account_id_map:
                steam_id = account_id_map[account_id]
                disc_id = steam_id_map[steam_id]
                if self.active_game.get(guild_id) is None: # First time we see this active game
                    steam_name = self.api_client.get_steam_display_name(steam_id)
                else:
                    steam_name = user_dict[disc_id].ingame_name

                users_in_current_game[disc_id] = User(disc_id, user_dict[disc_id].secret, [steam_name], [steam_id])

                active_game = game_info

        if len(game_ids) > 1: # People are in different games
            return None, users_in_current_game, self.GAME_STATUS_NOCHANGE

        if active_game is None:
            return None, users_in_current_game, None

        return (
            {
                "id": active_game["matchId"],
                "start": 0,
                "map_id": active_game["gameMap"],
                "map_name": self.api_client.get_map_name(active_game["gameMap"]),
                "game_type": active_game["gameType"]
            },
            users_in_current_game,
            None
        )

    async def get_finished_game_info(self, guild_id):
        match_id = self.active_game[guild_id]["id"]

        current_sharecodes = {
            disc_id: self.database.users_by_game[self.game][disc_id].latest_match_token
            for disc_id in self.users_in_game[guild_id]
        }

        retries = 4
        time_to_sleep = 30
        code_retrieved = {disc_id: False for disc_id in current_sharecodes}
        new_sharecode = None
        for _ in range(retries):
            for disc_id in current_sharecodes:
                if code_retrieved[disc_id]:
                    continue

                user_data = self.database.users_by_game[self.game][disc_id]
                next_code = self.api_client.get_next_sharecode(
                    user_data.steam_id,
                    user_data.match_auth_code,
                    user_data.latest_match_token
                )

                logger.info(f"New match sharing code for '{disc_id}': '{next_code}'")

                if next_code is not None and next_code != current_sharecodes[disc_id]: # Error or new code hasn't been updated yet
                    self.database.set_new_csgo_sharecode(disc_id, next_code)
                    code_retrieved[disc_id] = True
                    new_sharecode = new_sharecode

                await asyncio.sleep(0.5)

            if all(code_retrieved[disc_id] for disc_id in code_retrieved):
                break

            logger.warning(
                f"Next match sharecode not yet received for CSGO! Retrying in {time_to_sleep} secs..."
            )

            await asyncio.sleep(time_to_sleep)

        if not all(code_retrieved[disc_id] for disc_id in code_retrieved):
            logger.bind(game_id=match_id, sharecode=new_sharecode, guild_id=guild_id).error(
                "Next match sharecode STILL not yet received for everyone after 3 tries! Saving to missing games..."
            )
            status_code = self.POSTGAME_STATUS_MISSING

        else:
            game_info = self.api_client.get_game_details(new_sharecode)

            if self.database.game_exists(self.game, game_info["matchID"]):
                status_code = self.POSTGAME_STATUS_DUPLICATE
                logger.warning(
                    "We triggered end of game stuff again... Strange!"
                )

            elif len(self.users_in_game[guild_id]) == 1:
                status_code = self.POSTGAME_STATUS_SOLO

            elif not game_info.long_match:
                # Game was a short match
                status_code = self.POSTGAME_STATUS_SHORT_MATCH

            elif game_info["gameDuration"] < self.min_game_minutes * 60:
                # Game was too short to count. Probably an early surrender.
                status_code = self.POSTGAME_STATUS_SURRENDER

            else:
                status_code = self.POSTGAME_STATUS_OK

        return game_info, status_code
