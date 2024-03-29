from typing import Coroutine
import asyncio

from mhooge_flask.logging import logger

from api.game_monitor import GameMonitor
from api.game_database import GameDatabase
from api.user import User
from api.game_apis.lol import RiotAPIClient
from api.config import Config
from api.game_data.lol import get_player_stats

class LoLGameMonitor(GameMonitor):
    POSTGAME_STATUS_CUSTOM_GAME = 4
    POSTGAME_STATUS_URF = 5
    POSTGAME_STATUS_NOT_SR = 6
    POSTGAME_STATUS_REMAKE = 7

    def __init__(self, game: str, config: Config, database: GameDatabase, game_over_callback: Coroutine, api_client: RiotAPIClient):
        super().__init__(game, config, database, game_over_callback, api_client)

    def get_users_in_game(self, user_dict: dict[int, User], game_data: dict):
        users_in_game = {}
        for disc_id in user_dict:
            summ_ids = user_dict[disc_id].ingame_id
            player_stats = get_player_stats(game_data, summ_ids)
            if player_stats is not None:
                users_in_game[disc_id] = User(
                    disc_id,
                    user_dict[disc_id].secret,
                    [player_stats["summonerName"]],
                    [player_stats["summonerId"]],
                    champ_id=player_stats["championId"]
                )

        return users_in_game

    async def get_active_game_info(self, guild_id):
        # First check if users are in the same game (or all are in no games).
        user_dict = (
            self.users_in_voice.get(guild_id, {})
            if self.users_in_game.get(guild_id) is None
            else self.users_in_game[guild_id]
        )

        active_game = None
        active_game_start = None
        active_game_team = None
        game_ids = set()
        users_in_current_game = {}

        for disc_id in user_dict:
            summ_ids = user_dict[disc_id].ingame_id
            game_for_summoner = None

            # Check if any of the summ_names/summ_ids for a given player is in a game.
            for summ_id in summ_ids:
                game_data = self.api_client.get_active_game(summ_id)
                if game_data is not None:
                    game_start = int(game_data["gameStartTime"]) / 1000
                    active_game_start = game_start
                    game_for_summoner = game_data
                    break

                await asyncio.sleep(1)

            if game_for_summoner is not None: # We found a game for the current player
                player_stats = get_player_stats(game_for_summoner, summ_ids)
                game_ids.add(game_for_summoner["gameId"])
                active_game_team = player_stats["teamId"]
                active_game = game_for_summoner

                users_in_current_game.update(self.get_users_in_game(user_dict, game_for_summoner))

        if len(game_ids) > 1: # People are in different games.
            return None, users_in_current_game, self.GAME_STATUS_NOCHANGE

        if active_game is None:
            return None, users_in_current_game, None

        enemy_champ_ids = []
        for participant in active_game["participants"]:
            if participant["teamId"] != active_game_team:
                enemy_champ_ids.append(participant["championId"])

        return (
            {
                "id": active_game["gameId"],
                "start": active_game_start,
                "team_id": active_game_team,
                "enemy_champ_ids": enemy_champ_ids,
                "map_id": active_game["mapId"],
                "map_name": self.api_client.get_map_name(active_game["mapId"]),
                "game_type": active_game["gameType"],
                "game_mode": active_game["gameMode"],
            },
            users_in_current_game,
            None
        )

    async def get_finished_game_status(self, game_info: dict, guild_id: int):
        if self.database.game_exists(game_info["gameId"]):
            logger.warning(
                "We triggered end of game stuff again... Strange!"
            )
            return self.POSTGAME_STATUS_DUPLICATE

        if len(self.users_in_game.get(guild_id, [])) == 1:
            return self.POSTGAME_STATUS_SOLO

        if self.api_client.is_urf(game_info["gameMode"]):
            # Gamemode was URF.
            return self.POSTGAME_STATUS_URF

        if not self.api_client.map_is_sr(game_info["mapId"]):
            # Game is not on summoners rift.
            return self.POSTGAME_STATUS_NOT_SR

        if game_info["gameDuration"] < self.min_game_minutes * 60:
            # Game was too short to count. Probably a remake.
            return self.POSTGAME_STATUS_REMAKE

        self.active_game[guild_id]["queue_id"] = game_info["queueId"]
        return self.POSTGAME_STATUS_OK

    async def get_finished_game_info(self, guild_id):
        game_id = self.active_game[guild_id]["id"]

        logger.bind(event="game_over", game="lol").info(f"GAME OVER! Active game: {game_id}")

        # Check if game was a custom game, if so don't save stats.
        custom_game = self.active_game[guild_id].get("game_type", "") == "CUSTOM_GAME"

        game_info = None
        if not custom_game:
            game_info = self.api_client.get_game_details(game_id, tries=2)

            retry = 0
            retries = 5
            time_to_sleep = 30
            while game_info is None and retry < retries:
                logger.warning(
                    f"Game info is None! Retrying in {time_to_sleep} secs..."
                )

                await asyncio.sleep(time_to_sleep)
                time_to_sleep += 10
                game_info = self.api_client.get_game_details(game_id)
                retry += 1

        if custom_game: # Do nothing.
            logger.info(f"Game was a custom game: {game_id}")
            status_code = self.POSTGAME_STATUS_CUSTOM_GAME

        elif game_info is None: # Game info is still None after 3 retries.
            # Log error
            logger.bind(game_id=game_id, guild_id=guild_id).error(
                "Game info is STILL None after 3 retries! Saving to missing games..."
            )
            game_info = {"gameId": game_id}
            status_code = self.POSTGAME_STATUS_MISSING

        else:
            status_code = await self.get_finished_game_status(game_info, guild_id)

        return game_info, status_code
