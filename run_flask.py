import json
from logging import Logger, ERROR
from logging.handlers import TimedRotatingFileHandler

from gevent.pywsgi import WSGIServer

from app import init

class RedirectStderr(object):

    def __init__(self, logger):
        self.logger = logger

    def write(self, msg):
        # Just in-case you want to write to both stderr and another log file
        #super(RedirectStderr, self).write(msg)
        if msg and msg.endswith('\n'):
            msg = msg[:-1]

        self.logger.error(msg)

    def close(self):
        super(RedirectStderr, self).close()

logger = Logger("WSGI_Error", ERROR)
handler = TimedRotatingFileHandler("log/wsgi_error.log", "d", 7, 0, encoding="utf-8")
logger.addHandler(TimedRotatingFileHandler("log/wsgi_error.log", "d", 7, 0, encoding="utf-8"))

import sys
sys.stderr = RedirectStderr(logger)

def run_app(database, bet_handler, riot_api, config, bot_pipe):
    application = init.create_app(database, bet_handler, riot_api, config, bot_pipe)
    application.static_folder = 'static'

    # Run on HTTPS (with SSL) when on production environment.
    ssl_args = {}
    if config.env == "production":
        with open("resources/auth.json", "r", encoding="utf-8") as fp:
            data = json.load(fp)
            key_file = data["sslKey"]
            cert_file = data["sslCert"]

        ssl_args = {
            "keyfile": key_file,
            "certfile": cert_file
        }

    with open("../flask_ports.json", "r", encoding="utf-8") as fp:
        port_map = json.load(fp)
        port = port_map["intfar"]

    try:
        WSGIServer(('', port), application, log=sys.stdout, **ssl_args).serve_forever()
    except KeyboardInterrupt:
        config.log("Stopping Flask web app...")
