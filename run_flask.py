import json

from gevent.pywsgi import WSGIServer

from app import init

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

    try:
        WSGIServer(('', 5000), application, **ssl_args).serve_forever()
    except KeyboardInterrupt:
        config.log("Stopping Flask web app...")
