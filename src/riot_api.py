from time import sleep
import json
import requests

API_ROUTE = "https://euw1.api.riotgames.com"

class APIClient:
    def __init__(self, config):
        self.config = config

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
        with open("champions.json", encoding="UTF-8") as fp:
            champion_data = json.load(fp)
            for champ_name in champion_data["data"]:
                if int(champion_data["data"][champ_name]["key"]) == champ_id:
                    return champion_data["data"][champ_name]["name"]
        return None

    def is_summoners_rift(self, map_id):
        with open("maps.json", encoding="UTF-8") as fp:
            map_data = json.load(fp)
            for map_info in map_data:
                if map_info["mapId"] == map_id:
                    return map_info["mapName"] == "Summoner's Rift"
        return False
