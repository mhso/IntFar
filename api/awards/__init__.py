from glob import glob
import importlib
import os
from api.util import SUPPORTED_GAMES
from api.award_qualifiers import AwardQualifiers

_AWARD_QUALIFIER_MODULES = map(lambda x: x.replace(".py", ""), glob("api/awards/*.py"))
GAME_AWARD_HANDLERS: dict[str, AwardQualifiers] = {}

for module_name in _AWARD_QUALIFIER_MODULES:
    module_key = os.path.basename(module_name)
    if module_key not in SUPPORTED_GAMES:
        continue

    module = importlib.import_module(module_name.replace("\\", ".").replace("/", "."))
    for subclass in AwardQualifiers.__subclasses__():
        if hasattr(module, subclass.__name__):
            GAME_AWARD_HANDLERS[module_key] = subclass
            break

def get_awards_handler(game, config, parsed_game_stats) -> AwardQualifiers:
    return GAME_AWARD_HANDLERS[game](config, parsed_game_stats)

def get_intfar_reasons(game):
    return GAME_AWARD_HANDLERS[game].INTFAR_REASONS()

def get_intfar_criterias_desc(game):
    return GAME_AWARD_HANDLERS[game].INTFAR_CRITERIAS_DESC()

def get_doinks_reasons(game):
    return GAME_AWARD_HANDLERS[game].DOINKS_REASONS()
