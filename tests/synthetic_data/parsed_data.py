import inspect

from src.api.game_data.lol import LoLGameStats, LoLPlayerStats
from src.api.game_data.cs2 import CS2GameStats, CS2PlayerStats

GAME_STATS_CLS = {
    "lol": LoLGameStats,
    "cs2": CS2GameStats
}

PLAYER_STATS_CLS = {
    "lol": LoLPlayerStats,
    "cs2": CS2PlayerStats
}

def _get_default_value(dtype: str):
    if dtype == "float":
        return 0.0
    if dtype == "int":
        return 0
    if dtype == "bool":
        return False
    elif dtype == "str":
        return ""

    return None

def _get_class_args(fields, cls):
    argspec = inspect.getfullargspec(cls.__init__)

    args = argspec[0]
    annotations = argspec[-1]
    positional_args = args[1:-len(argspec[3])]

    for arg in positional_args:
        if arg not in fields:
            fields[arg] = _get_default_value(annotations[arg].__name__)

    return fields

def create_synthetic_data(game, game_fields, player_fields):
    game_stats_cls = GAME_STATS_CLS[game]
    player_stats_cls = PLAYER_STATS_CLS[game]

    game_args = _get_class_args(game_fields, game_stats_cls)
    player_args = _get_class_args(player_fields, player_stats_cls)

    game_args["all_player_stats"] = player_stats_cls(**player_args)

    return game_stats_cls(**game_args)
