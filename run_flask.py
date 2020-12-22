from gevent.pywsgi import WSGIServer
from app import init

def run_app():
    application = init.create_app()
    application.static_folder = 'app/static'
    #server = WSGIServer(('', 5500), application)
    #server.serve_forever()
    application.run(host=("0.0.0.0"), port=5500, extra_files=["app/static/style.css"], use_reloader=True)
