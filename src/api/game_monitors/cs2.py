import asyncio
from typing import Coroutine
from time import time

from mhooge_flask.logging import logger

from api.config import Config
from api.game_database import GameDatabase
from api.user import User
from api.game_monitor import GameMonitor
from api.game_apis.cs2 import SteamAPIClient

class CS2GameMonitor(GameMonitor):
    POSTGAME_STATUS_CUSTOM_GAME = 4
    POSTGAME_STATUS_DUPLICATE = 5
    POSTGAME_STATUS_SHORT_MATCH = 6
    POSTGAME_STATUS_SURRENDER = 7

    def __init__(self, game: str, config: Config, database: GameDatabase, game_over_callback: Coroutine, steam_api: SteamAPIClient):
        super().__init__(game, config, database, game_over_callback, steam_api)

    @property
    def min_game_minutes(self):
        return 10

    async def _get_next_sharecode(self, users: dict[int, User]):
        """
        Get the newest sharecode for all users in 'users'.
        Retrieves codes for 
        """
        code_retrieved = {disc_id: False for disc_id in users}
        for disc_id in users:
            new_code = None
            user_data = users[disc_id]

            curr_code = user_data.latest_match_token[0]
            while curr_code is not None:
                curr_code = self.api_client.get_next_sharecode(
                    user_data.player_id[0],
                    user_data.match_auth_code[0],
                    curr_code
                )
                if curr_code is not None:
                    new_code = curr_code

                await asyncio.sleep(2)

            if new_code is not None and new_code != user_data.latest_match_token[0]:
                old_code = user_data.latest_match_token[0]
                text = f"Match share code for '{disc_id}' was: '{old_code}', now: '{new_code}'"
                logger.bind(event="cs_sharecode", name=user_data.player_name[0], old_code=old_code, new_code=new_code).info(text)
                code_retrieved[disc_id] = True

        if all(code_retrieved.values()):
            return new_code

        return None

    async def get_active_game_info(self, guild_id):
        if not self.api_client.is_logged_in():
            # Steam is not logged on, don't try to track games
            return None, {}, self.GAME_STATUS_NOCHANGE

        # Create a bunch of maps for different ID representations
        user_dict = (
            self.users_in_voice.get(guild_id, {})
            if self.users_in_game.get(guild_id) is None
            else self.users_in_game[guild_id]
        )

        steam_id_map = {}
        for disc_id in user_dict:
            for steam_id in user_dict[disc_id].player_id:
                steam_id_map[int(steam_id)] = disc_id

        active_users = []
        for steam_id in steam_id_map:
            is_user_active = self.api_client.is_person_ingame(steam_id)     
            if is_user_active:
                active_users.append(steam_id)

        users_in_current_game = {}

        if active_users == []:
            return None, users_in_current_game, None # No active users

        # Gather data about users in the game
        for steam_id in active_users:
            disc_id = steam_id_map[steam_id]
            if self.active_game.get(guild_id) is None: # First time we see this active game
                steam_name = self.api_client.get_steam_display_name(steam_id)
            else:
                steam_name = user_dict[disc_id].player_name[0]

            user = User.clone(self.database.game_users[disc_id])
            user.player_id = [steam_id]
            user.player_name = [steam_name]
            users_in_current_game[disc_id] = user

        if self.active_game.get(guild_id) is not None:
            # Check if game is over
            next_code = await self._get_next_sharecode(user_dict)

            if next_code is not None:
                # New sharecodes recieved for all players. Game is over!
                for disc_id in users_in_current_game:
                    users_in_current_game[disc_id].latest_match_token[0] = next_code

                return None, users_in_current_game, None

        return (
            {
                "id": str(time()),
                "start": 0,
                "map_id": "Unknown",
                "map_name": "Unknown",
                "game_type": "Competitive",
                "game_mode": "CS2",
            },
            users_in_current_game,
            None
        )

    async def get_finished_game_status(self, game_info: dict, guild_id: int):
        # Define a value that determines whether the played game was (most likely) a CS2 match
        last_round = game_info["matches"][0]["roundstatsall"][-1]
        max_rounds = max(last_round["teamScores"])

        if self.database.game_exists(game_info["matchID"]):
            logger.warning(
                "We triggered end of game stuff again... Strange!"
            )
            return self.POSTGAME_STATUS_DUPLICATE

        if len(self.users_in_game.get(guild_id, [])) == 1:
            return self.POSTGAME_STATUS_SOLO

        if max_rounds < 10:
            # Game was a short match
            return self.POSTGAME_STATUS_SHORT_MATCH

        if last_round["matchDuration"] < self.min_game_minutes * 60:
            # Game was too short to count. Probably an early surrender.
            return self.POSTGAME_STATUS_SURRENDER

        return self.POSTGAME_STATUS_OK

    async def get_finished_game_info(self, guild_id: int):
        # Get users who haven't yet received a new sharecode
        users_missing = {
            disc_id: self.users_in_game[guild_id][disc_id]
            for disc_id in self.users_in_game[guild_id]
            if self.users_in_game[guild_id][disc_id].latest_match_token[0] == self.database.game_users[disc_id].latest_match_token[0]
        }

        # Get new CS sharecode, if we didn't already get it when searching for active games
        if users_missing != {}:
            next_code = await self._get_next_sharecode(users_missing)
        else:
            next_code = list(self.users_in_game[guild_id].values())[0].latest_match_token[0]

        if next_code is None:
            logger.bind(sharecodes=list(users_missing.values()), guild_id=guild_id).error(
                "Next match sharecode STILL not received for everyone after game ended! Saving to missing games..."
            )
            game_info = None
            status_code = self.POSTGAME_STATUS_MISSING

        else:
            game_info = self.api_client.get_game_details(next_code)
            if game_info is None:
                raise ValueError("Could not get game_info for some reason!")

            status_code = await self.get_finished_game_status(game_info, guild_id)

        return game_info, status_code
