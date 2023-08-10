import asyncio
from time import time
import requests
from abc import ABC, abstractmethod
from typing import Coroutine
from datetime import datetime

from mhooge_flask.logging import logger

from api.database import Database, User
from api.config import Config

class GameMonitor(ABC):
    GAME_STATUS_NOCHANGE = 0
    GAME_STATUS_ACTIVE = 1
    GAME_STATUS_ENDED = 2
    POSTGAME_STATUS_ERROR = -1
    POSTGAME_STATUS_OK = 0

    def __init__(self, config: Config, database: Database, game: str, game_over_callback: Coroutine):
        """
        Initialize the game monitor. This class handles the logic of polling for
        games to see if any users registered to Int-Far are playing a game or is done with one.

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
        self.game = game
        self.game_over_callback  = game_over_callback

        self.polling_active: dict[int, bool] = {}
        self.active_game: dict[int, dict] = {}
        self.users_in_game: dict[int, dict[int, User]] = {}
        self.users_in_voice: dict[int, dict[int, User]] = {}

    @abstractmethod
    async def get_active_game_info(self, guild_id):
        ...

    @abstractmethod
    async def get_finished_game_info(self, guild_id):
        ...

    async def check_game_status(self, guild_id: int, guild_name: str) -> int:
        """
        Check whether people that are active in voice channels are currently in a game.
        Returns a status code that can be one of:
         - GameMonitor.GAME_STATUS_NOCHANGE (0):    No change since we last checked
         - GameMonitor.GAME_STATUS_ACTIVE   (1):    A new game has begun
         - GameMonitor.GAME_STATUS_ENDED    (2):    Game is now over

        :param guild_id:    ID of the Discord server where the game took place
        :param guild_name:  Name of the Discord server where the game took place
        """
        active_game_info, users_in_current_game, status = await self.get_active_game_info(guild_id)

        if status is not None:
            return status

        if active_game_info is not None and self.active_game.get(guild_id) is None:
            if active_game_info["start"] == 0:
                active_game_info["start"] = int(time())

            active_game_info["game_guild_name"] = guild_name

            logger.debug(f"Game start for {self.game}: {datetime.fromtimestamp(self.active_game[guild_id]['start'])}")
            self.active_game[guild_id] = active_game_info
            self.users_in_game[guild_id] = users_in_current_game

            return self.GAME_STATUS_ACTIVE # Game is now active.

        if active_game_info is None and self.active_game.get(guild_id) is not None:
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
        logger.info(f"People are active in {guild_name}! Polling for games for {self.game}...")

        if not immediately:
            try:
                while time_slept < self.config.status_interval_dormant:
                    if not self.polling_active.get(guild_id, False): # Stop if people leave voice channels.
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
                "game": self.game,
                "guild_id": guild_id
            }
            req_data.update(self.active_game[guild_id])
            self._send_game_update("game_started", req_data)

            logger.info(f"Game of {self.game} is now active in {guild_name}, polling for game end...")

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
        logger.info(f"Polling for {self.game} game end...")
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
                game_info, status_code = await self.get_finished_game_info(guild_id)

                # Print who was in the game, for sanity checks.
                logger.debug(f"Users in game before: {self.users_in_game.get(guild_id)}")

                # Send update to Int-Far website that the game is over.
                req_data = {
                    "secret": self.config.discord_token,
                    "game": self.game,
                    "guild_id": guild_id,
                    "game_id": game_id
                }
                self._send_game_update("game_ended", req_data)

                # Call end-of-game callback
                await self.game_over_callback(game_info, guild_id, status_code)

                self.active_game[guild_id] = None
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
            logger.bind(endpoint=endpoint, data=data).exception(f"Error ignored in send_game_update for {self.game}")
