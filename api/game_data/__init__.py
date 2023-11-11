from api.util import find_subclasses_in_dir
from api.game_stats import GameStatsParser, GameStats, PlayerStats

_PATH = "api/game_data"
_GAME_STAT_PARSERS: dict[str, GameStatsParser] = find_subclasses_in_dir(_PATH, GameStatsParser)
_GAME_STATS_HOLDERS: dict[str, GameStats] = find_subclasses_in_dir(_PATH, GameStats)
_PLAYER_STATS_HOLDERS: dict[str, PlayerStats] = find_subclasses_in_dir(_PATH, PlayerStats)

def get_stat_parser(game, raw_data, api_client, all_users, guild_id) -> GameStatsParser:
    return _GAME_STAT_PARSERS[game](game, raw_data, api_client, all_users, guild_id)

def stats_from_database(game, database, api_client, all_users, guild_id, game_id=None) -> list[GameStats]:
    return get_stat_parser(game, None, api_client, all_users, guild_id).parse_from_database(database, game_id)

def get_stats_for_game(game) -> list[str]:
    return _GAME_STATS_HOLDERS[game].stats_to_save()

def get_stats_for_player(game) -> list[str]:
    return _PLAYER_STATS_HOLDERS[game].stats_to_save()

def get_stat_quantity_descriptions(game) -> dict[str, tuple[str, str]]:
    return _PLAYER_STATS_HOLDERS[game].stat_quantity_desc()

def get_formatted_stat_names(game) -> dict[str,  str]:
    return _PLAYER_STATS_HOLDERS[game].formatted_stat_names()

def get_formatted_stat_value(game, stat, value) -> dict[str,  str]:
    return _PLAYER_STATS_HOLDERS[game].get_formatted_stat_value(stat, value)

def get_empty_game_data(game) -> GameStats:
    return _GAME_STATS_HOLDERS[game](game, 0, 0, 0, 0, 0, [], [])
