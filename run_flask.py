from multiprocessing import Lock
from multiprocessing.connection import Connection

from mhooge_flask.logging import logger

from mhooge_flask import init
from mhooge_flask.init import Route

from app.util import before_request
from app.routes import errors as route_errors
from api.database import Database
from api.betting import BettingHandler
from api.riot_api import RiotAPIClient
from api.config import Config

def run_app(
    database: Database,
    bet_handlers: dict[str, BettingHandler],
    riot_api: RiotAPIClient,
    config: Config,
    bot_pipe: Connection
):
    # Define URL routes
    routes = [
        Route("index", "start_page"),
        Route("about", "about_page", "about"),
        Route("users", "user_page", "user"),
        Route("verify", "verify_page", "verify"),
        Route("betting", "betting_page", "betting"),
        Route("doinks", "doinks_page", "doinks"),
        Route("stats", "stats_page", "stats"),
        Route("soundboard", "soundboard_page", "soundboard"),
        Route("lan", "lan_page", "lan"),
        Route("lists", "lists_page", "lists"),
        Route("quiz", "quiz_page", "quiz"),
        Route("api", "api_page", "api"),
    ]

    app_name = "intfar"

    # Create Flask app.
    web_app = init.create_app(
        app_name,
        "/intfar/",
        routes,
        database,
        propagate_exceptions=False,
        app_config=config,
        bet_handlers=bet_handlers,
        bot_conn=bot_pipe,
        logged_in_users={},
        riot_api=riot_api,
        active_game={},
        game_prediction={},
        user_count=0,
        conn_map={},
        conn_lock=Lock(),
        max_content_length=1024 * 512, # 500 KB limit for uploaded sounds
        quiz_categories=set(),
        quiz_team_blue=True,
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
