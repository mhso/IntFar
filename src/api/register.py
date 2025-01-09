from api.meta_database import MetaDatabase
from api.game_database import GameDatabase
from api.game_apis.lol import RiotAPIClient
from api.game_apis.cs2 import SteamAPIClient
from api.game_api_client import GameAPIClient

from mhooge_flask.logging import logger

async def register_for_lol(
    meta_database: MetaDatabase,
    game_database: GameDatabase,
    api_client: RiotAPIClient,
    disc_id: int,
    *summ_name: tuple[str]
):
    if len(summ_name) == 0:
        return 0, "You must supply a Riot ID (in the format 'name#tag)."

    summ_name_joined = " ".join(summ_name)

    if "#" not in summ_name_joined:
        return 0, "You must supply your tag aswell (like this: 'name#tag')."

    split = summ_name_joined.split("#")
    if len(split) != 2:
        return 0, "Invalid Riot ID (should be in the format 'name#tag')."

    game_name = split[0].strip().replace(" ", "%20")
    tag = split[1].strip()

    if game_database.discord_id_from_ingame_info(player_name=summ_name_joined):
        return 0, "User with that Riot ID is already registered."

    elif (puuid := await api_client.get_puuid(game_name, tag)) is None:
        return 0, "Riot ID does not exist (acording to Rito)."

    summ_id = await api_client.get_player_data_from_puuid(puuid)["id"]

    # Add user to Int-Far base users if they are new
    meta_database.add_user(disc_id)

    # Add user to game database
    status_code, status = game_database.add_user(
        disc_id,
        player_name=summ_name_joined,
        player_id=summ_id,
        puuid=puuid
    )

    return status_code, status

async def register_for_cs2(
    meta_database: MetaDatabase,
    game_database: GameDatabase,
    api_client: SteamAPIClient,
    disc_id: int,
    steam_id: str,
    match_auth_code: str = None,
    match_token: str = None
):
    if steam_id is None:
        return 0, "You must supply a Steam ID."

    if match_auth_code is None:
        return 0, "You must supply a match authentication code."

    if match_token is None:
        return 0, "You must supply the most recent match token."

    if game_database.discord_id_from_ingame_info(player_id=steam_id) is not None:
        return 0, "User with that Steam ID is already registered."

    steam_name = await api_client.get_player_name(steam_id)
    if steam_name is None:
        return 0, "Invalid Steam ID."

    # Add user to Int-Far base users if they are new
    meta_database.add_user(disc_id)

    status_code, status_msg = game_database.add_user(
        disc_id,
        player_name=steam_name,
        player_id=steam_id,
        match_auth_code=match_auth_code,
        latest_match_token=match_token
    )

    if status_code in (1, 2):
        # Send friend request on Steam from Int-Far to the newly registered player
        friend_status = await api_client.send_friend_request(steam_id)
        logger.info(f"Sent Steam friend request with status {friend_status}")

        if friend_status == 2: # Int-Far was already friends with the person
            return 2, "You are already friends with Int-Far on Steam, so you are good to go!"

        if friend_status == 0:
            status_msg = "Could not send friend request from Int-Far. Contact Say wat and have him fix it."
            status_code = 0

    return status_code, status_msg

_REGISTER_METHODS = {
    "lol": register_for_lol,
    "cs2": register_for_cs2
}

async def register_for_game(
    meta_database: MetaDatabase,
    game_database: GameDatabase,
    api_client: GameAPIClient,
    disc_id: int,
    *game_params
) -> tuple[int, str]:
    return await _REGISTER_METHODS[api_client.game](meta_database, game_database, api_client, disc_id, *game_params)
