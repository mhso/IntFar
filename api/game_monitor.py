import asyncio
import requests
from typing import Coroutine
from time import sleep, time
from datetime import datetime

from mhooge_flask.logging import logger

from api import game_stats
from api.database import  Database
from api.riot_api import RiotAPIClient
from api.config import Config

class GameMonitor:
    GAME_STATUS_NOCHANGE = 0
    GAME_STATUS_ACTIVE = 1
    GAME_STATUS_ENDED = 2
    POSTGAME_STATUS_ERROR = -1
    POSTGAME_STATUS_OK = 0
    POSTGAME_STATUS_CUSTOM_GAME = 1
    POSTGAME_STATUS_MISSING = 2
    POSTGAME_STATUS_DUPLICATE = 3
    POSTGAME_STATUS_SOLO = 4
    POSTGAME_STATUS_URF = 5
    POSTGAME_STATUS_NOT_SR = 6
    POSTGAME_STATUS_REMAKE = 7

    def __init__(self, config: Config, database: Database, riot_api: RiotAPIClient, game_over_callback: Coroutine):
        """
        Initialize the game monitor. This class handles the logic of polling for
        games where any users registered to Int-Far are playing a game or is done with one.

        :param config:              Config instance that holds all the configuration
                                    options for Int-Far
        :param database:            SQLiteDatabase instance that handles the logic
                                    of interacting with the sqlite database
        :param riot_api:            RiotAPIClient instance that handles the logic of
                                    communicating with Riot Games' LoL API
        :param game_over_callback:  asyncio Coroutine called when a game is finished
        """
        self.config = config
        self.database = database
        self.riot_api = riot_api
        self.game_over_callback  = game_over_callback

        self.polling_active = {}
        self.active_game = {}
        self.game_start = {}
        self.users_in_game = {}
        self.users_in_voice = {}

    def check_game_status(self, guild_id: int, guild_name: str) -> int:
        """
        Check whether people that are active in voice channels are currently in a game.
        Returns a status code that can be one of:
         - GameMonitor.GAME_STATUS_NOCHANGE (0):    No change since we last checked
         - GameMonitor.GAME_STATUS_ACTIVE   (1):    A new game has begun
         - GameMonitor.GAME_STATUS_ENDED    (2):    Game is now over

        :param guild_id:    ID of the Discord server where the game took place
        :param guild_name:  Name of the Discord server where the game took place
        """
        active_game = None
        active_game_start = None
        active_game_team = None
        game_ids = set()

        # First check if users are in the same game (or all are in no games).
        user_list = (
            self.users_in_voice.get(guild_id, [])
            if self.users_in_game.get(guild_id) is None
            else self.users_in_game[guild_id]
        )
        users_in_current_game = []

        for user_data in user_list:
            disc_id = user_data[0]
            summ_names = user_data[1]
            summ_ids = user_data[2]
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

                sleep(0.5)

            if game_for_summoner is not None: # We found a game for the current player
                game_ids.add(game_for_summoner["gameId"])
                player_stats = game_stats.get_player_stats(game_for_summoner, summ_ids)
                champ_id = player_stats["championId"]
                active_game_team = player_stats["teamId"]
                users_in_current_game.append((disc_id, [active_name], [active_id], champ_id))
                active_game = game_for_summoner

        if len(game_ids) > 1: # People are in different games.
            return self.GAME_STATUS_NOCHANGE

        for player_data in users_in_current_game:
            champ_id = player_data[-1]
            # New champ has been released, that we don't know about.
            if self.riot_api.get_champ_name(champ_id) is None:
                logger.warning(f"Champ ID is unknown: {champ_id}")
                self.riot_api.get_latest_data() # Get latest data about champions.
                break

        if active_game is not None and self.active_game.get(guild_id) is None:
            logger.debug(f"Game start original: {active_game_start}")
            if active_game_start == 0:
                active_game_start = int(time())

            enemy_champ_ids = []
            for participant in active_game["participants"]:
                if participant["teamId"] != active_game_team:
                    enemy_champ_ids.append(participant["championId"])

            self.active_game[guild_id] = {
                "id": active_game["gameId"],
                "start": active_game_start,
                "team_id": active_game_team,
                "enemy_champ_ids": enemy_champ_ids,
                "map_id": active_game["mapId"],
                "map_name": self.riot_api.get_map_name(active_game["mapId"]),
                "game_type": active_game["gameType"],
                "game_mode": active_game["gameMode"],
                "game_guild_name": guild_name,
            }

            self.game_start[guild_id] = active_game_start
            logger.debug(f"Game start datetime: {datetime.fromtimestamp(self.game_start[guild_id])}")
            self.users_in_game[guild_id] = users_in_current_game

            return self.GAME_STATUS_ACTIVE # Game is now active.

        if active_game is None and self.active_game.get(guild_id) is not None:
            return self.GAME_STATUS_ENDED # Game is over.

        return self.GAME_STATUS_NOCHANGE

    async def poll_for_game_start(self, guild_id: int, guild_name: str, immediately=False):
        """
        Periodically poll the Riot Games League of Legends API to check if any users in
        Discord voice channels have joined a game. Whenever that happens, we instead
        switch to periodically polling for the game to end.

        :param guild_id:    ID of the Discord server where we should poll for a game
        :param guild_name:  Name of the Discord server where we should poll for a game
        :param immediately: Whether to start polling immediately, or sleep for a bit first
        """
        self.polling_active[guild_id] = True
        time_slept = 0
        sleep_per_loop = 0.2
        logger.info(f"People are active in {guild_name}! Polling for games...")

        if not immediately:
            try:
                while time_slept < self.config.status_interval_dormant:
                    if not self.polling_active.get(guild_id, False): # Stop if people leave voice channels.
                        logger.info(f"Polling is no longer active in {guild_name}.")
                        return

                    await asyncio.sleep(sleep_per_loop)
                    time_slept += sleep_per_loop

            except KeyboardInterrupt:
                self.polling_active[guild_id] = False
                return

        game_status = self.check_game_status(guild_id, guild_name)

        if game_status == self.GAME_STATUS_ACTIVE: # Game has started.
            # Send update to Int-Far website that a game has started.
            req_data = {
                "secret": self.config.discord_token,
                "guild_id": guild_id
            }
            req_data.update(self.active_game[guild_id])
            self._send_game_update("game_started", req_data)

            logger.info(f"Game is now active in {guild_name}, polling for game end...")

            await self.poll_for_game_end(guild_id, guild_name)

        elif game_status == self.GAME_STATUS_NOCHANGE: # Sleep for a bit and check game status again.
            await self.poll_for_game_start(guild_id, guild_name)

    async def poll_for_game_end(self, guild_id, guild_name):
        """
        When users are detected in an active game, this method polls the Riot Games
        League of Legends API to check when the game is over.
        When this is detected, the 'self.game_over_callback' method is called.

        :param guild_id:    ID of the Discord server where we should poll
                            for the end of the game
        :param guild_name:  Name of the Discord server where we should poll
                            for the end of the game
        """
        logger.info("Polling for game end...")
        time_slept = 0
        sleep_per_loop = 0.2
        try:
            while time_slept < self.config.status_interval_ingame:
                await asyncio.sleep(sleep_per_loop)
                time_slept += sleep_per_loop

        except KeyboardInterrupt:
            return

        game_status = self.check_game_status(guild_id, guild_name)
        if game_status == self.GAME_STATUS_ENDED: # Game is over.
            try:
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

                # Print who was in the game, for sanity checks.
                logger.debug(f"Users in game before: {self.users_in_game.get(guild_id)}")

                # Send update to Int-Far website that the game is over.
                req_data = {
                    "secret": self.config.discord_token,
                    "guild_id": guild_id, "game_id": game_id
                }
                self._send_game_update("game_ended", req_data)

                # Call end-of-game callback
                await self.game_over_callback(game_info, guild_id, status_code)

                self.active_game[guild_id] = None
                self.game_start[guild_id] = None
                del self.users_in_game[guild_id] # Reset the list of users who are in a game.

                asyncio.create_task(self.poll_for_game_start(guild_id, guild_name))

            except Exception as e:
                # Something went wrong when doing end-of-game stuff
                game_id = self.active_game.get(guild_id, {}).get("id")

                logger.bind(game_id=game_id).exception("Exception after game was over!!!")

                await self.game_over_callback(None, guild_id, self.POSTGAME_STATUS_ERROR)

                # Re-raise exception.
                raise e

        elif game_status == self.GAME_STATUS_NOCHANGE:
            await self.poll_for_game_end(guild_id, guild_name)

    def stop_polling(self, guild_id):
        self.polling_active[guild_id] = False

    def set_users_in_voice_channels(self, users, guild_id):
        self.users_in_voice[guild_id] = users

    def should_stop_polling(self, guild_id):
        return len(self.users_in_voice.get(guild_id, [])) < 2 and self.polling_active.get(guild_id, False)

    def should_poll(self, guild_id):
        return len(self.users_in_voice.get(guild_id, [])) > 1 and not self.polling_active.get(guild_id, False)

    def _send_game_update(self, endpoint, data):
        try:
            return requests.post(f"https://mhooge.com:5000/intfar/{endpoint}", data=data)
        except requests.exceptions.RequestException:
            logger.bind(endpoint=endpoint, data=data).exception("Error ignored in send_game_update")
