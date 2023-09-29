from multiprocessing.connection import Connection
from multiprocessing import Lock

from mhooge_flask.logging import logger

from mhooge_flask import init
from mhooge_flask.init import Route

from app.util import before_request
from app.routes import errors as route_errors
from api.util import GUILD_IDS, SUPPORTED_GAMES
from api.game_api_client import GameAPIClient
from api.database import Database
from api.betting import BettingHandler
from api.config import Config

def run_app(
    database: Database,
    bet_handlers: dict[str, BettingHandler],
    api_clients: dict[str, GameAPIClient],
    config: Config,
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
        Route("quiz", "quiz_page", "quiz"),
    ]

    # Dynamic routes that depend on which game is chosen
    game_routes = []
    for game in SUPPORTED_GAMES:
        game_route = Route("games", f"{game}_blueprint", f"/{game}")
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
        database,
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
        quiz_categories=set(),
        quiz_team_blue=True,
        now_playing=None,
        league_events=[],
        league_events_lock=Lock(),
        exit_code=0
    )

    # Misc. routing handling.
    web_app.before_request(before_request)
    web_app.register_error_handler(500, route_errors.handle_internal_error)
    web_app.register_error_handler(404, route_errors.handle_missing_page_error)

    ports_file = "../flask_ports.json"

    try:
        init.run_app(web_app, app_name, ports_file)
    except KeyboardInterrupt:
        logger.info("Stopping Flask web app...")
