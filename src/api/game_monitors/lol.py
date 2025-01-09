from time import time
import asyncio

from mhooge_flask.logging import logger

from api import lan
from api.game_monitor import GameMonitor
from api.user import User
from api.game_data.lol import get_player_stats

class LoLGameMonitor(GameMonitor):
    POSTGAME_STATUS_CUSTOM_GAME = 4
    POSTGAME_STATUS_URF = 5
    POSTGAME_STATUS_INVALID_MAP = 6
    POSTGAME_STATUS_REMAKE = 7

    def get_users_in_game(self, user_dict: dict[int, User], game_data: dict):
        users_in_game = {}
        for disc_id in user_dict:
            puuids = user_dict[disc_id].puuid
            player_stats = get_player_stats(game_data, puuids)
            if player_stats is not None:
                active_summ_name = None
                for puuid, summ_name in zip(user_dict[disc_id].puuid, user_dict[disc_id].player_name):
                    if puuid == player_stats["puuid"]:
                        active_summ_name = summ_name
                        break

                users_in_game[disc_id] = User(
                    disc_id,
                    user_dict[disc_id].secret,
                    [active_summ_name],
                    [player_stats["summonerId"]],
                    puuid=[player_stats["puuid"]],
                    champ_id=player_stats["championId"],
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
            game_data, active_id = await self.api_client.get_active_game_for_user(user_dict[disc_id])
            if game_data is None:
                continue

            game_start = int(game_data["gameStartTime"]) / 1000
            active_game_start = game_start

            player_stats = get_player_stats(game_data, [active_id])
            if player_stats is None:
                logger.bind(game_data=game_data).warning(f"Could not find player stats for {active_id}!")

            game_ids.add(game_data["gameId"])
            active_game_team = player_stats["teamId"]
            active_game = game_data

            users_in_current_game.update(self.get_users_in_game(user_dict, game_data))

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
            return self.POSTGAME_STATUS_REMAKE

        return self.POSTGAME_STATUS_OK

    async def get_finished_game_info(self, guild_id: int):
        game_id = self.active_game[guild_id]["id"]

        # Check if game was a custom game, if so don't save stats.
        custom_game = self.active_game[guild_id].get("game_type", "") == "CUSTOM_GAME"

        game_info = None
        if not custom_game:
            game_info, status_code = await self.try_get_finished_game_info(game_id, guild_id)

        if custom_game: # Do nothing.
            logger.info(f"Game was a custom game: {game_id}")
            status_code = self.POSTGAME_STATUS_CUSTOM_GAME

        elif game_info is None and status_code not in (self.POSTGAME_STATUS_DUPLICATE, self.POSTGAME_STATUS_SOLO):
             # Game info is still None after 3 retries, log error
            logger.bind(game_id=game_id, guild_id=guild_id).error(
                "Game info is STILL None after 5 retries! Saving to missing games..."
            )
            game_info = {"gameId": game_id}
            status_code = self.POSTGAME_STATUS_MISSING

        # Get rank of each player in the game, if status is OK
        if status_code == self.POSTGAME_STATUS_OK:
            player_ranks = {}
            await asyncio.sleep(2)

            for disc_id in self.users_in_game[guild_id]:
                summ_id = self.users_in_game[guild_id][disc_id].player_id[0]
                rank_info = await self.api_client.get_player_rank(summ_id)
                if rank_info is not None:
                    player_ranks[disc_id] = rank_info

                await asyncio.sleep(1.5)

            game_info["player_ranks"] = player_ranks

        return game_info, status_code

    def handle_game_over(self, game_info: dict, status_code: int, guild_id: int):
        if game_info is not None:
            self.active_game[guild_id]["queue_id"] = game_info["queueId"]
        
        post_game_data = super().handle_game_over(game_info, status_code, guild_id)

        if post_game_data is not None and lan.is_lan_ongoing(time(), guild_id):
            lan.update_bingo_progress(self.game_database, post_game_data)

        return post_game_data
