from api.util import find_subclasses_in_dir
from api.betting import BettingHandler

_BETTING_HANDLERS: dict[str, BettingHandler] = find_subclasses_in_dir("api/bets", BettingHandler)

def get_betting_handler(game, config, meta_database, game_database) -> BettingHandler:
    return _BETTING_HANDLERS[game](game, config, meta_database, game_database)
