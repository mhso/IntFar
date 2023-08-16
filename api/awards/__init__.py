from api.util import find_subclasses_in_dir
from api.award_qualifiers import AwardQualifiers

_GAME_AWARD_HANDLERS: dict[str, AwardQualifiers] = find_subclasses_in_dir("api/awards", AwardQualifiers)

def get_awards_handler(game, config, parsed_game_stats) -> AwardQualifiers:
    return _GAME_AWARD_HANDLERS[game](config, parsed_game_stats)

def get_intfar_reasons(game):
    return _GAME_AWARD_HANDLERS[game].INTFAR_REASONS()

def get_intfar_criterias_desc(game):
    return _GAME_AWARD_HANDLERS[game].INTFAR_CRITERIAS_DESC()

def get_doinks_reasons(game):
    return _GAME_AWARD_HANDLERS[game].DOINKS_REASONS()
