from time import sleep
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
        return response.json()["gameId"]

    def get_game_details(self, game_id, tries=0):
        endpoint = "/lol/match/v4/matches/{0}"
        response = self.make_request(endpoint, game_id)
        if response.status_code != 200:
            if tries == 0:
                return None
            sleep(0.2)
            return self.get_game_details(game_id, tries - 1) # Try again.
        return response.json()
