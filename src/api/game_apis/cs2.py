import asyncio
import json
import bz2
import os
from uuid import uuid4
import subprocess

from mhooge_flask.logging import logger

import httpx
from bs4 import BeautifulSoup
from steam.client import SteamClient
from csgo.client import CSGOClient
from steam.steamid import SteamID
from steam.core.msg import MsgProto
from steam.enums.emsg import EMsg
from steam.enums.common import EResult
from csgo import sharecode
from google.protobuf.json_format import MessageToJson
from awpy import DemoParser
from gevent import Timeout, sleep
from gevent.event import AsyncResult

from api.config import Config
from api.game_api_client import GameAPIClient
from api.user import User
from api.util import run_async_in_thread

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
    """
    Class for interacting with Steam and CS2 web and Game Coordinator APIs.
    """
    def __init__(self, game: str, config: Config):
        super().__init__(game, config)
        self.logged_on_once = False
        self._logging_on = False

        self.map_names = {}
        self.game_types = {
            1048584: "cache",
            8200: "nuke",
            4104: "inferno",
            2056: "ancient",
            264: "thera",
            520: "dust2",
            1032: "train",
            16392: "vertigo",
            32776: "mirage",
            8388616: "anubis",
            268435464: "overpass"
        }
        self.cs2_app_id = 730

        self.get_latest_data()

        self.steam_client = SteamClient()
        self.cs_client = CSGOClient(self.steam_client)

        self.steam_client.on("logged_on", self._handle_steam_start)
        self.steam_client.on("error", self._handle_steam_error)
        self.steam_client.on("channel_secured", self._handle_channel_secured)
        self.steam_client.on("disconnected", self._handle_steam_disconnect)
        self.steam_client.on("auth_code_required", self._handle_2fa_code)

        self.login()

    @property
    def playable_count(self):
        return len(self.map_names)

    async def wait_event_async(self, emitter, event, timeout=None, raises=True):
        result = AsyncResult()
        emitter.once(event, result)

        time_slept = 0
        sleep_per_loop = 0.01
        while True:
            try:
                return result.get(False)
            except Timeout:
                pass

            await asyncio.sleep(sleep_per_loop)
            sleep(sleep_per_loop)
            time_slept += sleep_per_loop

            if timeout is not None and time_slept > timeout:
                emitter.remove_listener(event, result)
                if raises:
                    raise TimeoutError()
                else:
                    return None

    def get_latest_data(self):
        url = "https://developer.valvesoftware.com/wiki/Counter-Strike_2/Maps"

        try:
            response = httpx.get(url)
            html = BeautifulSoup(response.text, "html.parser")

            former_header = html.find(id="Current_Maps")

            maps_table = former_header.find_next("table")
            table_rows = maps_table.find_all("tr")

            for row in table_rows[3:]:
                columns = row.find_all("td")
                full_name = columns[1].string.strip()
                split = columns[2].string.split("_")
                if len(split) == 1 or len(columns) < 8 or columns[7].string.strip() == "No":
                    continue

                short_name = split[-1].strip()
                self.map_names[short_name] = full_name

            if self.map_names == {}:
                logger.exception(f"Could not get active CS2 maps from {url}")

        except httpx.RequestError:
            logger.exception(f"Exception when downloading CS2 maps from {url}")

    async def download_demo_file(self, filename: str, url: str):
        try:
            data = await self.httpx_client.get(url)

            if data.status_code == 404:
                logger.bind(demo_url=url).error("CS Demo file was not found on Valve's servers!")
                return None

            with open(f"{filename}.dem.bz2", "wb") as fp:
                async for chunk in data.aiter_bytes(chunk_size=128):
                    fp.write(chunk)

        except httpx.RequestError:
            logger.exception("Exception when downloading CS2 demo file from", url)
            return None

        return filename

    def _parse_in_thread(self, demo_file: str, demo_bytes: bytes):
        # Decompress the gz2 compressed demo file
        decompressed = bz2.decompress(demo_bytes)
        with open(demo_file, "wb") as fp:
            fp.write(decompressed)

        # Parse the demo using awpy
        parser = DemoParser(demofile=demo_file)

        return parser.parse()

    async def parse_demo(self, demo_url: str):
        """
        Download and parse demo file from the given URL using awpy.
        """
        demo_file = uuid4().hex

        demo_bz2_file = f"{demo_file}.dem.bz2"
        demo_dem_file = f"{demo_file}.dem"
        demo_json_file = f"{demo_file}.json"

        try:
            # Download and save the demo file to disk
            logger.info("Downloading CS2 demo...")
            demo_file = await self.download_demo_file(demo_file, demo_url)

            if demo_file is None:
                demo_game_data = {"demo_parse_status": "missing"}

            else:
                with open(demo_bz2_file, "rb") as fp:
                    all_bytes = fp.read()

                logger.info("Parsing CS2 demo...")
                demo_game_data = await run_async_in_thread(self._parse_in_thread, demo_dem_file, all_bytes)
                demo_game_data["demo_parse_status"] = "parsed"

        except OSError: # Demo file was corrupt
            logger.bind(demo_url=demo_url).exception("Error when compressing/decompressing demo!")
            demo_game_data = {"demo_parse_status": "malformed"}

        except Exception: # Probably parsing error
            logger.bind(demo_url=demo_url).exception("Generic error when parsing demo.")

            demo_game_data = {"demo_parse_status": "error"}

        finally:
            # Clean up the files after use
            for filename in (demo_bz2_file, demo_dem_file, demo_json_file):
                if os.path.exists(filename):
                    os.remove(filename)

        return demo_game_data

    async def get_basic_match_info(self, match_sharecode: str) -> dict:
        """
        Get information about a match from the CS client, given the match sharecode.
        This includes basic stats about the game (everything seen on the scoreboard
        in-game) as well as a URL to download the demo.
        """
        self.login()
        code_dict = sharecode.decode(match_sharecode)
        self.cs_client.request_full_match_info(
            code_dict["matchid"],
            code_dict["outcomeid"],
            code_dict["token"],
        )
        resp = await self.wait_event_async(self.cs_client, "full_match_info", 10)
        return json.loads(MessageToJson(resp[0]))

    async def get_game_details(self, match_sharecode: str) -> dict:
        """
        Get details about a finished game from the given match sharecode.
        """
        game_info = await self.get_basic_match_info(match_sharecode)
        round_stats = game_info["matches"][0]["roundstatsall"]

        demo_url = round_stats[-1]["map"]

        game_info.update(await self.parse_demo(demo_url))

        if game_info["demo_parse_status"] == "error":
            return None

        game_info["gameId"] = match_sharecode

        return game_info

    async def get_active_game(self, steam_id: str) -> dict:
        self.login()
        self.cs_client.request_watch_info_friends([self.get_account_id(steam_id)])
        resp = await self.wait_event_async(self.cs_client, "watch_info", 10, False)

        if resp is not None:
            return json.loads(MessageToJson(resp[0]))

        return None

    async def get_active_game_for_user(self, user: User):
        for steam_id in user.player_id:
            game_info = await self.get_active_game(steam_id)

            if game_info is not None:
                return game_info, steam_id

            await asyncio.sleep(1)

        return None, None

    async def get_next_sharecode(self, steam_id: str, auth_code: str, match_token: str):
        url = _ENDPOINT_NEXT_MATCH.replace(
            "[key]", self.config.steam_key
        ).replace(
            "[steam_id]", steam_id
        ).replace(
            "[steam_id_key]", auth_code
        ).replace(
            "[match_token]", match_token
        )

        response = await self.httpx_client.get(url)
        if response.status_code not in (200, 202):
            logger.bind(
                steam_id=steam_id,
                steam_id_key=auth_code,
                match_token=match_token,
                status_code=response.status_code,
                response=response.text
            ).exception(
                "Erroneous response code when getting next sharecode form Steam web API."
            )
            return None

        json_response = response.json()

        if response.status_code == 202 and json_response["result"]["nextcode"] == "n/a":
            return None

        return json_response["result"]["nextcode"]

    def get_account_id(self, steam_id: str):
        return SteamID(steam_id).account_id

    def get_map_name(self, map_id: str):
        return self.map_names.get(map_id, map_id.capitalize())

    def get_map_id(self, game_type: int):
        return self.game_types.get(int(game_type))

    def get_playable_name(self, map_id: str):
        return self.get_map_name(map_id)

    async def get_player_name(self, steam_id: str):
        url = _ENDPOINT_PLAYER_SUMMARY.replace(
            "[key]", self.config.steam_key
        ).replace(
            "[steam_id]", steam_id
        )

        response = await self.httpx_client.get(url)
        if response.status_code != 200:
            return None

        for player in response.json().get("response", {}).get("players", []):
            if player["steamid"] == steam_id:
                return player["personaname"]

        return None

    async def get_player_names_for_user(self, user: User) -> list[str]:
        names = []
        for steam_id in user.player_id:
            logger.info(f"Getting username for Steam ID {steam_id}", flush=True)
            player_name = await self.get_player_name(steam_id)
            logger.info(f"Name: {player_name}", flush=True)
            names.append(player_name)

            await asyncio.sleep(1)

        return names

    async def is_person_ingame(self, steam_id: str):
        """
        Returns a boolean indicating whether the user with the given Steam ID is in a game of CS.
        """
        url = _ENDPOINT_PLAYER_SUMMARY.replace(
            "[key]", self.config.steam_key
        ).replace(
            "[steam_id]", steam_id
        )

        try:
            response = await self.httpx_client.get(url, timeout=20)
        except httpx.TimeoutException:
            return False

        if response.status_code != 200:
            return False

        for player in response.json().get("response", {}).get("players", []):
            if player["steamid"] == steam_id:
                return int(player.get("gameid", "0")) == self.cs2_app_id

        return False

    def try_find_playable_id(self, search_term):
        """
        Search for the ID of a map by name.

        Tries to find candidates that have `search_term` as part
        of their name. If only one candidate is found it is returned,
        if more are found, None is returned.

        :param search_term: The search term to try and match map against.
        """
        search_name = search_term.strip().lower()
        candidates = []

        # Try to find candidates that have the search_term in ther name.
        for map_id in self.map_names:
            lowered = self.map_names[map_id].lower()
            if search_name == lowered:
                return map_id

            if search_name in lowered:
                candidates.append(map_id)
                continue

            # Remove apostrophe and period from name.
            if search_name in lowered.replace("'", "").replace(".", ""):
                candidates.append(map_id)

        return candidates[0] if len(candidates) == 1 else None

    async def send_friend_request(self, steam_id: str):
        try:
            self.login()
            self.steam_client.send(MsgProto(EMsg.ClientAddFriend), {"steamid_to_add": int(steam_id)})
            resp_msg = await self.wait_event_async(self.steam_client, EMsg.ClientAddFriendResponse, 5, False)
            if resp_msg is None: # gevent timeout error
                return 0

            resp_json = json.loads(MessageToJson(resp_msg.body))

            if "eresult" not in resp_json: # Weird protobuf error (shouldn't happen)
                return 0

            if resp_json["eresult"] == EResult.DuplicateName: # We were already friends
                return 2

            if resp_json["eresult"] == EResult.OK: # Friend request sent succesfully
                return 1

            return 0 # Error occured
        except Exception:
            logger.bind(steam_id=steam_id).exception("Exception when sending friend request from Int-Far.")
            return 0

    def _handle_steam_start(self):
        logger.info("Steam and CS2 client started.")

        self.cs_client.launch()
        self.logged_on_once = True

    def _handle_steam_error(self, status_code):
        logger.bind(status_code=status_code.value).error(
            f"Steam Client error! Error code: {status_code.value} ({status_code.name})"
        )

    def _handle_channel_secured(self):
        if self.logged_on_once and self.steam_client.relogin_available:
            self.steam_client.relogin()

    def _handle_steam_disconnect(self):
        logger.warning("Steam disconnected!")
        if self.logged_on_once:
            logger.info("Trying to reconnect...")
            try:
                connected = self.steam_client.reconnect(maxdelay=30)
            except Exception:
                connected = False

            if not connected:
                logger.info("Reconnect failed, logging in again.")
                self.login()

    def _handle_2fa_code(self, is_2fa, status_code):
        self.login()

    def get_2fa_codes(self):
        """
        Generate Steam two-factor authentication code with `steamguard-cli`.
        """
        p = subprocess.Popen(["steamguard"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return p.communicate()[0]

    def login(self):
        if self._logging_on or self.is_logged_in():
            return

        logger.info(f"Logging in to Steam...")

        self._logging_on = True
        self.logged_on_once = False

        self.close()

        attempts = 3
        success = False
        for _ in range(attempts):
            try:
                status_code = self.steam_client.login(
                    self.config.steam_username,
                    self.config.steam_password,
                    two_factor_code=self.get_2fa_codes()
                )
            except RuntimeError:
                logger.warning("Already logged in to Steam!")
                return

            if status_code == EResult.OK:
                success = True

            if status_code not in (EResult.TryAnotherCM, EResult.TwoFactorCodeMismatch):
                break

            logger.warning("Could not login to Steam client! Retrying...")
            sleep(5)

        if not success:
            logger.error(
                f"Could not login to Steam client after {attempts} attempts! Error code: {status_code.value} ({status_code.name})"
            )

        while not self.logged_on_once:
            sleep(0.01)

        self._logging_on = False

    def is_logged_in(self):
        return self.steam_client.logged_on

    def close(self):
        if self.steam_client.logged_on:
            self.logged_on_once = False
            self.steam_client.logout()

        if self.steam_client.connected:
            self.steam_client.disconnect()

        if self.cs_client.connection_status:
            self.cs_client.exit()
