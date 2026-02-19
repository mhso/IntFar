from glob import glob
from intfar.api.game_apis.lol import RiotAPIClient
from intfar.api.game_apis.mocks.httpx_client import MockAsyncClient
from intfar.api.config import Config

class MockRiotAPI(RiotAPIClient):
    def __init__(self, game: str, config: Config):
        super().__init__(game, config)
        self.match_history = []

    def _create_http_client(self):
        return MockAsyncClient()

    def get_latest_patch(self):
        champ_file = glob(f"{self.config.resources_folder}/champions-*.json")[-1]
        return champ_file.split("-")[1].replace(".json", "")

    def get_latest_data(self):
        self.latest_patch = self.get_latest_patch()
        self.initialize_champ_dicts()

    async def get_match_history(self, puuid, date_from = None, date_to = None, game_type = "ranked"):
        return self.match_history
