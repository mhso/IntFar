from multiprocessing.connection import Connection
from multiprocessing import Lock

from mhooge_flask.logging import logger, WSGI_INFO_LOGGER, WSGI_ERROR_LOGGER
from mhooge_flask import init
from mhooge_flask.init import Route, ServerWrapper

from flask_socketio import SocketIO

import app.util
from app.routes import errors as route_errors
from api.util import GUILD_IDS, SUPPORTED_GAMES
from api.game_api_client import GameAPIClient
from api.meta_database import MetaDatabase
from api.game_database import GameDatabase
from api.betting import BettingHandler
from api.config import Config

class SocketIOServerWrapper(ServerWrapper):
    def create_handler(self):
        return app.util.socket_io

    def run(self):
        wsgi_args = {
            "log": WSGI_INFO_LOGGER,
            "error_log": WSGI_ERROR_LOGGER,
        }
        wsgi_args.update(**self.ssl_args)

        self.handler.run(
            self.app,
            self.host,
            self.port,
            **wsgi_args
        )

class SocketIOPatcher(SocketIO):
    def run(self, app, host: str | None = None, port: int | None = None, **kwargs):
        if host is None:
            host = '127.0.0.1'
        if port is None:
            server_name = app.config['SERVER_NAME']
            if server_name and ':' in server_name:
                port = int(server_name.rsplit(':', 1)[1])
            else:
                port = 5000

        app.debug = kwargs.pop('debug', app.debug)

        from gevent import pywsgi

        self.wsgi_server = pywsgi.WSGIServer((host, port), app, **kwargs)
        self.wsgi_server.serve_forever()

    def _handle_event(self, handler, message, namespace, sid, *args):
        try:
            super()._handle_event(handler, message, namespace, sid, *args)
        except:
            logger.exception("SocketIO error")

def run_app(
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
        Route("quiz", "quiz_page", "quiz"),
        Route("jeopardy_presenter", "jeopardy_presenter_page", "jeopardy/presenter"),
        Route("jeopardy_contestant", "jeopardy_contestant_page", "jeopardy"),
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

    app.util.socket_io = SocketIOPatcher()

    # Create Flask app.
    web_app = init.create_app(
        app_name,
        "/intfar/",
        static_routes + game_routes,
        meta_database,
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
        jeopardy_lock=Lock(),
        bingo_events={},
        league_events=[],
        league_events_lock=Lock(),
        exit_code=0
    )

    app.util.socket_io.init_app(web_app)

    # Misc. routing handling.
    web_app.before_request(app.util.before_request)
    web_app.register_error_handler(500, route_errors.handle_internal_error)
    web_app.register_error_handler(404, route_errors.handle_missing_page_error)

    ports_file = "../../flask_ports.json"

    try:
        init.run_app(web_app, app_name, ports_file, SocketIOServerWrapper)
    except KeyboardInterrupt:
        logger.info("Stopping Flask web app...")
