from multiprocessing import Pipe, Process
from multiprocessing.connection import wait
from time import sleep

from api.game_api.cs2 import SteamAPIClient
from test.runner import TestRunner, test
from api.config import Config
from api.database import Database
from api.proxy import ProxyManager

def send_from_proc(proxy, conn):
    tries = 10
    success = 0
    for _ in range(tries):
        logged_in = proxy.is_logged_in()
        if logged_in:
            success += 1

    conn.send(success)

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
    def test_account_id(self):
        steam_id = 76561197970416015
        account_id = self.proxy.get_account_id(steam_id)
    
        self.assert_equals(type(account_id), int, "Account ID is int")
        self.assert_equals(account_id, 10150287, "Account ID is correct")

    @test
    def test_stress(self):
        conn_1_1, conn_1_2 = Pipe()
        conn_2_1, conn_2_2 = Pipe()

        p_1 = Process(target=send_from_proc, args=(self.proxy, conn_1_2))
        p_2 = Process(target=send_from_proc, args=(self.proxy, conn_2_2))

        p_1.start()
        p_2.start()

        timeout = 60
        count = 0
        sleep_time = 0.5
        responses_recieved = 0
        while count < timeout:
            count += sleep_time
            sleep(sleep_time)

            for response in wait([conn_1_1, conn_2_1], timeout=0.01):
                self.assert_equals(response, 10, "Correct count of succesful commands")
                responses_recieved += 1
                if responses_recieved == 2:
                    return

        p_1.kill()
        p_2.kill()

        while any(p.exitcode is not None for p in (p_1, p_2)):
            sleep(0.1)

        self.fail("Timeout!")
