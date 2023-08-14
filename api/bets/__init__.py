from glob import glob
import importlib
import os
from api.util import SUPPORTED_GAMES
from api.betting import BettingHandler

_BETTING_HANDLER_MODULES = map(lambda x: x.replace(".py", ""), glob("api/bets/*.py"))
_BETTING_HANDLERS: dict[str, BettingHandler] = {}

for module_name in _BETTING_HANDLER_MODULES:
    module_key = os.path.basename(module_name)
    if module_key not in SUPPORTED_GAMES:
        continue

    module = importlib.import_module(module_name.replace("\\", ".").replace("/", "."))
    for subclass in BettingHandler.__subclasses__():
        if hasattr(module, subclass.__name__):
            _BETTING_HANDLERS[module_key] = subclass
            break

def get_betting_handler(game, config, database) -> BettingHandler:
    return _BETTING_HANDLERS[game](game, config, database)
