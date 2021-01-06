from flask import Flask
from api import riot_api
from flask_cors import CORS
from logging.config import dictConfig

def create_app(database, bet_handler, riot_api, conf, bot_pipe):
    dictConfig({
        'version': 1,
        'formatters': {'default': {
            'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
        }},
        'handlers': {'wsgi': {
            'class': 'logging.StreamHandler',
            'stream': 'ext://flask.logging.wsgi_errors_stream',
            'formatter': 'default'
        }},
        'root': {
            'level': 'INFO',
            'handlers': ['wsgi']
        }
    })
    web_app = Flask(__name__)
    CORS(web_app)
    root = "/intfar/"

    # Set up the blueprints for all the pages/routes.
    from app.routes import index, users, verify, betting, doinks, stats, errors
    web_app.register_blueprint(index.start_page, url_prefix=root)
    web_app.register_blueprint(users.user_page, url_prefix=root + "user/")
    web_app.register_blueprint(verify.verify_page, url_prefix=root + "verify/")
    web_app.register_blueprint(betting.betting_page, url_prefix=root + "betting/")
    web_app.register_blueprint(doinks.doinks_page, url_prefix=root + "doinks/")
    web_app.register_blueprint(stats.stats_page, url_prefix=root + "stats/")
    web_app.register_error_handler(500, errors.handle_internal_error)
    web_app.register_error_handler(404, errors.handle_missing_page_error)

    # Set up Flask lifetime variables.
    web_app.config['PROPAGATE_EXCEPTIONS'] = False
    web_app.config["APP_CONFIG"] = conf
    web_app.config["DATABASE"] = database
    web_app.config["BET_HANDLER"] = bet_handler
    web_app.config["BOT_CONN"] = bot_pipe
    web_app.config["LOGGED_IN_USERS"] = {}
    web_app.config["RIOT_API"] = riot_api
    web_app.config["ACTIVE_GAME"] = None

    web_app.secret_key = open("app/static/secret.txt").readline()

    return web_app
