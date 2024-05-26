from api.meta_database import MetaDatabase
from api.game_database import GameDatabase
from api.game_apis.lol import RiotAPIClient
from api.game_apis.cs2 import SteamAPIClient
from api.game_api_client import GameAPIClient

from mhooge_flask.logging import logger

def register_for_lol(
    meta_database: MetaDatabase,
    game_database: GameDatabase,
    api_client: RiotAPIClient,
    disc_id: int,
    *summ_name: tuple[str]
):
    if len(summ_name) == 0:
        return 0, "You must supply a summoner name."

    summ_name_joined = " ".join(summ_name)

    if game_database.discord_id_from_ingame_info(player_name=summ_name_joined):
        return 0, "User with that summoner name is already registered."

    elif (summ_info := api_client.get_summoner_data(summ_name_joined.replace(" ", "%20"))) is None:
        return 0, "Invalid summoner name."

    # Add user to Int-Far base users if they are new
    meta_database.add_user(disc_id)

    # Add user to game database
    status_code, status = game_database.add_user(
        disc_id,
        player_name=summ_name_joined,
        player_id=summ_info["id"],
        puuid=summ_info["puuid"]
    )

    return status_code, status

def register_for_cs2(
    meta_database: MetaDatabase,
    game_database: GameDatabase,
    api_client: SteamAPIClient,
    disc_id: int,
    steam_id: int,
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

    steam_name = api_client.get_steam_display_name(steam_id)
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
        friend_status = api_client.send_friend_request(steam_id)
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

def register_for_game(
    meta_database: MetaDatabase,
    game_database: GameDatabase,
    api_client: GameAPIClient,
    disc_id: int,
    *game_params
) -> tuple[int, str]:
    return _REGISTER_METHODS[api_client.game](meta_database, game_database, api_client, disc_id, *game_params)
