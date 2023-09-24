import asyncio
from typing import Coroutine
from time import time

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
    POSTGAME_STATUS_CS2 = 7
    POSTGAME_STATUS_SURRENDER = 8

    def __init__(self, game: str, config: Config, database: Database, game_over_callback: Coroutine, steam_api: SteamAPIClient):
        super().__init__(game, config, database, game_over_callback, steam_api)

    @property
    def min_game_minutes(self):
        return 10

    async def get_active_game_info(self, guild_id):
        if not self.api_client.logged_on_once:
            # Steam is not logged on, don't try to track games
            return None, {}, None

        # Create a bunch of maps for different IDs
        user_dict = (
            self.users_in_voice.get(guild_id, {})
            if self.users_in_game.get(guild_id) is None
            else self.users_in_game[guild_id]
        )

        steam_id_map = {}
        for disc_id in user_dict:
            for steam_id in user_dict[disc_id].ingame_id:
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
                steam_name = user_dict[disc_id].ingame_name[0]

            user = User.clone(self.database.users_by_game[self.game][disc_id])
            user.ingame_id = [steam_id]
            user.ingame_name = [steam_name]
            users_in_current_game[disc_id] = user

        if self.active_game is not None:
            # Check if game is over
            code_retrieved = {disc_id: False for disc_id in user_dict}
            next_code = None
            for disc_id in user_dict:
                user_data = user_dict[disc_id]
                next_code = self.api_client.get_next_sharecode(
                    user_data.ingame_id[0],
                    user_data.match_auth_code[0],
                    user_data.latest_match_token[0]
                )

                if next_code is not None and next_code != user_data.latest_match_token[0]:
                    logger.info(f"New sharecode in get_active_game_info: {next_code}")
                    code_retrieved[disc_id] = True
        
            if all(code_retrieved[disc_id] for disc_id in code_retrieved):
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
                "game_mode": "CSGO",
            },
            users_in_current_game,
            None
        )

    async def get_finished_game_info(self, guild_id):
        match_id = self.active_game[guild_id]["id"]

        current_sharecodes = {
            disc_id: self.database.users_by_game[self.game][disc_id].latest_match_token[0]
            for disc_id in self.users_in_game[guild_id]
        }

        # Get new CS sharecode, if we didn't already get it when searching for active games
        code_retrieved = {disc_id: False for disc_id in current_sharecodes}
        new_sharecode = None
        game_info = None
        for disc_id in current_sharecodes:
            if self.users_in_game[guild_id][disc_id].latest_match_token[0] == current_sharecodes[disc_id]:
                # New sharecode has not been recieved for player
                user_data = self.database.users_by_game[self.game][disc_id]
                next_code = self.api_client.get_next_sharecode(
                    user_data.ingame_id[0],
                    user_data.match_auth_code[0],
                    user_data.latest_match_token[0]
                )

                logger.info(f"Match share code for '{disc_id}' was: '{user_data.latest_match_token[0]}', now: '{next_code}'")

                if next_code is not None and next_code != current_sharecodes[disc_id]:
                    code_retrieved[disc_id] = True
                    if new_sharecode is None:
                        new_sharecode = next_code
            else:
                logger.info(f"User '{disc_id}' already has a new sharecode saved from earlier.")
                new_sharecode = self.users_in_game[guild_id][disc_id].latest_match_token[0]

            await asyncio.sleep(2)

        if not all(code_retrieved[disc_id] for disc_id in code_retrieved):
            logger.bind(game_id=match_id, sharecodes=list(current_sharecodes.values()), guild_id=guild_id).error(
                "Next match sharecode STILL not received for everyone after game ended! Saving to missing games..."
            )
            status_code = self.POSTGAME_STATUS_MISSING

        else:
            game_info = self.api_client.get_game_details(new_sharecode)
            if game_info is None:
                raise ValueError("Could not get game_info for some reason!")

            # Define a value that determines whether the played game was (most likely) a CS2 match
            last_round = game_info["matches"][0]["roundstatsall"][-1]
            max_rounds = max(last_round["teamScores"])
            map_id = self.api_client.get_map_id(last_round["reservation"].get("gameType"))

            cs2 = (game_info["demo_parse_status"] == "error") and (max_rounds == 13 or all(score == 15 for score in last_round["teamScores"]))

            if self.database.game_exists(self.game, game_info["matchID"]):
                status_code = self.POSTGAME_STATUS_DUPLICATE
                logger.warning(
                    "We triggered end of game stuff again... Strange!"
                )

            elif len(self.users_in_game.get(guild_id, [])) == 1:
                status_code = self.POSTGAME_STATUS_SOLO

            elif max_rounds < 10:
                # Game was a short match
                status_code = self.POSTGAME_STATUS_SHORT_MATCH

            elif cs2:
                # Game was (presumably) a CS2 game
                status_code = self.POSTGAME_STATUS_CS2

            elif last_round["matchDuration"] < self.min_game_minutes * 60:
                # Game was too short to count. Probably an early surrender.
                status_code = self.POSTGAME_STATUS_SURRENDER

            else:
                status_code = self.POSTGAME_STATUS_OK

        return game_info, status_code
