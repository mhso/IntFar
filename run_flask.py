from gevent.pywsgi import WSGIServer
from app import init

def run_app(database, bet_handler, riot_api, config, bot_pipe):
    application = init.create_app(database, bet_handler, riot_api, config, bot_pipe)
    application.static_folder = 'static'
    server = WSGIServer(('', 5000), application)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        config.log("Stopping Flask web app...")
