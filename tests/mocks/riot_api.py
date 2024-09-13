from src.api.game_apis.lol import RiotAPIClient

class MockRiotAPI(RiotAPIClient):
    def make_request(self, endpoint, api_route, *params, ignore_errors=...):
        return super().make_request(endpoint, api_route, *params, ignore_errors=ignore_errors)
