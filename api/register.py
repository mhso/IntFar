from api.database import Database
from api.game_api.lol import RiotAPIClient
from api.game_api.csgo import SteamAPIClient
from api.game_api_client import GameAPIClient

def register_for_lol(database: Database, api_client: RiotAPIClient, disc_id: int, summ_name: str):
    if summ_name is None:
        return 0, "You must supply a summoner name."

    if database.discord_id_from_ingame_info(api_client.game, ingame_name=summ_name):
        return 0, "User with that summoner name is already registered."

    elif (summ_id := api_client.get_summoner_id(summ_name.replace(" ", "%20"))) is None:
        return 0, "Error: Invalid summoner name."

    return database.add_user(
        api_client.game,
        disc_id,
        ingame_name=summ_name,
        ingame_id=summ_id
    )

def register_for_csgo(database: Database, api_client: SteamAPIClient, disc_id: int, steam_id: str, match_auth_code: str=None):
    if steam_id is None:
        return 0, "You must supply a Steam ID."

    if match_auth_code is None:
        return 0, "You must supply a match authentication code."

    if database.discord_id_from_ingame_info(api_client.game, ingame_id=steam_id):
        return 0, "User with that Steam ID is already registered."

    steam_name = api_client.get_steam_display_name(steam_id)
    if steam_name is None:
        return False, "Error: Invalid Steam ID."

    status_code, status_msg = database.add_user(
        api_client.game,
        disc_id,
        ingame_name=steam_name,
        ingame_id=steam_id,
        match_auth_code=match_auth_code
    )

    if status_code == 1: # New user
        # Send friend request on Steam from Int-Far to the newly registered player
        api_client.send_friend_request(steam_id)

    return status_code, status_msg

_REGISTER_METHODS = {
    "lol": register_for_lol,
    "csgo": register_for_csgo
}

def register_for_game(database: Database, api_client: GameAPIClient, disc_id: int, *game_params) -> tuple[int, str]:
    return _REGISTER_METHODS[api_client.game](database, api_client, disc_id, *game_params)
