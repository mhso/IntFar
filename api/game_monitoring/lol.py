from typing import Coroutine
import asyncio

from mhooge_flask.logging import logger

from api.game_monitor import GameMonitor
from api.database import  Database, User
from api.riot_api import RiotAPIClient
from api.config import Config
from api import game_stats

class LoLGameMonitor(GameMonitor):
    POSTGAME_STATUS_CUSTOM_GAME = 1
    POSTGAME_STATUS_MISSING = 2
    POSTGAME_STATUS_DUPLICATE = 3
    POSTGAME_STATUS_SOLO = 4
    POSTGAME_STATUS_URF = 5
    POSTGAME_STATUS_NOT_SR = 6
    POSTGAME_STATUS_REMAKE = 7

    def __init__(self, config: Config, database: Database, game: str, game_over_callback: Coroutine, riot_api: RiotAPIClient):
        super().__init__(config, database, game, game_over_callback)

        self.riot_api = riot_api

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
            summ_names = user_dict[disc_id].ingame_name
            summ_ids = user_dict[disc_id].ingame_id
            game_for_summoner = None
            active_name = None
            active_id = None
            champ_id = None

            # Check if any of the summ_names/summ_ids for a given player is in a game.
            for summ_name, summ_id in zip(summ_names, summ_ids):
                game_data = self.riot_api.get_active_game(summ_id)
                if game_data is not None:
                    game_start = int(game_data["gameStartTime"]) / 1000
                    active_game_start = game_start
                    game_for_summoner = game_data
                    active_name = summ_name
                    active_id = summ_id
                    break

                await asyncio.sleep(0.5)

            if game_for_summoner is not None: # We found a game for the current player
                game_ids.add(game_for_summoner["gameId"])
                player_stats = game_stats.get_player_stats(game_for_summoner, summ_ids)
                champ_id = player_stats["championId"]
                active_game_team = player_stats["teamId"]
                users_in_current_game[disc_id] = User([active_name], [active_id], champ_id=champ_id)
                active_game = game_for_summoner

        if len(game_ids) > 1: # People are in different games.
            return None, users_in_current_game, self.GAME_STATUS_NOCHANGE

        for disc_id in users_in_current_game:
            champ_id = users_in_current_game[disc_id].champ_id
            # New champ has been released, that we don't know about.
            if self.riot_api.get_champ_name(champ_id) is None:
                logger.warning(f"Champ ID is unknown: {champ_id}")
                self.riot_api.get_latest_data() # Get latest data about champions.
                break

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
                "map_name": self.riot_api.get_map_name(active_game["mapId"]),
                "game_type": active_game["gameType"],
                "game_mode": active_game["gameMode"],
            },
            users_in_current_game,
            None
        )

    async def get_finished_game_info(self, guild_id):
        game_id = self.active_game[guild_id]["id"]

        logger.info("GAME OVER!!")
        logger.debug(f"Active game: {game_id}")

        # Check if game was a custom game, if so don't save stats.
        custom_game = self.active_game[guild_id]["game_type"] == "CUSTOM_GAME"

        game_info = None

        if not custom_game:
            game_info = self.riot_api.get_game_details(
                game_id, tries=2
            )

            retry = 0
            retries = 4
            time_to_sleep = 30
            while game_info is None and retry < retries:
                logger.warning(
                    f"Game info is None! Retrying in {time_to_sleep} secs..."
                )

                await asyncio.sleep(time_to_sleep)
                game_info = self.riot_api.get_game_details(game_id)
                retry += 1

        if custom_game: # Do nothing.
            logger.info(f"Game was a custom game: {game_id}")
            status_code = self.POSTGAME_STATUS_CUSTOM_GAME

        elif game_info is None: # Game info is still None after 3 retries.
            # Log error
            logger.bind(game_id=game_id, guild_id=guild_id).error(
                "Game info is STILL None after 3 retries! Saving to missing games..."
            )
            status_code = self.POSTGAME_STATUS_MISSING

        elif self.database.game_exists(game_info["gameId"]):
            status_code = self.POSTGAME_STATUS_DUPLICATE
            logger.warning(
                "We triggered end of game stuff again... Strange!"
            )

        elif len(self.users_in_game[guild_id]) == 1:
            status_code = self.POSTGAME_STATUS_SOLO

        elif self.riot_api.is_urf(game_info["gameMode"]):
            # Gamemode was URF.
            status_code = self.POSTGAME_STATUS_URF

        elif not self.riot_api.map_is_sr(game_info["mapId"]):
            # Game is not on summoners rift.
            status_code = self.POSTGAME_STATUS_NOT_SR

        elif game_info["gameDuration"] < self.config.min_game_minutes * 60:
            # Game was too short to count. Probably a remake.
            status_code = self.POSTGAME_STATUS_REMAKE

        else:
            status_code = self.POSTGAME_STATUS_OK

        self.active_game[guild_id]["queue_id"] = game_info["queueId"]

        return game_info, status_code
