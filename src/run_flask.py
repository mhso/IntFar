from argparse import ArgumentParser
from multiprocessing.connection import Connection
from multiprocessing import Lock

from mhooge_flask.logging import logger
from mhooge_flask import init
from mhooge_flask.init import Route, SocketIOServerWrapper

from intfar.app import util
from intfar.app.routes import errors as route_errors
from intfar.api.util import GUILD_IDS, SUPPORTED_GAMES
from intfar.api.game_apis import get_api_client
from intfar.api.game_api_client import GameAPIClient
from intfar.api.game_databases import get_database_client
from intfar.api.meta_database import MetaDatabase
from intfar.api.bets import get_betting_handler
from intfar.api.game_database import GameDatabase
from intfar.api.betting import BettingHandler
from intfar.api.config import Config

def run_app(
    port: int,
    config: Config,
    meta_database: MetaDatabase,
    game_databases: dict[str, GameDatabase],
    bet_handlers: dict[str, BettingHandler],
    api_clients: dict[str, GameAPIClient],
    bot_pipe: Connection
):
    # Define URL routes
    static_routes = [
        Route("about", "about_page", "about"),
        Route("verify", "verify_page", "verify"),
        Route("soundboard", "soundboard_page", "soundboard"),
        Route("lan", "lan_page", "lan"),
        Route("lists", "lists_page", "lol/lists"),
        Route("register_cs2", "register_cs2_page", "cs2/register"),
        Route("jeoparty", "jeopardy_contestant_page", "jeopardy"),
    ]

    # Dynamic routes that depend on which game is chosen
    game_routes = []
    for game in SUPPORTED_GAMES:
        game_route = Route("games", f"{game}_blueprint", f"{game}")
        game_routes += [
            Route("index", "start_page", parent_route=game_route),
            Route("users", "user_page", "user", parent_route=game_route),
            Route("betting", "betting_page", "betting", parent_route=game_route),
            Route("doinks", "doinks_page", "doinks", parent_route=game_route),
            Route("stats", "stats_page", "stats", parent_route=game_route),
            Route("api", "api_page", "api", parent_route=game_route),
        ]

    app_name = "intfar"

    # Create Flask app.
    web_app = init.create_app(
        app_name,
        "/intfar/",
        static_routes + game_routes,
        meta_database,
        root_folder="intfar/app",
        server_cls=SocketIOServerWrapper,
        game_databases=game_databases,
        propagate_exceptions=False,
        app_config=config,
        bet_handlers=bet_handlers,
        bot_conn=bot_pipe,
        current_game=None,
        logged_in_users={},
        game_api_clients=api_clients,
        active_game={guild_id: {} for guild_id in GUILD_IDS},
        game_prediction={},
        user_count=0,
        conn_map={},
        conn_lock=Lock(),
        max_content_length=1024 * 512, # 500 KB limit for uploaded sounds
        now_playing=None,
        jeopardy_data={"contestants": {}, "state": None},
        jeopardy_buzz_lock=Lock(),
        jeopardy_join_lock=Lock(),
        jeopardy_power_lock=Lock(),
        bingo_events={},
        league_events=[],
        league_game_start=None,
        league_events_lock=Lock(),
        exit_code=0
    )

    # Misc. routing handling.
    web_app.before_request(util.before_request)
    web_app.register_error_handler(500, route_errors.handle_internal_error)
    web_app.register_error_handler(404, route_errors.handle_missing_page_error)

    try:
        init.run_app(web_app, app_name, port)
    except KeyboardInterrupt:
        logger.info("Stopping Flask web app...")

if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-p", "--port", default=5000, type=int)
    args = parser.parse_args()

    config = Config()
    meta_database = MetaDatabase(config)
    game_databases = {game: get_database_client(game, config) for game in SUPPORTED_GAMES}
    bet_handlers = {game: get_betting_handler(game, config, meta_database, game_databases[game]) for game in SUPPORTED_GAMES}
    api_clients = {"lol": get_api_client("lol", config), "cs2": None}

    run_app(args.port, config, meta_database, game_databases, bet_handlers, api_clients, None)
