import flask

from api.util import SUPPORTED_GAMES

for game in SUPPORTED_GAMES:
    locals()[f"{game}_blueprint"] = flask.Blueprint(game, __name__, template_folder="templates")
