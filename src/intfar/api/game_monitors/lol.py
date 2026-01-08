from time import time
import asyncio
from typing import Dict, List

from mhooge_flask.logging import logger

from intfar.api import lan
from intfar.api.game_monitor import GameMonitor
from intfar.api.user import User
from intfar.api.game_data.lol import get_player_stats
from intfar.api.game_apis.lol import RiotAPIClient
from intfar.api.game_databases.lol import LoLGameDatabase
from intfar.api.util import GUILD_IDS

class LoLGameMonitor(GameMonitor[LoLGameDatabase, RiotAPIClient]):
    POSTGAME_STATUS_CUSTOM_GAME = 5
    POSTGAME_STATUS_URF = 6
    POSTGAME_STATUS_INVALID_MAP = 7

    def __init__(self, game, config, meta_database, game_database, api_client, game_over_callback = None):
        super().__init__(game, config, meta_database, game_database, api_client, game_over_callback)
        self.fetch_ranks = True
        self.latest_game_timestamp: Dict[int, int] = {}
        self.latest_game_id: Dict[int, List[int]] = {}
        self._get_latest_game()

    @property
    def polling_stop_delay(self):
        return 300

    def _get_latest_game(self):
        latest_game_data = self.game_database.get_latest_game()[0]
        if latest_game_data is not None:
            latest_id = int(latest_game_data[0])
            latest_game = latest_game_data[1]

            for guild_id in GUILD_IDS:
                self.latest_game_id[guild_id] = [latest_id]
                self.latest_game_timestamp[guild_id] = latest_game

    def get_users_in_game(self, user_dict: dict[int, User], raw_game_data: dict):
        users_in_game = {}
        for disc_id in user_dict.keys():
            player_stats = get_player_stats(raw_game_data, user_dict[disc_id].player_id)
            if player_stats is not None:
                active_summ_name = None
                for puuid, summ_name in zip(user_dict[disc_id].player_id, user_dict[disc_id].player_name):
                    if puuid == player_stats["puuid"]:
                        active_summ_name = summ_name
                        break

                users_in_game[disc_id] = User(
                    disc_id,
                    user_dict[disc_id].secret,
                    [active_summ_name],
                    [player_stats["puuid"]],
                    champ_id=player_stats["championId"],
                )

        return users_in_game

    async def get_active_game_info(self, guild_id: int):
        # First check if users are in the same game (or all are in no games).
        user_dict = self.users_in_voice.get(guild_id, {})

        game_ids = {}
        for disc_id in user_dict:
            user_data = user_dict[disc_id]

            for puuid, name in zip(user_data.player_id, user_data.player_name):
                matches = await self.api_client.get_match_history(puuid, self.latest_game_timestamp[guild_id])
                await asyncio.sleep(0.5)
                matches += await self.api_client.get_match_history(puuid, self.latest_game_timestamp[guild_id], game_type="normal")

                if not matches:
                    continue

                for game_id in matches:
                    if game_id in self.latest_game_id[guild_id]:
                        continue

                    game_id_str = str(game_id)
                    if game_id_str not in game_ids:
                        game_ids[game_id_str] = []

                    game_ids[game_id_str].append(User(disc_id, user_data.secret, name, puuid))

                if game_ids != {}:
                    logger.bind(event="monitor_match_history", matches=matches).info(f"League match list for {name}: {matches}")

                await asyncio.sleep(1)

            await asyncio.sleep(2)

        elligible_game_id = None
        users_in_current_game = {}
        for game_id in game_ids:
            users_in_game = game_ids[game_id]

            if len(users_in_game) > 1 and not self.game_database.game_exists(game_id):
                elligible_game_id = game_id
                users_in_current_game = users_in_game
                break

        if elligible_game_id is None:
            return None, users_in_current_game, None

        return (
            {
                "id": elligible_game_id,
                "start": 0,
                "game_type": "MATCHED_GAME",
            },
            users_in_current_game,
            GameMonitor.GAME_STATUS_ENDED
        )

    def get_finished_game_status(self, game_info: dict, guild_id: int):
        status = super().get_finished_game_status(game_info, guild_id)

        if status is not None:
            return status

        if self.api_client.is_urf(game_info["gameMode"]):
            # Gamemode was URF.
            return self.POSTGAME_STATUS_URF

        if not self.api_client.map_is_valid(game_info["mapId"]):
            # Game is not on a valid map.
            return self.POSTGAME_STATUS_INVALID_MAP

        if game_info["gameDuration"] < self.min_game_minutes * 60:
            # Game was too short to count. Probably a remake.
            return self.POSTGAME_STATUS_TOO_SHORT

        return self.POSTGAME_STATUS_OK

    async def get_finished_game_info(self, guild_id: int):
        game_id = self.active_game[guild_id]["id"]

        # Check if game was a custom game, if so don't save stats.
        custom_game = self.active_game[guild_id].get("game_type", "") == "CUSTOM_GAME"

        game_info = None

        if custom_game: # Do nothing.
            logger.info(f"Game was a custom game: {game_id}")
            status_code = self.POSTGAME_STATUS_CUSTOM_GAME
        else:
            game_info, status_code = await self.try_get_finished_game_info(game_id, guild_id)

        if not custom_game and game_info is None and status_code == self.POSTGAME_STATUS_ERROR:
            # Game info is still None after 3 retries, log error
            logger.bind(game_id=game_id, guild_id=guild_id).error(
                "Game info is STILL None after 5 retries! Saving to missing games..."
            )
            game_info = {"gameId": game_id}
            status_code = self.POSTGAME_STATUS_MISSING

        if game_info is not None:
            timestamp = game_info.get("gameCreation")

            logger.info(f"Saving game ID and timestamp to cache: {timestamp}, {game_info.get('gameId')}")

            if timestamp is not None:
                self.latest_game_timestamp[guild_id] = int(timestamp / 1000)

            if status_code == self.POSTGAME_STATUS_OK:
                # If status is OK, we save the game to DB and don't need to cache game IDs
                self.latest_game_id[guild_id] = []

            self.latest_game_id[guild_id].append(game_info.get("gameId"))

        return game_info, status_code

    async def get_parsed_stats(self, game_info: dict, guild_id: int):
        if self.fetch_ranks:
            logger.debug("Fetching ranks for all players...")
            player_ranks = {}
            await asyncio.sleep(2)

            for disc_id in self.users_in_game[guild_id]:
                puuid = self.users_in_game[guild_id][disc_id].player_id[0]
                rank_info = await self.api_client.get_player_rank(puuid)
                if rank_info is not None:
                    player_ranks[disc_id] = rank_info

                await asyncio.sleep(1.5)

            game_info["player_ranks"] = player_ranks

        return await super().get_parsed_stats(game_info, guild_id)

    async def handle_game_over(self, game_info: dict, status_code: int, guild_id: int):
        if game_info is not None and "queueId" in game_info:
            self.active_game[guild_id]["queue_id"] = game_info["queueId"]

        post_game_data = await super().handle_game_over(game_info, status_code, guild_id)

        if post_game_data is not None and lan.is_lan_ongoing(time(), guild_id):
            lan.update_bingo_progress(self.game_database, post_game_data)

        return post_game_data
