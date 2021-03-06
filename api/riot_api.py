from time import sleep
from glob import glob
from os import remove
from os.path import exists
import json
import requests

API_ROUTE = "https://euw1.api.riotgames.com"

class APIClient:
    def __init__(self, config):
        self.config = config
        self.latest_patch = self.get_latest_patch()
        if not exists(self.get_champions_file()):
            self.get_latest_champions_file()

    def get_champions_file(self):
        return f"api/champions-{self.latest_patch}.json"

    def get_latest_patch(self):
        url = "https://ddragon.leagueoflegends.com/api/versions.json"
        try:
            response_json = requests.get(url).json()
            return response_json[0]
        except requests.exceptions.RequestException as exc:
            self.config.log("Exception when getting newest game version!")
            self.config.log(exc)
            return None

    def get_latest_champions_file(self):
        url = f"http://ddragon.leagueoflegends.com/cdn/{self.latest_patch}/data/en_US/champion.json"
        self.config.log(f"Downloading latest champions file: '{self.get_champions_file()}'")

        old_file = glob("api/champions-*.json")[0]

        try:
            response_json = requests.get(url).json()
            f_out = open(self.get_champions_file(), "w", encoding="utf-8")
            json.dump(response_json, f_out)
            remove(old_file)
        except requests.exceptions.RequestException as exc:
            self.config.log("Exception when getting newest champions.json file!")
            self.config.log(exc)

    def make_request(self, endpoint, *params):
        req_string = endpoint
        for index, param in enumerate(params):
            req_string = req_string.replace("{" + str(index) + "}", str(param))
        token_header = {"X-Riot-Token": self.config.riot_key}
        response = requests.get(API_ROUTE + req_string, headers=token_header)
        return response

    def get_summoner_id(self, summ_name):
        endpoint = "/lol/summoner/v4/summoners/by-name/{0}"
        response = self.make_request(endpoint, summ_name)
        if response.status_code != 200:
            return None
        return response.json()["id"]

    def get_active_game(self, summ_id):
        endpoint = "/lol/spectator/v4/active-games/by-summoner/{0}"
        response = self.make_request(endpoint, summ_id)
        if response.status_code != 200:
            return None
        return response.json()

    def get_game_details(self, game_id, tries=0):
        endpoint = "/lol/match/v4/matches/{0}"
        response = self.make_request(endpoint, game_id)
        if response.status_code != 200:
            if tries == 0:
                return None
            sleep(10)
            return self.get_game_details(game_id, tries - 1) # Try again.
        return response.json()

    def get_champ_name(self, champ_id):
        champions_file = self.get_champions_file()
        if champions_file is None:
            return None

        with open(champions_file, encoding="UTF-8") as fp:
            champion_data = json.load(fp)
            for champ_name in champion_data["data"]:
                if int(champion_data["data"][champ_name]["key"]) == champ_id:
                    return champion_data["data"][champ_name]["name"]
        return None

    def get_map_name(self, map_id):
        with open("api/maps.json", encoding="UTF-8") as fp:
            map_data = json.load(fp)
            for map_info in map_data:
                if map_info["mapId"] == map_id:
                    return map_info["mapName"]
        return None

    def is_good_map(self, map_id):
        with open("api/maps.json", encoding="UTF-8") as fp:
            map_data = json.load(fp)
            for map_info in map_data:
                if map_info["mapId"] == map_id:
                    return map_info["mapName"] in ("Summoner's Rift", "Nexus Blitz")
        return False

    def is_clash(self, queue_id):
        return queue_id == 700
