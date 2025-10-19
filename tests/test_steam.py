from multiprocessing import Pipe, Process
from multiprocessing.connection import wait
from time import sleep

import pytest

from src.api.game_apis.cs2 import SteamAPIClient
from src.api.config import Config
from src.api.meta_database import MetaDatabase
from src.api.game_databases.cs2 import CS2GameDatabase
from src.api.proxy import ProxyManager

def send_from_proc(proxy, conn):
    tries = 10
    success = 0
    for _ in range(tries):
        print("before", flush=True)
        logged_in = proxy.is_logged_in()
        print("after", logged_in, flush=True)
        if logged_in:
            success += 1

    conn.send(success)

@pytest.fixture(scope="module")
def metadatabase():
    conf = Config()
    return MetaDatabase(conf)

@pytest.fixture(scope="module")
def steam_proxy(metadatabase: MetaDatabase):
    config = Config()
    proxy_manager = ProxyManager(SteamAPIClient, "cs2", metadatabase, config)

    yield proxy_manager.create_proxy()

    proxy_manager.kill()

@pytest.fixture(autouse=True)
def clear_db(metadatabase: MetaDatabase):
    metadatabase.clear_command_queue()

def test_get_map_name(steam_proxy: SteamAPIClient):
    map_name = steam_proxy.get_map_name("dust2")
    assert map_name == "Dust II", "Correct map name"

def test_account_id(steam_proxy: SteamAPIClient):
    steam_id = 76561197970416015
    account_id = steam_proxy.get_account_id(steam_id)

    assert type(account_id) == int, "Account ID is int"
    assert account_id == 10150287, "Account ID is correct"

@pytest.mark.asyncio
async def test_get_player_names_for_user(steam_proxy: SteamAPIClient):
    disc_id = 172757468814770176
    config = Config()
    database = CS2GameDatabase("cs2", config)
    user = database.game_users[disc_id]
    names = await steam_proxy.get_player_names_for_user(user)

    assert type(names) == list, "Names list is list"
    assert names == ["Murt"], "Names list is correct"

def test_stress(steam_proxy: SteamAPIClient):
    conn_1_1, conn_1_2 = Pipe()
    conn_2_1, conn_2_2 = Pipe()

    p_1 = Process(target=send_from_proc, args=(steam_proxy, conn_1_2))
    p_2 = Process(target=send_from_proc, args=(steam_proxy, conn_2_2))

    p_1.start()
    p_2.start()

    timeout = 60
    count = 0
    sleep_time = 0.5
    responses_recieved = 0
    while count < timeout:
        count += sleep_time
        sleep(sleep_time)

        for conn in wait([conn_1_1, conn_2_1], timeout=0.01):
            response = conn.recv()
            assert response == 10, "Correct count of succesful commands"
            responses_recieved += 1
            if responses_recieved == 2:
                return

    p_1.kill()
    p_2.kill()

    while any(p.exitcode is not None for p in (p_1, p_2)):
        sleep(0.1)

    pytest.fail("Timeout!")

def test_property(steam_proxy: SteamAPIClient):
    count = steam_proxy.playable_count

    print(count)
