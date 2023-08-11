from glob import glob
import importlib
import os
from api.util import SUPPORTED_GAMES
from game_stats import GameStatsParser

_GAME_DATA_MODULES = map(lambda x: x.replace(".py", ""), glob("api/game_data/*.py"))
GAME_STAT_PARSERS: dict[str, GameStatsParser] = {}

for module_name in _GAME_DATA_MODULES:
    module_key = os.path.basename(module_name)
    if module_key not in SUPPORTED_GAMES:
        continue

    module = importlib.import_module(module_name.replace("\\", ".").replace("/", "."))
    for subclass in GameStatsParser.__subclasses__():
        if hasattr(module, subclass.__name__):
            GAME_STAT_PARSERS[module_key] = subclass
            break

def get_awards_handler(game, raw_data, all_users) -> GameStatsParser:
    return GAME_STAT_PARSERS[game](game, raw_data, all_users)
