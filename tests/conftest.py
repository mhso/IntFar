import pytest

from src.api.config import Config
from src.api.meta_database import MetaDatabase
from src.api.game_databases import get_database_client
from src.api.game_monitors import get_game_monitor
from src.api.bets import get_betting_handler
from src.api.game_apis.mocks.riot_api import MockRiotAPI
from src.api.game_apis.mocks.steam_api import MockSteamAPI
from src.api.util import SUPPORTED_GAMES
from src.discbot.commands.util import ADMIN_DISC_ID
from src.run_command import create_client

_TEST_USERS = [
    ADMIN_DISC_ID, 2, 3, 4, 5, 6
]
_GAME_USERS = {
    "lol": [
        {"player_name": "Senile Felines", "player_id": "10", "puuid": "100"},
        {"player_name": "Slugger", "player_id": "20", "puuid": "200"},
        {"player_name": "Murt", "player_id": "30", "puuid": "300"},
        {"player_name": "Eddie Smurphy", "player_id": "40", "puuid": "400"},
        {"player_name": "Nønø", "player_id": "50", "puuid": "500"},
    ],
    "cs2": [
        {"player_name": "Say wat", "player_id": "10", "match_auth_code": "100", "latest_match_token": "abc"},
        {"player_name": "Slugger", "player_id": "20", "match_auth_code": "200", "latest_match_token": "abc"},
        {"player_name": "Murt", "player_id": "30", "match_auth_code": "300", "latest_match_token": "abc"},
        {"player_name": "Zikzak", "player_id": "40", "match_auth_code": "400", "latest_match_token": "abc"},
    ]
}

@pytest.fixture()
def config():
    config = Config()
    config.static_folder = f"{config.src_folder}/app/static"
    config.database_folder += "/test"
    config.env = "test"

    yield config

@pytest.fixture()
def meta_database(config):
    meta_database = MetaDatabase(config)
    meta_database.clear_tables()
    for disc_id in _TEST_USERS:
        meta_database.add_user(disc_id)

    yield meta_database

    meta_database.clear_tables()

@pytest.fixture()
def game_databases(config):
    game_databases = {}
    for game in SUPPORTED_GAMES:
        database = get_database_client(game, config)
        database.clear_tables()
        for disc_id, game_params in zip(_TEST_USERS, _GAME_USERS[game]):
            database.add_user(disc_id, **game_params)

        game_databases[game] = database

    yield game_databases

    for game in game_databases:
        game_databases[game].clear_tables()

@pytest.fixture()
def api_clients(config):
    api_clients = {
        "lol": MockRiotAPI("lol", config),
        "cs2": MockSteamAPI("cs2", config),
    }

    yield api_clients

@pytest.fixture()
def game_monitors(config, meta_database, game_databases, api_clients):
    yield {
        game: get_game_monitor(game, config, meta_database, game_databases[game], api_clients[game])
        for game in SUPPORTED_GAMES
    }

@pytest.fixture()
def betting_handlers(config, meta_database, game_databases):
    betting_handlers = {}
    for game in SUPPORTED_GAMES:
        betting_handlers[game] = get_betting_handler(game, config, meta_database, game_databases[game])

    yield betting_handlers

@pytest.fixture()
def discord_client(config, meta_database, game_databases):
    yield create_client(config, meta_database, game_databases)
