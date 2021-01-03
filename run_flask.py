from gevent.pywsgi import WSGIServer
from app import init

def run_app(database, bet_handler, config, bot_pipe):
    application = init.create_app(database, bet_handler, config, bot_pipe)
    application.static_folder = 'static'
    server = WSGIServer(('', 5000), application)
    server.serve_forever()
    #application.run(host=("0.0.0.0"), port=5500, extra_files=["app/static/style.css"], use_reloader=True)
