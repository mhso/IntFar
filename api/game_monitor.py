import asyncio
import requests
from time import sleep, time
from datetime import datetime

from mhooge_flask.logging import logger

from api import game_stats

class GameMonitor:
    def __init__(self, config):
        self.config = config
        self.polling_active = {}

    def check_game_status(self, guild_id):
        active_game = None
        active_game_start = None
        active_game_team = None
        game_ids = set()

        # First check if users are in the same game (or all are in no games).
        user_list = (
            self.get_users_in_voice()[guild_id]
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

            if game_for_summoner is not None:
                game_ids.add(game_for_summoner["gameId"])
                player_stats = game_stats.get_player_stats(game_for_summoner, summ_ids)
                champ_id = player_stats["championId"]
                active_game_team = player_stats["teamId"]
                users_in_current_game.append((disc_id, [active_name], [active_id], champ_id))
                active_game = game_for_summoner

        if len(game_ids) > 1: # People are in different games.
            return 0

        for player_data in users_in_current_game:
            champ_id = player_data[-1]
            # New champ has been released, that we don't know about.
            if self.riot_api.get_champ_name(champ_id) is None:
                logger.warning(f"Champ ID is unknown: {champ_id}")
                self.riot_api.get_latest_data()
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
                "game_guild_name": self.get_guild_name(guild_id),
            }

            self.game_start[guild_id] = active_game_start
            logger.debug(f"Game start datetime: {datetime.fromtimestamp(self.game_start[guild_id])}")
            self.users_in_game[guild_id] = users_in_current_game

            return 1 # Game is now active.

        if active_game is None and self.active_game.get(guild_id) is not None:
            return 2 # Game is over.

        return 0

    async def poll_for_game_start(self, guild_id, guild_name, immediately=False):
            self.polling_active[guild_id] = True
            time_slept = 0
            sleep_per_loop = 0.2
            logger.info(f"People are active in {guild_name}! Polling for games...")

            if not immediately:
                try:
                    while time_slept < self.config.status_interval_dormant:
                        if not self.polling_is_active(guild_id): # Stop if people leave voice channels.
                            self.polling_active[guild_id] = False
                            logger.info(f"Polling is no longer active in {guild_name}.")
                            return

                        await asyncio.sleep(sleep_per_loop)
                        time_slept += sleep_per_loop

                except KeyboardInterrupt:
                    self.polling_active[guild_id] = False
                    return

            game_status = self.check_game_status(guild_id)

            if game_status == 1: # Game has started.
                # Send update to Int-Far website that a game has started.
                req_data = {
                    "secret": self.config.discord_token,
                    "guild_id": guild_id
                }
                req_data.update(self.active_game[guild_id])
                self.send_game_update("game_started", req_data)

                logger.info(f"Game is now active in {guild_name}, polling for game end...")

                await self.poll_for_game_end(guild_id)

            elif game_status == 0: # Sleep for a bit and check game status again.
                await self.poll_for_game_start(guild_id)

    async def poll_for_game_end(self, guild_id):
        """
        This method is called periodically when a game is active.
        When this method detects that the game is no longer active,
        it calls the 'game_over' method, which determines who is the Int-Far,
        who to give doinks to, etc.
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

        game_status = self.check_game_status(guild_id)
        if game_status == 2: # Game is over.
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

                elif game_info is None: # Game info is still None after 3 retries.
                    # Log error
                    logger.bind(game_id=game_id, guild_id=guild_id).error(
                        "Game info is STILL None after 3 retries! Saving to missing games..."
                    )
    
                    self.database.save_missed_game(game_id, guild_id, int(time()))
    
                    # Send message pinging me about the error.
                    mention_me = self.get_mention_str(commands_util.ADMIN_DISC_ID, guild_id)
                    message_str = (
                        "Riot API is being a dickfish again, not much I can do :shrug:\n"
                        f"{mention_me} will add the game manually later."
                    )

                    await self.send_message_unprompted(message_str, guild_id)

                elif self.database.game_exists(game_info["gameId"]):
                    logger.warning(
                        "We triggered end of game stuff again... Strange!"
                    )

                elif len(self.users_in_game[guild_id]) == 1:
                    response = "Only one person in that game. "
                    response += "no Int-Far will be crowned "
                    response += "and no stats will be saved."
                    await self.channels_to_write[guild_id].send(response)

                elif self.riot_api.is_urf(game_info["gameMode"]):
                    # Gamemode was URF. Don't save stats then.
                    response = "That was an URF game {emote_poggers} "
                    response += "no Int-Far will be crowned "
                    response += "and no stats will be saved."
                    await self.channels_to_write[guild_id].send(self.insert_emotes(response))

                elif not self.riot_api.map_is_sr(game_info["mapId"]):
                    # Game is not on summoners rift. Same deal.
                    response = "That game was not on Summoner's Rift "
                    response += "{emote_woahpikachu} no Int-Far will be crowned "
                    response += "and no stats will be saved."
                    await self.channels_to_write[guild_id].send(self.insert_emotes(response))

                # Game was too short to count. Probably a remake.
                elif game_info["gameDuration"] < self.config.min_game_minutes * 60:
                    response = (
                        "That game lasted less than 5 minutes " +
                        "{emote_zinking} assuming it was a remake. " +
                        "No stats are saved."
                    )
                    await self.channels_to_write[guild_id].send(self.insert_emotes(response))

                else:
                    await self.game_over(game_info, guild_id)

                # Send update to Int-Far website that game is over.
                req_data = {
                    "secret": self.config.discord_token,
                    "guild_id": guild_id, "game_id": game_id
                }
                self.send_game_update("game_ended", req_data)

                self.active_game[guild_id] = None
                self.game_start[guild_id] = None
                del self.users_in_game[guild_id] # Reset the list of users who are in a game.
                asyncio.create_task(self.poll_for_game_start(guild_id))

            except Exception as e:
                game_id = self.active_game.get(guild_id, {}).get("id")

                logger.bind(game_id=game_id).exception("Exception after game was over!!!")

                # Send error message to Discord and re-raise exception.
                await self.send_error_msg(guild_id)

                raise e

        elif game_status == 0:
            await self.poll_for_game_end(guild_id)

    def _send_game_update(self, endpoint, data):
        try:
            return requests.post(f"https://mhooge.com:5000/intfar/{endpoint}", data=data)
        except requests.exceptions.RequestException:
            logger.bind(endpoint=endpoint, data=data).exception("Error ignored in send_game_update")
