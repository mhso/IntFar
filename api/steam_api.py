import json
from mhooge_flask.logging import logger

import requests
from steam.client import SteamClient
from steam.guard import SteamAuthenticator
from csgo.client import CSGOClient
from csgo import sharecode
from google.protobuf.json_format import MessageToJson

_ENDPOINT = (
    "https://api.steampowered.com/ICSGOPlayers_730/GetNextMatchSharingCode/v1"
    "?key=[key]"
    "&steamid=[steam_id]"
    "&steamidkey=[steam_id_key]"
    "&knowncode=[match_token]"
)

class SteamAPIClient:
    _MATCH_TOKEN_DICT = "ABCDEFGHJKLMNOPQRSTUVWXYZabcdefhijkmnopqrstuvwxyz23456789"
    _MATCH_TOKEN_DICT_LEN = len(_MATCH_TOKEN_DICT)

    def __init__(self, config):
        self.config = config
        self.logged_on_once = False

        self.steam_client = SteamClient()
        self.cs_client = CSGOClient(self.steam_client)

        self.steam_client.on("logged_on", self.handle_steam_start)
        self.steam_client.on("error", self.handle_steam_error)
        self.steam_client.on("connected", self.handle_steam_connected)
        self.steam_client.on("channel_secured", self.handle_channel_secured)
        self.steam_client.on("disconnected", self.handle_steam_disconnect)
        self.steam_client.on("reconnect", self.handle_steam_reconnect)

        self.cs_client.on("ready", self.handle_cs_started)

        if self.config.steam_2fa_code is not None:
            self.login()
        else:
            logger.warning("No Steam 2FA code provided. Steam/CSGO functionality wont work!")

    def handle_steam_start(self):
        self.cs_client.launch()

        self.logged_on_once = True
        logger.info(f"Logged on to Steam as '{self.steam_client.user.name}'")

        self.steam_client.run_forever()

    def handle_cs_started(self):
        logger.info("CS Started")
    
    def handle_steam_error(self, error):
        logger.bind(steam_error=error).error("Steam Client error")

    def handle_steam_connected(self):
        logger.info(f"Steam connected to {self.steam_client.current_server_addr}")

    def handle_channel_secured(self):
        if self.logged_on_once and self.steam_client.relogin_available:
            self.steam_client.relogin()

    def handle_steam_disconnect(self):
        logger.info("Steam disconnected")

        if self.logged_on_once:
            logger.info("Reconnecting to Steam...")
            self.steam_client.reconnect(maxdelay=30)

    def handle_steam_reconnect(self, delay):
        logger.info(f"Reconnecting to steam in {delay} seconds...")

    def get_2fa_code_from_secrets(self):
        return SteamAuthenticator(self.config.steam_secrets).get_code()

    def login(self):
        if self.config.steam_2fa_code is not None:
            self.steam_client.login(
                self.config.steam_username,
                self.config.steam_password,
                two_factor_code=self.config.steam_2fa_code
            )

    def close(self):
        if self.steam_client.logged_on:
            self.logged_on_once = False
            self.steam_client.logout()

        if self.steam_client.connected:
            self.steam_client.disconnect()

    def get_game_details(self, match_token):
        code_dict = sharecode.decode(match_token)
        self.cs_client.request_full_match_info(
            code_dict["matchid"],
            code_dict["outcomeid"],
            code_dict["token"],
        )
        resp, = self.cs_client.wait_event('full_match_info')
        as_json = json.loads(MessageToJson(resp))

        return as_json

    def get_next_sharecode(self, steam_id, game_code, match_token):
        url = _ENDPOINT.replace(
            "[key]", self.config.steam_key
        ).replace(
            "[steam_id]", steam_id
        ).replace(
            "[steam_id_key]", game_code
        ).replace(
            "[match_token]", match_token
        )

        return requests.get(url)
