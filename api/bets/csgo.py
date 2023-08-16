from api.betting import BettingHandler, BetResolver, Bet
from api.game_stats import GameStats, get_outlier

class CSGOBetResolver(BetResolver):
    def resolve_intfar_reason(self):
        pass

    def resolve_doinks_reason(self):
        pass

    def resolve_stats(self):
        pass

    def should_resolve_with_intfar_reason(self):
        pass

    def should_resolve_with_doinks_reason(self):
        pass

    def should_resolve_with_stats(self):
        pass

class CSGOBettingHandler(BettingHandler):
    @property
    def all_bets(self) -> list[Bet]:
        return super().all_bets + [
            Bet("most_kills", "someone getting the most kills", Bet.TARGET_REQUIRED, 1),
            Bet("highest_kda", "someone having the highest KDA", Bet.TARGET_REQUIRED, 1),
        ]

    def get_bet_resolver(self, bet: Bet, game_stats: GameStats, target_id: int = None) -> BetResolver:
        return CSGOBetResolver(bet, game_stats, target_id)
