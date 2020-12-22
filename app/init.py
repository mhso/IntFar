from flask import Flask
from flask_cors import CORS
from logging.config import dictConfig

def create_app():
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
    from app.routes import index
    web_app.register_blueprint(index.start_page, url_prefix=root)
    web_app.config['TESTING'] = True
    web_app.config["DATABASE"] = "database.db"
    web_app.secret_key = open("app/static/secret.txt").readline()

    return web_app
