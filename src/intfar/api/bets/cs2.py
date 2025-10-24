from intfar.api.betting import BettingHandler, BetResolver, Bet
from intfar.api.game_stats import GameStats, get_outlier

class CS2BetResolver(BetResolver):
    def resolve_game_outcome(self):
        bet_outcomes = ["game_loss", "game_tie", "game_win"]
        index = bet_outcomes.index(self.bet.event_id) - 1
        return self.game_stats.win == index

    def resolve_intfar_reason(self):
        reason_str = self.game_stats.intfar_reason
        reasons = ["intfar_kda", "intfar_mvp", "intfar_adr", "intfar_score"]
        index = reasons.index(self.bet.event_id)

        return self.resolve_has_intfar() and reason_str[index] == "1"

    def resolve_doinks_reason(self):
        doinks = {
            player_stats.disc_id: player_stats.doinks
            for player_stats in self.game_stats.filtered_player_stats
        }
        reasons = [
            "doinks_kda",
            "doinks_kills",
            "doinks_headshot",
            "doinks_adr",
            "doinks_utility",
            "doinks_mvp",
            "doinks_entries",
            "doinks_ace"
            "doinks_clutch"
            "doinks_ace_clutch"
        ]
        index = reasons.index(self.bet.event_id)

        if self.target_id is not None:
            return self.target_id in doinks and doinks[self.target_id][index] == "1"

        return any(doinks[disc_id][index] == "1" for disc_id in doinks)

    def resolve_stats(self):
        stat = self.bet.event_id.split("_")[1]
        stat_outlier_ties = get_outlier(
            self.game_stats.filtered_player_stats, stat, asc=False, include_ties=True
        )

        if stat_outlier_ties is None:
            return False

        return any(self.target_id == stats.disc_id for stats in stat_outlier_ties) and len(stat_outlier_ties) == 1

    @property
    def should_resolve_with_game_outcome(self) -> list[str]:
        return ["game_win", "game_tie", "game_loss"]

    @property
    def should_resolve_with_intfar_reason(self):
        return ["intfar_kda", "intfar_mvp", "intfar_adr", "intfar_score"]

    @property
    def should_resolve_with_doinks_reason(self):
        return [
            "doinks_kda",
            "doinks_kills",
            "doinks_headshot",
            "doinks_adr",
            "doinks_utility",
            "doinks_mvp",
            "doinks_entries",
            "doinks_ace"
            "doinks_clutch"
            "doinks_ace_clutch"
        ]

    @property
    def should_resolve_with_stats(self):
        return [
            "most_kills",
            "highest_kda"
            "highest_accuracy"
            "highest_utility_damage"
            "most_flash_assists"
        ]

class CS2BettingHandler(BettingHandler):
    @property
    def all_bets(self) -> list[Bet]:
        return super().all_bets + [
            Bet("game_win", "winning the game", Bet.TARGET_INVALID, 2),
            Bet("game_tie", "tieing the game", Bet.TARGET_INVALID, 2),
            Bet("game_loss", "losing the game", Bet.TARGET_INVALID, 2),
            Bet("intfar_kda", "someone being Int-Far by low KDA", Bet.TARGET_OPTIONAL, 4),
            Bet("intfar_mvp", "someone being Int-Far by no MVPs", Bet.TARGET_OPTIONAL, 10),
            Bet("intfar_adr", "someone being Int-Far by low ADR", Bet.TARGET_OPTIONAL, 30),
            Bet("intfar_score", "someone being Int-Far by low score", Bet.TARGET_OPTIONAL, 20),
            Bet("doinks_kda", "someone being awarded doinks for high KDA", Bet.TARGET_OPTIONAL, 10),
            Bet("doinks_kills", "someone being awarded doinks for many kills", Bet.TARGET_OPTIONAL, 10),
            Bet("doinks_headshot", "someone being awarded doinks for high headshot percentage", Bet.TARGET_OPTIONAL, 25),
            Bet("doinks_adr", "someone being awarded doinks for high ADR", Bet.TARGET_OPTIONAL, 25),
            Bet("doinks_utility", "someone being awarded doinks for high utility damage", Bet.TARGET_OPTIONAL, 20),
            Bet("doinks_mvp", "someone being awarded doinks for many MVPs", Bet.TARGET_OPTIONAL, 25),
            Bet("doinks_entries", "someone being awarded doinks for many entry frags", Bet.TARGET_OPTIONAL, 25),
            Bet("doinks_ace", "someone being awarded doinks for getting an ace", Bet.TARGET_OPTIONAL, 30),
            Bet("doinks_clutch", "someone being awarded doinks for clutching a 1v4", Bet.TARGET_OPTIONAL, 40),
            Bet("doinks_ace_clutch", "someone being awarded doinks for clutching a 1v5", Bet.TARGET_OPTIONAL, 100),
            Bet("most_kills", "someone getting the most kills", Bet.TARGET_REQUIRED, 1),
            Bet("highest_kda", "someone having the highest KDA", Bet.TARGET_REQUIRED, 1),
            Bet("highest_accuracy", "someone having the highest accuracy", Bet.TARGET_REQUIRED, 1),
            Bet("highest_utility_damage", "someone having the highest utility_damage", Bet.TARGET_REQUIRED, 1),
            Bet("most_flash_assists", "someone having the most flash assists", Bet.TARGET_REQUIRED, 1),
        ]

    def get_bet_resolver(self, bet: Bet, game_stats: GameStats, target_id: int = None) -> BetResolver:
        return CS2BetResolver(bet, game_stats, target_id)
