from time import sleep
from api.game_api.cs2 import SteamAPIClient

from test.runner import TestRunner, test
from api.config import Config
from api.database import Database
from api.proxy import ProxyManager

class TestWrapper(TestRunner):
    def __init__(self):
        super().__init__()
        conf = Config()
        db = Database(conf)
        db.clear_command_queue()
        self.steam_process = None
        self.proxy_manager = None
        self.proxy = None
        self.before_all(config=conf, database=db)

    def before_all(self, **test_args):
        super().before_all(**test_args)

        self.config.steam_2fa_code = input("Steam 2FA Code: ")
        self.proxy_manager = ProxyManager(SteamAPIClient, "cs2", self.database, self.config)
        self.proxy = self.proxy_manager.create_proxy()

    def after_all(self):
        self.proxy_manager.close()

    @test
    def test_get_map_name(self):
        map_name = self.proxy.get_map_name("dust2")
        self.assert_equals(map_name, "Dust II", "Correct map name")

    @test
    def test_match_info(self):
        match_token = "CSGO-EAcYr-PnXWK-CfHHM-WyofA-8TryM"
        data = self.proxy.get_game_details(match_token)
