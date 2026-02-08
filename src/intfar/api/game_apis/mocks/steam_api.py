from intfar.api.config import Config
from intfar.api.game_apis.cs2 import SteamAPIClient
from intfar.api.game_apis.mocks.httpx_client import MockAsyncClient

class MockSteamAPI(SteamAPIClient):
    def __init__(self, game: str, config: Config):
        super().__init__(game, config)

    def _create_http_client(self):
        return MockAsyncClient()

    def _init_clients(self):
        pass

    def get_latest_data(self):
        self.map_names = {
            "cache": "Cache",
            "nuke": "Nuke",
            "inferno": "Inferno",
            "ancient": "Ancient",
            "dust2": "Dust II",
            "train": "Train",
            "vertigo": "Vertigo",
            "mirage": "Mirage",
            "anubis": "Anubis",
            "overpass": "Overpass"
        }

    def login(self):
        self.logged_on_once = True
