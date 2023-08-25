import json
import bz2
import os
from uuid import uuid4

from mhooge_flask.logging import logger

import requests
from steam.client import SteamClient
from steam.guard import SteamAuthenticator
from csgo.client import CSGOClient
from steam.steamid import SteamID
from steam.core.msg import MsgProto
from steam.enums.emsg import EMsg
from csgo import sharecode
from google.protobuf.json_format import MessageToJson
from awpy import DemoParser

from api.config import Config
from api.game_api_client import GameAPIClient

_ENDPOINT_NEXT_MATCH = (
    "https://api.steampowered.com/ICSGOPlayers_730/GetNextMatchSharingCode/v1"
    "?key=[key]"
    "&steamid=[steam_id]"
    "&steamidkey=[steam_id_key]"
    "&knowncode=[match_token]"
)
_ENDPOINT_PLAYER_SUMMARY = (
    "http://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/"
    "?key=[key]"
    "&steamids=[steam_id]"
)

class SteamAPIClient(GameAPIClient):
    def __init__(self, game: str, config: Config):
        super().__init__(game, config)
        self.logged_on_once = False

        self.steam_client = SteamClient()
        self.cs_client = CSGOClient(self.steam_client)

        self.steam_client.on("logged_on", self._handle_steam_start)
        self.steam_client.on("error", self._handle_steam_error)
        self.steam_client.on("connected", self._handle_steam_connected)
        self.steam_client.on("channel_secured", self._handle_channel_secured)
        self.steam_client.on("disconnected", self._handle_steam_disconnect)
        self.steam_client.on("reconnect", self._handle_steam_reconnect)

        self.cs_client.on("ready", self._handle_cs_started)

        if self.config.steam_2fa_code is not None:
            self.login()
        else:
            logger.warning("No Steam 2FA code provided. Steam/CSGO functionality wont work!")

    def _download_demo_file(self, filename, url):
        try:
            data = requests.get(url, stream=True)
            with open(f"{filename}.dem.bz2", "wb") as fp:
                for chunk in data.iter_content(chunk_size=128):
                    fp.write(chunk)

        except requests.RequestException:
            logger.exception("Exception when downloading CSGO demo file from ", url)
            return None

        return filename

    def parse_demo(self, demo_url):
        """
        Download and parse demo file from the given URL
        """
        demo_file = uuid4().hex

        demo_bz2_file = f"{demo_file}.dem.bz2"
        demo_dem_file = f"{demo_file}.dem"
        demo_json_file = f"{demo_file}.json"

        try:
            # Download and save the demo file to disk
            demo_file = self._download_demo_file(demo_file, demo_url)
            with open(demo_bz2_file, "rb") as fp:
                all_bytes = fp.read()

            # Decompress the gz2 compressed demo file
            decompressed = bz2.decompress(all_bytes)
            with open(demo_dem_file, "wb") as fp:
                fp.write(decompressed)

            # Parse the demo using awpy
            parser = DemoParser(demo_dem_file)
            demo_game_data = parser.parse()
        except Exception:
            demo_game_data = None
        finally:
            # Clean up the files after use
            for filename in (demo_bz2_file, demo_dem_file, demo_json_file):
                if os.path.exists(filename):
                    os.remove(filename)

        return demo_game_data

    def get_game_details(self, match_token):
        code_dict = sharecode.decode(match_token)
        self.cs_client.request_full_match_info(
            code_dict["matchid"],
            code_dict["outcomeid"],
            code_dict["token"],
        )
        resp, = self.cs_client.wait_event('full_match_info')
        game_info = json.loads(MessageToJson(resp))
        round_stats = game_info["matches"][0]["roundstatsall"]
        demo_url = round_stats[-1]["map"]

        parsed_data = self.parse_demo(demo_url)
        parsed_data["matchID"] = match_token
        parsed_data["timestamp"] = game_info["matches"][0]["matchtime"]
        parsed_data["duration"] = round_stats[-1]["matchDuration"]
        parsed_data["mvps"] = dict(zip(round_stats[-1]["reservation"]["accountIds"], round_stats[-1]["mvps"]))
        parsed_data["scores"] = dict(zip(round_stats[-1]["reservation"]["accountIds"], round_stats[-1]["scores"]))

        return parsed_data

    def get_active_game(self, steam_ids):
        account_ids = [self.get_account_id(steam_id) for steam_id in steam_ids]
        self.cs_client.request_watch_info_friends(account_ids)
        resp = self.cs_client.wait_event("watch_info", timeout=10)
        return json.loads(MessageToJson(resp[0]))

    def get_next_sharecode(self, steam_id, game_code, match_token):
        url = _ENDPOINT_NEXT_MATCH.replace(
            "[key]", self.config.steam_key
        ).replace(
            "[steam_id]", steam_id
        ).replace(
            "[steam_id_key]", game_code
        ).replace(
            "[match_token]", match_token
        )

        return requests.get(url)

    def get_account_id(self, steam_id):
        return SteamID(steam_id).account_id

    def get_steam_display_name(self, steam_id):
        url = _ENDPOINT_PLAYER_SUMMARY.replace(
            "[key]", self.config.steam_key
        ).replace(
            "[steam_id]", str(steam_id)
        )

        response = requests.get(url)
        if response.status_code != 200:
            return None

        for player in response.json().get("response", {}).get("players", []):
            if player["steamid"] == str(steam_id):
                return player["personaname"]

        return None

    def send_friend_request(self, steam_id):
        try:
            self.steam_client.send(MsgProto(EMsg.ClientFriendProfileInfo), {"steamid_friend": steam_id})
            resp_msg = self.steam_client.wait_msg(EMsg.ClientFriendProfileInfoResponse, timeout=5, raises=False)
            if resp_msg is None:
                raise TimeoutError()

            resp_json = json.loads(MessageToJson(resp_msg.body))
            print(resp_json, flush=True)
            if "eresult" in resp_json and resp_json["eresult"] == 1:
                return True

            self.steam_client.send(MsgProto(EMsg.ClientAddFriend), {"steamid_to_add": steam_id})
            resp_msg = self.steam_client.wait_msg(EMsg.ClientAddFriendResponse, timeout=10, raises=False)
            if resp_msg is None:
                raise TimeoutError()

            resp_json = json.loads(MessageToJson(resp_msg.body))
            print(resp_json, flush=True)
        except Exception:
            logger.bind(steam_id=steam_id).exception("Exception when sending friend request from Int-Far.")
            print("DED", flush=True)
            return False

        return "eresult" in resp_json and resp_json["eresult"] == 1

    def _handle_steam_start(self):
        self.cs_client.launch()

        self.logged_on_once = True
        logger.info(f"Logged on to Steam as '{self.steam_client.user.name}'")

        self.steam_client.run_forever()

    def _handle_cs_started(self):
        logger.info("CS Started")

    def _handle_steam_error(self, error):
        logger.bind(steam_error=error).error("Steam Client error")

    def _handle_steam_connected(self):
        logger.info(f"Steam connected to {self.steam_client.current_server_addr}")

    def _handle_channel_secured(self):
        if self.logged_on_once and self.steam_client.relogin_available:
            self.steam_client.relogin()

    def _handle_steam_disconnect(self):
        logger.info("Steam disconnected")

        if self.logged_on_once:
            logger.info("Reconnecting to Steam...")
            self.steam_client.reconnect(maxdelay=30)

    def _handle_steam_reconnect(self, delay):
        logger.info(f"Reconnecting to steam in {delay} seconds...")

    def get_2fa_code_from_secrets(self):
        return SteamAuthenticator(self.config.steam_secrets).get_code()

    def login(self):
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

        if self.cs_client.connection_status:
            self.cs_client.exit()
