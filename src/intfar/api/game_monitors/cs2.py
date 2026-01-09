import asyncio
from time import time
from typing import Dict

from mhooge_flask.logging import logger

from intfar.api.user import User
from intfar.api.game_monitor import GameMonitor
from intfar.api.game_apis.cs2 import SteamAPIClient
from intfar.api.game_data.cs2 import CS2GameStats, CS2PlayerStats
from intfar.api.game_databases.cs2 import CS2GameDatabase

class CS2GameMonitor(GameMonitor[CS2GameDatabase, SteamAPIClient, CS2GameStats, CS2PlayerStats]):
    POSTGAME_STATUS_CUSTOM_GAME = 4
    POSTGAME_STATUS_DEMO_MISSING = 5
    POSTGAME_STATUS_DEMO_MALFORMED = 6

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
                curr_code = await self.api_client.get_next_sharecode(
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

    def get_users_in_game(self, user_dict: dict[int, User], raw_game_data: dict):
        users_in_game = {}
        round_stats = raw_game_data["matches"][0]["roundstatsall"]

        max_player_round = 0
        max_players = 0
        for index, round_data in enumerate(round_stats):
            players_in_round = len(round_data["reservation"]["accountIds"])
            if players_in_round > max_players:
                max_players = players_in_round
                max_player_round = index

        for disc_id in user_dict.keys():
            for steam_id in user_dict[disc_id].player_id:
                account_id = self.api_client.get_account_id(steam_id)
                if account_id in round_stats[max_player_round]["reservation"]["accountIds"]:
                    users_in_game[disc_id] = user_dict[disc_id]
                    break

        return users_in_game

    async def get_active_game_info(self, guild_id: int):
        # Create a bunch of maps for different ID representations
        user_dict: Dict[int, User] = (
            self.users_in_voice.get(guild_id, {})
            if self.users_in_game.get(guild_id) is None
            else self.users_in_game[guild_id]
        )

        steam_id_map = {}
        for disc_id in user_dict:
            for steam_id in user_dict[disc_id].player_id:
                steam_id_map[str(steam_id)] = disc_id

        active_users = []
        for steam_id in steam_id_map:  
            in_game = await self.api_client.is_person_ingame(steam_id)
            if in_game or (in_game is None and steam_id_map[steam_id] in user_dict):
                active_users.append(steam_id)
                await asyncio.sleep(5)

        users_in_current_game = {}

        if active_users == []:
            return None, users_in_current_game, None # No active users

        # Gather data about users in the game
        for steam_id in active_users:
            disc_id = steam_id_map[steam_id]
            if self.active_game.get(guild_id) is None: # First time we see this active game
                steam_name = await self.api_client.get_player_name(steam_id)
            else:
                steam_name = user_dict[disc_id].player_name[0]

            user = User.clone(self.game_database.game_users[disc_id])
            user["player_id"] = [steam_id]
            user["player_name"] = [steam_name]
            user["latest_match_token"] = [self.game_database.get_latest_sharecode(steam_id)]
            users_in_current_game[disc_id] = user

        if self.active_game.get(guild_id) is not None:
            # Check if game is over
            next_code = await self._get_next_sharecode(users_in_current_game)

            if next_code is not None:
                # New sharecodes recieved for all players. Game is over!
                for disc_id in users_in_current_game:
                    self.users_in_game[guild_id][disc_id].latest_match_token[0] = next_code

                return None, users_in_current_game, None

        return (
            {
                "id": str(time()),
                "start": 0,
                "map_id": "Unknown",
                "map_name": "Unknown",
                "game_type": "Premier",
                "game_mode": "CS2",
            },
            users_in_current_game,
            None
        )

    def get_finished_game_status(self, game_info: dict, guild_id: int):
        status = super().get_finished_game_status(game_info, guild_id)

        if status is not None:
            return status

        last_round = game_info["matches"][0]["roundstatsall"][-1]

        if last_round["matchDuration"] < self.min_game_minutes * 60:
            # Game was too short to count. Probably an early surrender.
            return self.POSTGAME_STATUS_TOO_SHORT

        if game_info["demo_parse_status"] == "missing":
            # Demo was not found on Valve's servers
            return self.POSTGAME_STATUS_DEMO_MISSING

        if game_info["demo_parse_status"] == "malformed":
            return self.POSTGAME_STATUS_DEMO_MALFORMED

        return self.POSTGAME_STATUS_OK

    async def get_finished_game_info(self, guild_id: int):
        # Get users who haven't yet received a new sharecode
        users_missing = {
            disc_id: self.users_in_game[guild_id][disc_id]
            for disc_id in self.users_in_game[guild_id]
            if self.users_in_game[guild_id][disc_id].latest_match_token[0] == self.game_database.game_users[disc_id].latest_match_token[0]
        }

        # Get new CS sharecode, if we didn't already get it when searching for active games
        if users_missing != {}:
            next_code = await self._get_next_sharecode(users_missing)
        else:
            next_code = list(self.users_in_game[guild_id].values())[0].latest_match_token[0]

        logger.info(f"Users missing: {users_missing}")
        logger.info(f"Next code: {next_code}")

        if next_code is None:
            logger.bind(sharecodes=list(users_missing.values()), guild_id=guild_id).error(
                "Next match sharecode STILL not received for everyone after game ended! Saving to missing games..."
            )
            game_info = {"gameId": None}
            status_code = self.POSTGAME_STATUS_MISSING

        else:
            game_info, status_code = await self.try_get_finished_game_info(next_code, guild_id)
            if game_info is None and status_code != self.POSTGAME_STATUS_DUPLICATE:
                game_info = {"gameId": next_code}
                if status_code != self.POSTGAME_STATUS_SOLO:
                    logger.bind(game_id=next_code, guild_id=guild_id).error(
                        "Game info is STILL None after 5 retries! Saving to missing games..."
                    )
                    status_code = self.POSTGAME_STATUS_MISSING

        return game_info, status_code

    async def handle_game_over(self, game_info: dict, status_code: int, guild_id: int):
        post_game_data = await super().handle_game_over(game_info, status_code, guild_id)

        if post_game_data.status_code not in (
            self.POSTGAME_STATUS_ERROR,
            self.POSTGAME_STATUS_MISSING,
            self.POSTGAME_STATUS_DUPLICATE,
        ):
            if (
                post_game_data.status_code != self.POSTGAME_STATUS_OK
                and post_game_data.status_code != self.POSTGAME_STATUS_SOLO
            ):
                # Parse only basic stats if CS2 demo is missing or malformed
                post_game_data.parsed_game_stats = self.parse_stats(game_info, guild_id)
                self.save_stats(post_game_data.parsed_game_stats)

                post_game_data.winstreak_data = self.get_winstreak_data(post_game_data.parsed_game_stats)

            for disc_id in self.users_in_game[guild_id]:
                steam_id = self.users_in_game[guild_id][disc_id].player_id[0]
    
                self.users_in_game[guild_id][disc_id]["latest_match_token"] = [game_info["gameId"]]
                self.game_database.set_new_cs2_sharecode(disc_id, steam_id, game_info["gameId"])

        return post_game_data
