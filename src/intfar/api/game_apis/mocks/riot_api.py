from glob import glob
from intfar.api.config import Config
from intfar.api.game_apis.lol import RiotAPIClient
from intfar.api.game_apis.mocks.httpx_client import MockAsyncClient

class MockRiotAPI(RiotAPIClient):
    def __init__(self, game: str, config: Config):
        self.httpx_client = MockAsyncClient()
        super().__init__(game, config)

    def get_latest_patch(self):
        champ_file = glob(f"{self.config.resources_folder}/champions-*.json")[-1]
        return champ_file.split("-")[1].replace(".json", "")

    def get_latest_data(self):
        self.latest_patch = self.get_latest_patch()
        self.initialize_champ_dicts()
