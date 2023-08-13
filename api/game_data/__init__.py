from glob import glob
import importlib
import os
from api.util import SUPPORTED_GAMES
from api.game_stats import GameStatsParser, GameStats, PlayerStats

_GAME_DATA_MODULES = map(lambda x: x.replace(".py", ""), glob("api/game_data/*.py"))

_GAME_STAT_PARSERS: dict[str, GameStatsParser] = {}
for module_name in _GAME_DATA_MODULES:
    module_key = os.path.basename(module_name)
    if module_key not in SUPPORTED_GAMES:
        continue

    module = importlib.import_module(module_name.replace("\\", ".").replace("/", "."))
    for subclass in GameStatsParser.__subclasses__():
        if hasattr(module, subclass.__name__):
            _GAME_STAT_PARSERS[module_key] = subclass
            break

_GAME_STATS_HOLDERS: dict[str, GameStats] = {}
for module_name in _GAME_DATA_MODULES:
    module_key = os.path.basename(module_name)
    if module_key not in SUPPORTED_GAMES:
        continue

    module = importlib.import_module(module_name.replace("\\", ".").replace("/", "."))
    for subclass in GameStats.__subclasses__():
        if hasattr(module, subclass.__name__):
            _GAME_STATS_HOLDERS[module_key] = subclass
            break

_PLAYER_STATS_HOLDERS: dict[str, PlayerStats] = {}
for module_name in _GAME_DATA_MODULES:
    module_key = os.path.basename(module_name)
    if module_key not in SUPPORTED_GAMES:
        continue

    module = importlib.import_module(module_name.replace("\\", ".").replace("/", "."))
    for subclass in PlayerStats.__subclasses__():
        if hasattr(module, subclass.__name__):
            _PLAYER_STATS_HOLDERS[module_key] = subclass
            break

def get_stat_parser(game, raw_data, all_users) -> GameStatsParser:
    return _GAME_STAT_PARSERS[game](game, raw_data, all_users)

def get_stats_for_game(game) -> list[str]:
    return _GAME_STATS_HOLDERS[game].STATS_TO_SAVE()

def get_stats_for_player(game) -> list[str]:
    return _PLAYER_STATS_HOLDERS[game].STATS_TO_SAVE()

def get_stat_quantity_descriptions(game) -> dict[str, tuple[str, str]]:
    return _PLAYER_STATS_HOLDERS[game].STAT_QUANTITY_DESC()
