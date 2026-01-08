from time import sleep
from glob import glob
from os import remove
from os.path import exists
import json
import asyncio
from typing import Literal

from mhooge_flask.logging import logger
import httpx

from intfar.api.game_api_client import GameAPIClient
from intfar.api.user import User
from intfar.api.config import Config

API_PLATFORM = "https://euw1.api.riotgames.com"
API_REGION = "https://europe.api.riotgames.com"

class RiotAPIClient(GameAPIClient):
    """
    Class for interacting with Riot Games League of Legends game data API.
    """
    def __init__(self, game: str, config: Config):
        super().__init__(game, config)
        self.champ_names = {}
        self.champ_ids = {}
        self.champ_portraits_path = f"{config.static_folder}/img/champions/portraits"
        self.champ_splash_path = f"{config.static_folder}/img/champions/splashes"
        self.champ_abilities_path = f"{config.static_folder}/img/champions/abilities"
        self.item_icons_path = f"{config.static_folder}/img/items"
        self.champ_data_path = f"{config.static_folder}/champ_data"
        self.latest_patch = None

        self.get_latest_data()

    @property
    def playable_count(self):
        return len(self.champ_ids)

    @property
    def champions_file(self):
        return f"{self.config.resources_folder}/champions-{self.latest_patch}.json"

    @property
    def items_file(self):
        return f"{self.config.resources_folder}/items-{self.latest_patch}.json"

    @property
    def maps_file(self):
        return f"{self.config.resources_folder}/maps.json"

    def get_latest_data(self):
        """
        Fetch information about the latest League of Legends patch.
        First, fetches what the latest patch is,
        then downloads champion metadata, splashes, and portraits.
        """
        self.latest_patch = self.get_latest_patch()
        if not exists(self.champions_file):
            self.get_latest_champions_file()

        if not exists(self.items_file):
            self.get_latest_items_file()

        self.initialize_champ_dicts()
        self.get_champion_portraits()
        self.get_champion_splashes()
        self.get_champion_data()

    def initialize_champ_dicts(self):
        champions_file = self.champions_file
        if champions_file is None:
            return

        with open(champions_file, encoding="utf-8") as fp:
            champion_data = json.load(fp)
            for champ_name in champion_data["data"]:
                data_for_champ = champion_data["data"][champ_name]
                self.champ_names[int(data_for_champ["key"])] = data_for_champ["name"]

        name_order_champs = sorted(list(self.champ_names.items()), key=lambda x: x[1])
        self.champ_ids = {kv[0]: index for index, kv in enumerate(name_order_champs)}

    def get_latest_patch(self):
        url = "https://ddragon.leagueoflegends.com/api/versions.json"
        try:
            response_json = httpx.get(url).json()
            return response_json[0]
        except httpx.RequestError:
            logger.exception("Exception when getting newest game version from Riot API!")
            return None

    def get_latest_champions_file(self):
        url = f"http://ddragon.leagueoflegends.com/cdn/{self.latest_patch}/data/en_US/champion.json"
        logger.info(f"Downloading latest champions file: '{self.champions_file}'")

        old_files = glob(f"{self.config.resources_folder}/champions-*.json")

        try:
            response_json = httpx.get(url).json()
            f_out = open(self.champions_file, "w", encoding="utf-8")
            json.dump(response_json, f_out)
            for old_file in old_files:
                remove(old_file)
        except httpx.RequestError:
            logger.exception("Exception when getting newest champion.json file from Riot API.")

    def get_latest_items_file(self):
        url = f"https://ddragon.leagueoflegends.com/cdn/{self.latest_patch}/data/en_US/item.json"
        logger.info(f"Downloading latest item file: '{self.items_file}'")

        old_files = glob(f"{self.config.resources_folder}/items-*.json")

        try:
            response_json = httpx.get(url).json()
            f_out = open(self.items_file, "w", encoding="utf-8")
            json.dump(response_json, f_out)
            for old_file in old_files:
                remove(old_file)
        except httpx.RequestError:
            logger.exception("Exception when getting newest item.json file from Riot API.")

    def get_champion_portraits(self):
        base_url = f"http://ddragon.leagueoflegends.com/cdn/{self.latest_patch}/img/champion"

        with open(self.champions_file, encoding="utf-8") as fp:
            champion_data = json.load(fp)

        for champ_name in champion_data["data"]:
            champ_id = int(champion_data["data"][champ_name]["key"])
            filename = self.get_champ_portrait_path(champ_id)
            if exists(filename):
                continue

            url = f"{base_url}/{champ_name}.png"
            logger.info(f"Downloading champion portrait for '{champ_name}'")

            try:
                data = httpx.get(url)
                with open(filename, "wb") as fp_out:
                    for chunk in data.iter_bytes(chunk_size=128):
                        fp_out.write(chunk)

            except httpx.RequestError:
                logger.exception(f"Exception when getting champion portrait for {champ_name} from Riot API.")

            sleep(0.5)

    def get_champion_splashes(self):
        base_url = f"http://ddragon.leagueoflegends.com/cdn/img/champion/loading"

        with open(self.champions_file, encoding="utf-8") as fp:
            champion_data = json.load(fp)

        for champ_name in champion_data["data"]:
            champ_id = int(champion_data["data"][champ_name]["key"])
            filename = self.get_champ_splash_path(champ_id)
            if exists(filename):
                continue

            url = f"{base_url}/{champ_name}_0.jpg"
            logger.info(f"Downloading champion splash for '{champ_name}'")

            try:
                data = httpx.get(url)
                with open(filename, "wb") as fp_out:
                    for chunk in data.iter_bytes(chunk_size=128):
                        fp_out.write(chunk)

            except httpx.RequestError:
                logger.exception(f"Exception when getting champion splash for {champ_name} from Riot API.")

            sleep(0.5)

    def get_champion_abilities(self):
        base_url_passives = f"https://ddragon.leagueoflegends.com/cdn/{self.latest_patch}/img/passive"
        base_url_actives = f"https://ddragon.leagueoflegends.com/cdn/{self.latest_patch}/img/spell"

        with open(self.champions_file, encoding="utf-8") as fp:
            champion_data = json.load(fp)

        for champ_name in champion_data["data"]:
            champ_id = int(champion_data["data"][champ_name]["key"])
            champ_data_file = self.get_champ_data_path(champ_id)

            with open(champ_data_file, "r", encoding="utf-8") as fp:
                champ_data = json.load(fp)

            logger.info(f"Downloading ability icons for '{champ_name}'")

            abilities = [champ_data["data"][champ_name]["passive"]] + champ_data["data"][champ_name]["spells"]

            for index, ability in enumerate(abilities):
                base_url = base_url_passives if index == 0 else base_url_actives
                ability_id = ability["id"] if "id" in ability else "passive"

                filename = self.get_champ_abilities_path(champ_id, ability_id)
                if exists(filename):
                    continue

                image_name = ability["image"]["full"]
                url = f"{base_url}/{image_name}"

                try:
                    data = httpx.get(url)
                    with open(filename, "wb") as fp:
                        for chunk in data.iter_bytes(chunk_size=128):
                            fp.write(chunk)

                except httpx.RequestError:
                    logger.exception(f"Exception when getting ability icon for {ability['name']} for {champ_name} from Riot API.")

                sleep(0.5)

    def get_champion_data(self):
        base_url = f"https://ddragon.leagueoflegends.com/cdn/{self.latest_patch}/data/en_US/champion"

        with open(self.champions_file, encoding="utf-8") as fp:
            champion_data = json.load(fp)

        for champ_name in champion_data["data"]:
            champ_id = int(champion_data["data"][champ_name]["key"])

            filename = self.get_champ_data_path(champ_id)
            if exists(filename):
                continue

            url = f"{base_url}/{champ_name}.json"
            logger.info(f"Downloading champion data for '{champ_name}'")

            try:
                data = httpx.get(url)
                with open(filename, "wb") as fp_out:
                    for chunk in data.iter_bytes(chunk_size=128):
                        fp_out.write(chunk)

            except httpx.RequestError:
                logger.exception(f"Exception when getting champion data for {champ_name} from Riot API.")

            sleep(0.5)

    def get_item_icons(self):
        base_url = f"https://ddragon.leagueoflegends.com/cdn/{self.latest_patch}/img/item"

        with open(self.items_file, encoding="utf-8") as fp:
            item_data = json.load(fp)

        for item_id in item_data["data"]:
            filename = f"{self.item_icons_path}/{item_id}.png"
            if exists(filename):
                continue

            url = f"{base_url}/{item_id}.png"
            logger.info(f"Downloading item icon for '{item_data['data'][item_id]['name']}'")

            try:
                data = httpx.get(url)
                with open(filename, "wb") as fp_out:
                    for chunk in data.iter_bytes(chunk_size=128):
                        fp_out.write(chunk)

            except httpx.RequestError:
                logger.exception(f"Exception when getting item icon for {item_id} from Riot API.")

            sleep(0.5)

    async def make_request(self, endpoint, api_route, *params, ignore_errors=[]):
        req_string = endpoint
        for index, param in enumerate(params):
            req_string = req_string.replace("{" + str(index) + "}", str(param))

        full_url = api_route + req_string

        token_header = {"X-Riot-Token": self.config.riot_key}
        try:
            response = await self.httpx_client.get(full_url, headers=token_header)
        except httpx.ConnectTimeout:
            logger.bind(
                event="riot_api_error",
                url=full_url,
            ).error("Connection timeout during Riot API request")
            return None

        if response.status_code != 200 and response.status_code not in ignore_errors:
            logger.bind(
                event="riot_api_error",
                url=full_url,
                response=response.text,
                status_code=response.status_code 
            ).error("Error during Riot API request")

        return response

    async def get_puuid(self, game_name, tag):
        endpoint = "/riot/account/v1/accounts/by-riot-id/{0}/{1}"
        response = await self.make_request(endpoint, API_REGION, game_name, tag)
        if response is None or response.status_code != 200:
            return None

        return response.json()["puuid"]

    async def get_player_data(self, player_id: str):
        endpoint = f"/lol/summoner/v4/summoners/by-puuid"
        route = API_REGION
        endpoint = endpoint + "/" + "{0}"

        response = await self.make_request(endpoint, route, player_id)
        if response is None or response.status_code != 200:
            return None

        return response.json()

    async def get_player_name(self, puuid: str):
        endpoint = "/riot/account/v1/accounts/by-puuid/{0}"
        response = await self.make_request(endpoint, API_REGION, puuid)
        if response is None or response.status_code != 200:
            return None

        data = response.json()
        return f"{data['gameName']}#{data['tagLine']}"

    async def get_player_names_for_user(self, user: User) -> list[str]:
        names = []
        for puuid in user.player_id:
            player_name = await self.get_player_name(puuid)
            names.append(player_name)

            await asyncio.sleep(1)

        return names

    async def get_match_history(
        self,
        puuid: str,
        date_from: int | float | None = None,
        date_to: int | float | None = None,
        game_type: Literal["ranked", "normal", "tourney", "tutorial"] | None = "ranked",
    ):
        query_params = []
        if date_from:
            query_params.append(f"startTime={int(date_from)}")
        if date_to:
            query_params.append(f"endTime={int(date_to)}")
        if game_type:
            query_params.append(f"type={game_type}")

        endpoint = "/lol/match/v5/matches/by-puuid/{0}/ids"
        if query_params:
            endpoint += f"?{'&'.join(query_params)}"

        response = await self.make_request(endpoint, API_REGION, puuid)
        if response is None or response.status_code != 200:
            return []

        return sorted(map(lambda x: int(x.removeprefix("EUW1_")), json.loads(response.text)))

    async def get_active_game(self, puuid: str):
        endpoint = "/lol/spectator/v5/active-games/by-summoner/{0}"
        try:
            response = await self.make_request(endpoint, API_PLATFORM, puuid, ignore_errors=[404])
            if response is None or response.status_code != 200:
                return None

        except (httpx.ConnectError, httpx.RequestError):
            return None

        return response.json()

    async def get_active_game_for_user(self, user: User):
        for puuid in user.player_id:
            game_info = await self.get_active_game(puuid)

            if game_info is not None:
                return game_info, puuid

            await asyncio.sleep(1)

        return None, None

    async def get_game_timeline(self, game_id, tries=0):
        endpoint = "/lol/match/v5/matches/{0}/timeline"

        response = await self.make_request(endpoint, API_REGION, f"EUW1_{game_id}")
        if response is None or response.status_code != 200:
            if tries > 0:
                sleep(30)
                return await self.get_game_timeline(game_id, tries-1)

            return None

        return response.json()["info"]

    async def get_player_rank(self, puuid):
        endpoint = "/lol/league/v4/entries/by-puuid/{0}"

        response = await self.make_request(endpoint, API_PLATFORM, puuid)
        if response is None or response.status_code != 200:
            return None

        return response.json()

    async def get_game_details(self, game_id):
        api_v4_cutoff = 5448295599
        if int(game_id) > api_v4_cutoff:
            endpoint = "/lol/match/v5/matches/{0}"
            response = await self.make_request(endpoint, API_REGION, f"EUW1_{game_id}")

        else:
            endpoint = "/lol/match/v4/matches/{0}"
            response = await self.make_request(endpoint, API_PLATFORM, game_id)

            return response.json()

        if response is None or response.status_code != 200:
            return None

        data = response.json()["info"]
        duration = data["gameDuration"]
        data["gameDuration"] = duration if "gameEndTimestamp" in data else duration / 1000 

        await asyncio.sleep(2)

        # Get timeline data
        timeline_data = await self.get_game_timeline(game_id)
        data["timeline"] = timeline_data

        return data

    async def get_champion_mastery(self, puuid):
        endpoint = "/lol/champion-mastery/v4/champion-masteries/by-puuid/{0}"
        response = await self.make_request(endpoint, API_PLATFORM, puuid)

        if response is None or response.status_code != 200:
            return None

        return response.json()

    def get_champ_name(self, champ_id):
        return self.champ_names.get(champ_id)

    def get_playable_name(self, champ_id):
        return self.get_champ_name(champ_id)

    def get_champ_portrait_path(self, champ_id):
        return f"{self.champ_portraits_path}/{champ_id}.png"

    def get_champ_splash_path(self, champ_id):
        return f"{self.champ_splash_path}/{champ_id}.png"

    def get_champ_abilities_path(self, champ_id, ability):
        return f"{self.champ_abilities_path}/{champ_id}_{ability}.png"

    def get_champ_data_path(self, champ_id):
        return f"{self.champ_data_path}/{champ_id}.json"

    def try_find_playable_id(self, search_term):
        """
        Search for the ID of a champion by name.

        Tries to find candidates that have `search_term` as part
        of their name. If only one candidate is found it is returned,
        if more are found, None is returned.

        :param search_term: The search term to try and match champions against.
        Should use _ in place of spaces and should not include
        . or ' (fx. Kai'sa should be Kaisa, Dr. Mundo should be Dr_Mundo)
        """
        search_name = search_term.strip().lower().replace("_", " ").replace("'", "")
        candidates = {
            0: [],
            1: []
        }

        # Try to find candidates that have the search_term in ther name.
        for champ_id in self.champ_names:
            lowered = self.champ_names[champ_id].lower()
            if search_name == lowered:
                return champ_id

            if lowered.startswith(search_name):
                candidates[0].append(champ_id)
                continue

            if search_name in lowered:
                candidates[1].append(champ_id)
                continue

            # Remove apostrophe and period from name.
            if search_name in lowered.replace("'", "").replace(".", ""):
                candidates[1].append(champ_id)

        for priority in candidates:
            if len(candidates[priority]) == 1:
                return candidates[priority][0]

        return None

    def get_map_name(self, map_id):
        """
        Get name of League of Legends map with id `map_id`.
        """
        with open(self.maps_file, encoding="utf-8") as fp:
            map_data = json.load(fp)
            for map_info in map_data:
                if map_info["mapId"] == map_id:
                    return map_info["mapName"]

        return None

    def map_is_valid(self, map_id):
        with open(self.maps_file, encoding="utf-8") as fp:
            map_data = json.load(fp)
            for map_info in map_data:
                if map_info["mapId"] == map_id:
                    return map_info["mapName"] in ("Summoner's Rift", "Nexus Blitz")#, "Rings of Wrath")

        return False

    def is_urf(self, gamemode):
        return gamemode == "URF"

    def is_clash(self, queue_id):
        return queue_id == 700
