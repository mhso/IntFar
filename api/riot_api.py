from time import sleep
from glob import glob
from os import remove
from os.path import exists
import json

from mhooge_flask.logging import logger
import requests

API_PLATFORM = "https://euw1.api.riotgames.com"
API_REGION = "https://europe.api.riotgames.com"

class APIClient:
    def __init__(self, config):
        self.config = config
        self.champ_names = {}
        self.champ_ids = {}
        self.champ_portraits_path = "app/static/img/champions/portraits"
        self.champ_splash_path = "app/static/img/champions/splashes"
        self.champ_data_path = "app/static/champ_data"
        self.latest_patch = None

        self.get_latest_data()

    def get_latest_data(self):
        self.latest_patch = self.get_latest_patch()
        if not exists(self.get_champions_file()):
            self.get_latest_champions_file()
        self.champ_splash_path = "app/static/img/champions/splashes"
        self.initialize_champ_dicts()
        self.get_champion_portraits()
        self.get_champion_splashes()

    def initialize_champ_dicts(self):
        champions_file = self.get_champions_file()
        if champions_file is None:
            return

        with open(champions_file, encoding="utf-8") as fp:
            champion_data = json.load(fp)
            for champ_name in champion_data["data"]:
                data_for_champ = champion_data["data"][champ_name]
                self.champ_names[int(data_for_champ["key"])] = data_for_champ["name"]

        name_order_champs = sorted(list(self.champ_names.items()), key=lambda x: x[1])
        self.champ_ids = {kv[0]: index for index, kv in enumerate(name_order_champs)}

    def get_champions_file(self):
        return f"api/champions-{self.latest_patch}.json"

    def get_latest_patch(self):
        url = "https://ddragon.leagueoflegends.com/api/versions.json"
        try:
            response_json = requests.get(url).json()
            return response_json[0]
        except requests.exceptions.RequestException:
            logger.error("Exception when getting newest game version from Riot API!")
            return None

    def get_latest_champions_file(self):
        url = f"http://ddragon.leagueoflegends.com/cdn/{self.latest_patch}/data/en_US/champion.json"
        logger.info(f"Downloading latest champions file: '{self.get_champions_file()}'")

        old_file = glob("api/champions-*.json")[0]

        try:
            response_json = requests.get(url).json()
            f_out = open(self.get_champions_file(), "w", encoding="utf-8")
            json.dump(response_json, f_out)
            remove(old_file)
        except requests.exceptions.RequestException:
            logger.error("Exception when getting newest champions.json file from Riot API.")

    def get_champion_portraits(self):
        base_url = f"http://ddragon.leagueoflegends.com/cdn/{self.latest_patch}/img/champion"

        with open(self.get_champions_file(), encoding="utf-8") as fp:
            champion_data = json.load(fp)
            for champ_name in champion_data["data"]:
                champ_id = int(champion_data["data"][champ_name]["key"])
                filename = self.get_champ_portrait_path(champ_id)
                if exists(filename):
                    continue

                url = f"{base_url}/{champ_name}.png"
                logger.info(f"Downloading champion portrait for '{champ_name}'")

                try:
                    data = requests.get(url, stream=True)
                    with open(filename, "wb") as fp:
                        for chunk in data.iter_content(chunk_size=128):
                            fp.write(chunk)

                except requests.exceptions.RequestException:
                    logger.error(f"Exception when getting champion portrait for {champ_name} from Riot API.")

                sleep(0.5)

    def get_champion_splashes(self):
        base_url = f"http://ddragon.leagueoflegends.com/cdn/img/champion/loading"

        with open(self.get_champions_file(), encoding="utf-8") as fp:
            champion_data = json.load(fp)
            for champ_name in champion_data["data"]:
                champ_id = int(champion_data["data"][champ_name]["key"])
                filename = self.get_champ_splash_path(champ_id)
                if exists(filename):
                    continue

                url = f"{base_url}/{champ_name}_0.jpg"
                logger.info(f"Downloading champion splash for '{champ_name}'")

                try:
                    data = requests.get(url, stream=True)
                    with open(filename, "wb") as fp:
                        for chunk in data.iter_content(chunk_size=128):
                            fp.write(chunk)

                except requests.exceptions.RequestException:
                    logger.error(f"Exception when getting champion splash for {champ_name} from Riot API.")

                sleep(0.5)

    def get_champion_data(self):
        base_url = f"https://ddragon.leagueoflegends.com/cdn/{self.latest_patch}/data/en_US/champion"

        with open(self.get_champions_file(), encoding="utf-8") as fp:
            champion_data = json.load(fp)
            for champ_name in champion_data["data"]:
                champ_id = int(champion_data["data"][champ_name]["key"])

                filename = self.get_champ_data_path(champ_id)
                if exists(filename):
                    continue

                url = f"{base_url}/{champ_name}.json"
                logger.info(f"Downloading champion data for '{champ_name}'")

                try:
                    data = requests.get(url, stream=True)
                    with open(filename, "wb") as fp:
                        for chunk in data.iter_content(chunk_size=128):
                            fp.write(chunk)

                except requests.exceptions.RequestException:
                    logger.error(f"Exception when getting champion data for {champ_name} from Riot API.")

                sleep(0.5)


    def make_request(self, endpoint, api_route, *params, ignore_errors=[]):
        req_string = endpoint
        for index, param in enumerate(params):
            req_string = req_string.replace("{" + str(index) + "}", str(param))

        full_url = api_route + req_string
        logger.debug(f"URL: {full_url}")

        token_header = {"X-Riot-Token": self.config.riot_key}
        response = requests.get(full_url, headers=token_header)

        if response.status_code != 200 and response.status_code not in ignore_errors:
            logger.bind(
                url=full_url,
                response=response.text,
                status_code=response.status_code 
            ).error("Error during Riot API request")

        return response

    def get_summoner_id(self, summ_name):
        endpoint = "/lol/summoner/v4/summoners/by-name/{0}"
        response = self.make_request(endpoint, API_PLATFORM, summ_name)
        if response.status_code != 200:
            return None

        return response.json()["id"]

    def get_active_game(self, summ_id):
        endpoint = "/lol/spectator/v4/active-games/by-summoner/{0}"
        try:
            response = self.make_request(endpoint, API_PLATFORM, summ_id, ignore_errors=[404])
            if response.status_code != 200:
                return None

        except (requests.ConnectionError, requests.RequestException):
            return None

        return response.json()

    def get_game_details(self, game_id, tries=0):
        endpoint = "/lol/match/v5/matches/{0}"
        response = self.make_request(endpoint, API_REGION, f"EUW1_{game_id}")

        if response.status_code != 200:
            if tries > 0:
                sleep(30)
                return self.get_game_details(game_id, tries-1)

            else:
                endpoint = "/lol/match/v4/matches/{0}"
                response = self.make_request(endpoint, API_PLATFORM, game_id)

                if response.status_code != 200:
                    return None

                return response.json()

        data = response.json()["info"]
        duration = data["gameDuration"]
        data["gameDuration"] = duration if "gameEndTimestamp" in data else duration / 1000 

        return data

    def get_game_timeline(self, game_id, tries=0):
        endpoint = "/lol/match/v5/matches/{0}/timeline"

        response = self.make_request(endpoint, API_REGION, f"EUW1_{game_id}")
        if response.status_code != 200:
            if tries > 0:
                sleep(30)
                return self.get_game_timeline(game_id, tries-1)
            else:
                return None

        return response.json()["info"]

    def get_champion_mastery(self, summoner_id):
        endpoint = "/lol/champion-mastery/v4/champion-masteries/by-summoner/{0}"
        response = self.make_request(endpoint, API_PLATFORM, summoner_id)

        if response.status_code != 200:
            return None

        return response.json()

    def get_champ_name(self, champ_id):
        return self.champ_names.get(champ_id)

    def get_champ_portrait_path(self, champ_id):
        return f"{self.champ_portraits_path}/{champ_id}.png"

    def get_champ_splash_path(self, champ_id):
        return f"{self.champ_splash_path}/{champ_id}.png"

    def get_champ_data_path(self, champ_id):
        return f"{self.champ_data_path}/{champ_id}.json"

    def try_find_champ(self, name):
        search_name = name.strip().lower().replace("_", " ")
        candidates = []
        for champ_id in self.champ_names:
            lowered = self.champ_names[champ_id].lower()
            if search_name in lowered:
                candidates.append(champ_id)
                break

            # Remove apostrophe and period from name.
            if search_name in lowered.replace("'", "").replace(".", ""):
                candidates.append(champ_id)

        return candidates[0] if len(candidates) == 1 else None

    def get_map_name(self, map_id):
        with open("api/maps.json", encoding="utf-8") as fp:
            map_data = json.load(fp)
            for map_info in map_data:
                if map_info["mapId"] == map_id:
                    return map_info["mapName"]

        return None

    def map_is_sr(self, map_id):
        with open("api/maps.json", encoding="utf-8") as fp:
            map_data = json.load(fp)
            for map_info in map_data:
                if map_info["mapId"] == map_id:
                    return map_info["mapName"] in ("Summoner's Rift", "Nexus Blitz")

        return False

    def is_urf(self, gamemode):
        return gamemode == "URF"

    def is_clash(self, queue_id):
        return queue_id == 700
