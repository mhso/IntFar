import asyncio
from time import time
import httpx
from abc import abstractmethod
from typing import Any, Coroutine, Dict, Generic, Tuple, TypeVar
from datetime import datetime

from mhooge_flask.logging import logger

from intfar.api.user import User
from intfar.api.meta_database import MetaDatabase
from intfar.api.game_database import GameDatabase
from mhooge_flask.database import DBException
from intfar.api.config import Config
from intfar.api.game_data import get_stat_parser
from intfar.api.game_stats import PostGameStats, GameStatsType, PlayerStatsType
from intfar.api.awards import AwardQualifiers, get_awards_handler
from intfar.api.game_api_client import GameAPIClient
from intfar.api.util import get_website_link, GUILD_ABBREVIATIONS, SUPPORTED_GAMES

GameDatabaseType = TypeVar("GameDatabaseType", bound=GameDatabase)
GameAPIType = TypeVar("GameAPIType", bound=GameAPIClient)

class GameMonitor(Generic[GameDatabaseType, GameAPIType, GameStatsType, PlayerStatsType]):
    GAME_STATUS_NOCHANGE = 0
    GAME_STATUS_ACTIVE = 1
    GAME_STATUS_ENDED = 2
    POSTGAME_STATUS_ERROR = -1
    POSTGAME_STATUS_OK = 0
    POSTGAME_STATUS_SOLO = 1
    POSTGAME_STATUS_DUPLICATE = 2
    POSTGAME_STATUS_MISSING = 3
    POSTGAME_STATUS_TOO_SHORT = 4

    def __init__(
        self,
        game: str,
        config: Config,
        meta_database: MetaDatabase,
        game_database: GameDatabaseType,
        api_client: GameAPIType,
        game_over_callback: Coroutine | None = None
    ):
        """
        Initialize the game monitor. This class handles the logic of polling for
        games to see if any users registered to Int-Far are playing a game or is done with one.

        :param config:              Config instance that holds all the configuration
                                    options for Int-Far
        :param database:            GameDatabase instance that handles the logic
                                    of interacting with the sqlite database
        :param api_client:          GameAPICLient instance that handles the logic of
                                    communicating with the game's API
        :param game_over_callback:  asyncio Coroutine called when a game is finished
        """
        self.game = game
        self.config = config
        self.meta_database = meta_database
        self.game_database = game_database
        self.api_client = api_client
        self.game_over_callback  = game_over_callback

        self.polling_stop_delay: int = 0
        self.polling_active: Dict[int, bool] = {}
        self.active_game: Dict[int, dict] = {}
        self.users_in_game: Dict[int, Dict[int, User]] = {}
        self.users_in_voice: Dict[int, Dict[int, User]] = {}
        self.polling_tasks: Dict[int, asyncio.Task] = {}
        self.remove_user_task: Dict[int, Dict[int, asyncio.Task]] = {}

    @property
    def polling_enabled(self):
        return True

    @property
    def min_game_minutes(self):
        """
        Minimum amount of minutes for a game to be valid.
        """
        return 5

    @abstractmethod
    async def get_active_game_info(self, guild_id: int):
        ...

    @abstractmethod
    async def get_finished_game_info(self, guild_id: int) -> tuple[Dict, int]:
        ...

    @abstractmethod
    def get_users_in_game(self, user_dict: Dict[int, User], raw_game_data: Dict) -> Dict[int, User]:
        ...

    def is_status_error(self, status_code: int):
        return status_code == self.POSTGAME_STATUS_ERROR

    async def check_game_status(self, guild_id: int) -> int:
        """
        Check whether people that are active in voice channels are currently in a game.
        Returns a status code that can be one of:
         - GameMonitor.GAME_STATUS_NOCHANGE (0):    No change since we last checked
         - GameMonitor.GAME_STATUS_ACTIVE   (1):    A new game has begun
         - GameMonitor.GAME_STATUS_ENDED    (2):    Game is now over

        :param guild_id:    ID of the Discord server where the game took place
        """
        active_game_info, users_in_current_game, status = await self.get_active_game_info(guild_id)

        if active_game_info is not None and self.active_game.get(guild_id) is None:
            if active_game_info["start"] == 0:
                active_game_info["start"] = int(time())

            active_game_info["game_guild_name"] = GUILD_ABBREVIATIONS.get(guild_id, "Unknown Server")

            self.active_game[guild_id] = active_game_info
            self.users_in_game[guild_id] = users_in_current_game
            logger.debug(f"Game start for {self.game}: {datetime.fromtimestamp(self.active_game[guild_id]['start'])}")

            if status is not None:
                return status

            return self.GAME_STATUS_ACTIVE # Game is now active.

        if active_game_info is None and self.active_game.get(guild_id) is not None:
            return self.GAME_STATUS_ENDED # Game is over.

        return self.GAME_STATUS_NOCHANGE

    async def poll_for_new_game(self, guild_id: int, immediately: bool = False):
        """
        Periodically poll the API for the relevant game to check if any users in
        Discord voice channels have joined a game. Whenever that happens, we instead
        switch to periodically polling for the game to end.

        :param guild_id:    ID of the Discord server where we should poll for a game
        :param immediately: Whether to start polling immediately, or sleep for a bit first
        """
        while True:
            if not immediately:
                try:
                    await asyncio.sleep(self.config.status_interval_dormant)
                except KeyboardInterrupt:
                    self.polling_active[guild_id] = False
                    return

            immediately = False

            if not self.polling_active.get(guild_id, False): # Stop if people leave voice channels.
                return

            try:
                game_status = await self.check_game_status(guild_id)
            except Exception:
                bound_logger = logger.bind(event="game_status_error", game=self.game, guild_id=guild_id)
                bound_logger.exception(f"Error when getting status for {self.game}")
                game_status = self.GAME_STATUS_NOCHANGE

            # If we can't track active games for a given game,
            # the status might go from no game to game ended immediately
            if game_status == self.GAME_STATUS_NOCHANGE: # Sleep for a bit and check game status again.
                continue

            if game_status == self.GAME_STATUS_ACTIVE: # Game has started.
                # Send update to Int-Far website that a game has started.
                req_data = {
                    "secret": self.config.discord_token,
                    "guild_id": guild_id
                }
                req_data.update(self.active_game[guild_id])
                self._send_game_update("game_started", self.game, req_data)

                bound_logger = logger.bind(
                    event="game_start",
                    game=self.game,
                    guild_id=guild_id,
                    users_in_game=self.users_in_game,
                    users_in_voice=self.users_in_voice
                )
                bound_logger.info(f"Game of {self.game} is now active in guild with ID {guild_id}, polling for game end...")

                await self.poll_for_game_end(guild_id)

            elif game_status == self.GAME_STATUS_ENDED:
                await self.on_game_end(guild_id)

    def get_finished_game_status(self, game_info: Dict[str, Any], guild_id: int):
        if self.game_database.game_exists(game_info["gameId"]):
            logger.warning("We triggered end of game stuff again... Strange!")
            return self.POSTGAME_STATUS_DUPLICATE

        if len(self.users_in_game.get(guild_id, [])) == 1:
            return self.POSTGAME_STATUS_SOLO

        return None

    async def _get_finished_game_and_status(self, game_id: str, guild_id: int):
        game_info = await self.api_client.get_game_details(game_id)

        if game_info is None:
            return None, self.POSTGAME_STATUS_ERROR

        status = self.get_finished_game_status(game_info, guild_id)

        return game_info, status

    async def try_get_finished_game_info(self, game_id: str, guild_id: int, retries=5, start_sleep=30, sleep_delta=10):
        """
        Try to get game details from game API client. If this fails, retry the specified
        amount of times, sleeping inbetween.
        """
        game_info, status = await self._get_finished_game_and_status(game_id, guild_id)
        if status in (self.POSTGAME_STATUS_DUPLICATE, self.POSTGAME_STATUS_SOLO, self.POSTGAME_STATUS_TOO_SHORT):
            return game_info, status

        retry = 0
        retries = 5
        time_to_sleep = start_sleep
        while (game_info is None or self.is_status_error(status)) and retry < retries:
            logger.warning(
                f"Game info is None! Retrying in {time_to_sleep} secs..."
            )

            await asyncio.sleep(time_to_sleep)
            time_to_sleep += sleep_delta

            game_info, status = await self._get_finished_game_and_status(game_id, guild_id)
            if status in (self.POSTGAME_STATUS_DUPLICATE, self.POSTGAME_STATUS_SOLO, self.POSTGAME_STATUS_TOO_SHORT):
                return game_info, status

            retry += 1

        return game_info, status

    def get_intfar_data(self, awards_handler: AwardQualifiers[GameAPIType, GameStatsType, PlayerStatsType]):
        intfar_data = awards_handler.get_intfar()
        intfar_id = intfar_data[0]
        intfar_reasons = intfar_data[1]

        reason_ids = ["0"] * len(awards_handler.INTFAR_REASONS())
        reasons_list = list(awards_handler.INTFAR_REASONS())

        if intfar_reasons is None:
            reasons_str = None
        else:
            for stat, _ in intfar_reasons:
                reason_ids[reasons_list.index(stat)] = "1"

            reasons_str = "".join(reason_ids)

        awards_handler.parsed_game_stats.intfar_id = intfar_id
        awards_handler.parsed_game_stats.intfar_reason = reasons_str

        return intfar_data, self.game_database.get_current_intfar_streak()

    def get_doinks_data(self, awards_handler: AwardQualifiers[GameAPIType, GameStatsType, PlayerStatsType]):
        doinks_mentions, doinks = awards_handler.get_big_doinks()
        for stats in awards_handler.parsed_game_stats.filtered_player_stats:
            stats.doinks = doinks.get(stats.disc_id)

        return doinks_mentions, doinks

    def get_ranks_data(self, awards_handler: AwardQualifiers[GameAPIType, GameStatsType, PlayerStatsType]):
        prev_ranks = {
            stats.disc_id: self.game_database.get_current_rank(stats.player_id)
            for stats in awards_handler.parsed_game_stats.filtered_player_stats
        }
        return awards_handler.get_rank_mentions(prev_ranks)

    def get_winstreak_data(self, parsed_game_stats: GameStatsType):
        active_streaks = {}
        broken_streaks = {}
        game_result = parsed_game_stats.win
        opposite = -game_result

        for stats in parsed_game_stats.filtered_player_stats:
            disc_id = stats.disc_id

            current_streak = self.game_database.get_current_win_or_loss_streak(disc_id, game_result)
            prev_streak = self.game_database.get_current_win_or_loss_streak(disc_id, opposite) - 1

            if current_streak >= self.config.stats_min_win_loss_streak:
                # We are currently on a win/loss streak
                streak_list = active_streaks.get(current_streak, [])
                streak_list.append(disc_id)
                active_streaks[current_streak] = streak_list

            elif prev_streak >= self.config.stats_min_win_loss_streak:
                # We broke a win/loss streak
                streak_list = broken_streaks.get(prev_streak, [])
                streak_list.append(disc_id)
                broken_streaks[prev_streak] = streak_list

        return active_streaks, broken_streaks

    def get_cool_timeline_data(self, awards_handler: AwardQualifiers[GameAPIType, GameStatsType, PlayerStatsType]):
        return awards_handler.get_cool_timeline_events()

    def get_cool_stats_data(self, awards_handler: AwardQualifiers[GameAPIType, GameStatsType, PlayerStatsType]):
        return awards_handler.get_cool_stats()

    def save_stats(self, parsed_game_stats: GameStatsType):
        (
            global_best_records,
            global_worst_records,
            player_best_records,
            player_worst_records
        ) = self.game_database.save_stats(parsed_game_stats)

        # Create backup of databases
        self.meta_database.create_backup()
        self.game_database.create_backup()
        logger.info("Game over! Stats were saved succesfully.")

        return global_best_records, global_worst_records, player_best_records, player_worst_records

    def get_lifetime_stats_data(self, awards_handler: AwardQualifiers[GameAPIType, GameStatsType, PlayerStatsType]):
        return awards_handler.get_lifetime_stats(self.game_database)

    async def get_parsed_stats(self, game_info: Dict[str, Any], guild_id: int) -> GameStatsType | None:
        try: # Get formatted stats that are relevant for the players in the game.
            stat_parser = get_stat_parser(self.game, game_info, self.api_client, self.game_database.game_users, guild_id)
            return stat_parser.parse_data()
        except Exception:
            # Game data was not formatted correctly for some reason (Rito/Volvo pls).
            logger.bind(event="parse_stats_error", game_id=game_info["gameId"]).exception("Error when parsing game data!")
            return None

    async def get_post_game_data(self, game_info: Dict[str, Any], status_code: int, guild_id: int) -> Tuple[PostGameStats[GameStatsType, PlayerStatsType] | None, int]:
        # Update users in game based on game data
        logger.bind(event="user_in_game_before", users=self.users_in_game[guild_id]).info(f"Users in game before: {self.users_in_game[guild_id]}")
        self.users_in_game[guild_id] = self.get_users_in_game(self.game_database.game_users, game_info)
        if len(self.users_in_game[guild_id]) <= 1:
            return None, self.POSTGAME_STATUS_SOLO
    
        # Get formatted stats that are relevant for the players in the game.
        parsed_game_stats = await self.get_parsed_stats(game_info, guild_id)

        if parsed_game_stats is None:
            return None, self.POSTGAME_STATUS_ERROR

        logger.bind(event="user_in_game_after", users=self.users_in_game[guild_id]).info(f"Users in game after: {self.users_in_game[guild_id]}")

        # Get class for handling award qualifiers for the current game
        awards_handler = get_awards_handler(self.game, self.config, self.api_client, parsed_game_stats)

        # Int-Far data
        intfar_data, intfar_streak_data = self.get_intfar_data(awards_handler)

        # Doinks data
        doinks_data = self.get_doinks_data(awards_handler)

        # Ranks data
        ranks_mentions = self.get_ranks_data(awards_handler)

        # Winstreak data
        winstreak_data = self.get_winstreak_data(parsed_game_stats)

        # Timeline data
        timeline_mentions = self.get_cool_timeline_data(awards_handler)

        # Misc cool data
        cool_stats_data = self.get_cool_stats_data(awards_handler)

        # Save stats to database
        try:
            beaten_records_data = self.save_stats(parsed_game_stats)

            # Lifetime data
            lifetime_data = self.get_lifetime_stats_data(awards_handler)

        except DBException:
            # Log error along with relevant variables.
            logger.bind(
                event="save_data_error",
                game_id=game_info["gameId"],
                intfar_id=parsed_game_stats.intfar_id,
                intfar_reason=parsed_game_stats.intfar_reason,
                doinks=[player_stats.doinks for player_stats in parsed_game_stats.filtered_player_stats],
                guild_id=guild_id
            ).exception("Game stats could not be saved!")
    
            self.game_database.save_missed_game(game_info["gameId"], guild_id, int(time()))

            beaten_records_data = None
            lifetime_data = None

        return (
            PostGameStats(
                self.game,
                status_code,
                guild_id,
                parsed_game_stats,
                intfar_data,
                intfar_streak_data,
                doinks_data,
                ranks_mentions,
                winstreak_data,
                timeline_mentions,
                cool_stats_data,
                beaten_records_data,
                lifetime_data,
            ),
            self.POSTGAME_STATUS_OK
        )

    async def handle_game_over(self, game_info: Dict[str, Any], status_code: int, guild_id: int) -> PostGameStats[GameStatsType, PlayerStatsType] | None:
        """
        Called when a game is over. Combines all the necessary post game data
        into one object that is returned and passed to any listeners via a callback.
        """
        if status_code in (self.POSTGAME_STATUS_ERROR, self.POSTGAME_STATUS_MISSING) and game_info["gameId"] is not None:
            self.game_database.save_missed_game(game_info["gameId"], guild_id, int(time()))

        post_game_data = None
        if status_code == self.POSTGAME_STATUS_OK:
            with self.game_database:
               post_game_data, status_code = await self.get_post_game_data(game_info, status_code, guild_id)

        if post_game_data is None:
            post_game_data = PostGameStats(self.game, status_code, guild_id)

        return post_game_data

    async def on_game_end(self, guild_id: int):
        game_id = None
        try:
            game_id = self.active_game.get(guild_id, {}).get("id")
            logger.bind(event="game_over", game=self.game).info(f"GAME OVER! Active game: {game_id}")

            game_info, status_code = await self.get_finished_game_info(guild_id)

        except Exception:
            # Something went wrong when doing end-of-game stuff
            bound_logger = logger.bind(event="game_over_error", game=self.game, guild_id=guild_id, game_id=game_id)
            bound_logger.exception("Exception after game was over!!!")

            game_info = {"gameId": game_id}
            status_code = self.POSTGAME_STATUS_ERROR

        finally:
            # Send update to Int-Far website that the game is over.
            req_data = {
                "secret": self.config.discord_token,
                "guild_id": guild_id,
                "game_id": game_id
            }
            self._send_game_update("game_ended", self.game, req_data)

            logger.info(f"Game status: {status_code}")

            post_game_data = await self.handle_game_over(game_info, status_code, guild_id)
            if self.game_over_callback is not None:
                await self.game_over_callback(post_game_data)

            del self.active_game[guild_id]
            del self.users_in_game[guild_id] # Reset the list of users who are in a game.

    async def poll_for_game_end(self, guild_id: int):
        """
        When users are detected in an active game, this method polls the relevant API
        to check when the game has ended. When this is detected,
        data is saved and the 'self.game_over_callback' method is called.

        :param guild_id:    ID of the Discord server where we should poll
                            for the end of the game
        """
        while True:
            try:
                logger.info(f"Polling for {self.game} game end...")
                await asyncio.sleep(self.config.status_interval_ingame)

            except KeyboardInterrupt:
                return

            game_status = await self.check_game_status(guild_id)
            if game_status == self.GAME_STATUS_NOCHANGE:
                continue

            if game_status == self.GAME_STATUS_ENDED: # Game is over.
                await self.on_game_end(guild_id)

            break

    async def stop_polling(self, guild_id):
        self.polling_active[guild_id] = False
        logger.info(f"Stopping polling of '{self.game}'.")

    def should_stop_polling(self, guild_id):
        return len(self.users_in_voice.get(guild_id, [])) < 2 and self.polling_active.get(guild_id, False)

    def should_poll(self, guild_id):
        return self.polling_enabled and len(self.users_in_voice.get(guild_id, [])) > 1 and not self.polling_active.get(guild_id, False)

    def _print_task_result(self, task: asyncio.Task,  guild_id: int):
        bound_logger = logger.bind(game=self.game, guild_id=guild_id)
        try:
            task.result()
            bound_logger.info("Polling task ended successfully.")
        except asyncio.CancelledError:
            bound_logger.info("Polling task was cancelled.")
        except asyncio.InvalidStateError:
            bound_logger.info("Polling task is not yet done.")
        except Exception:
            bound_logger.exception("Exception in polling task!")

    def add_user_in_voice_channel(self, user: User, guild_id: int, poll_immediately: bool = False):
        if guild_id not in self.users_in_voice:
            self.users_in_voice[guild_id] = {}

        self.users_in_voice[guild_id][user.disc_id] = user

        if self.remove_user_task.get(guild_id, {}).get(user.disc_id):
            self.remove_user_task[guild_id][user.disc_id].cancel()

        if self.should_poll(guild_id):
            bound_logger = logger.bind(event="poll_start", game=self.game, guild_id=guild_id)
            bound_logger.info(f"People are active in guild with ID {guild_id}! Polling for games for {SUPPORTED_GAMES[self.game]}...")

            self.polling_active[guild_id] = True
            polling_task = asyncio.create_task(self.poll_for_new_game(guild_id, poll_immediately))
            polling_task.add_done_callback(lambda t: self._print_task_result(t, guild_id))
            self.polling_tasks[guild_id] = polling_task

    async def _remove_user(self, user: User, guild_id: int):
        logger.info(f"Removing user '{user.player_name[0]}' in '{self.game}' now")
        del self.users_in_voice[guild_id][user.disc_id]

        if guild_id in self.remove_user_task and user.disc_id in self.remove_user_task[guild_id]:
           del self.remove_user_task[guild_id][user.disc_id]

        if self.should_stop_polling(guild_id):
            task = self.polling_tasks[guild_id]
            await self.stop_polling(guild_id)
            self._print_task_result(task, guild_id)

    async def _remove_user_after_delay(self, user: User, guild_id: int):
        await asyncio.sleep(self.polling_stop_delay)
        await self._remove_user(user, guild_id)

    async def remove_user_from_voice_channel(self, user: User, guild_id: int):
        if self.polling_stop_delay == 0:
            await self._remove_user(user, guild_id)
        elif not self.remove_user_task.get(guild_id, {}).get(user.disc_id):
            if guild_id not in self.remove_user_task:
                self.remove_user_task[guild_id] = {}

            logger.info(f"Removing user '{user.player_name[0]}' in '{self.game}' after {self.polling_stop_delay} seconds...")
            self.remove_user_task[guild_id][user.disc_id] = asyncio.create_task(self._remove_user_after_delay(user, guild_id))    

    def _send_game_update(self, endpoint, game, data):
        try:
            base_url = get_website_link(game)
            return httpx.post(f"{base_url}/{endpoint}", data=data)
        except httpx.RequestError:
            logger.bind(endpoint=endpoint, data=data).exception(f"Error ignored in send_game_update for {self.game}")
