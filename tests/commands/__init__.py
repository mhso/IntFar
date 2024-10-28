from src.api.util import SUPPORTED_GAMES
from src.api.meta_database import DEFAULT_GAME

def get_games():
    games = [game for game in SUPPORTED_GAMES if game != DEFAULT_GAME]
    games.append(None)

    return games
