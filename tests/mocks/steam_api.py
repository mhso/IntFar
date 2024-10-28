from src.api.config import Config
from src.api.game_apis.cs2 import SteamAPIClient
from tests.mocks.httpx_client import MockAsyncClient

class MockSteamAPI(SteamAPIClient):
    def __init__(self, game: str, config: Config):
        self.httpx_client = MockAsyncClient()
        super().__init__(game, config)

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
