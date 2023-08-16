from api.betting import BettingHandler, BetResolver, Bet
from api.game_stats import GameStats, get_outlier

class LoLBetResolver(BetResolver):
    def resolve_intfar_reason(self):
        reason_str = self.game_stats.intfar_reason
        reasons = ["intfar_kda", "intfar_deaths", "intfar_kp", "intfar_vision"]
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
            "doinks_damage",
            "doinks_penta",
            "doinks_vision",
            "doinks_kp",
            "doinks_monsters",
            "doinks_cs"
        ]
        index = reasons.index(self.bet.event_id)

        if self.target_id is not None:
            return self.target_id in doinks and doinks[self.target_id][index] == "1"

        return any(doinks[disc_id][index] == "1" for disc_id in doinks)

    def resolve_stats(self):
        stat = self.bet.event_id.split("_")[1]
        most_kills_ties = get_outlier(
            self.game_stats.filtered_player_stats, stat, asc=False, include_ties=True
        )[0]

        return self.target_id in most_kills_ties and len(most_kills_ties) == 1

    @property
    def should_resolve_with_intfar_reason(self):
        return ["intfar_kda", "intfar_deaths", "intfar_kp", "intfar_vision"]

    @property
    def should_resolve_with_doinks_reason(self):
        return [
            "doinks_kda",
            "doinks_kills",
            "doinks_damage",
            "doinks_penta",
            "doinks_vision",
            "doinks_kp",
            "doinks_monsters",
            "doinks_cs"
        ]

    @property
    def should_resolve_with_stats(self):
        return ["most_kills", "most_damage", "most_kp", "highest_kda"]

class LoLBettingHandler(BettingHandler):
    @property
    def all_bets(self):
        return super().all_bets + [
            Bet("intfar_kda", "someone being Int-Far by low KDA", Bet.TARGET_OPTIONAL, 4),
            Bet("intfar_deaths", "someone being Int-Far by many deaths", Bet.TARGET_OPTIONAL, 4),
            Bet("intfar_kp", "someone being Int-Far by low KP", Bet.TARGET_OPTIONAL, 10),
            Bet("intfar_vision", "someone being Int-Far by low vision score", Bet.TARGET_OPTIONAL, 5),
            Bet("doinks_kda", "someone being awarded doinks for high KDA", Bet.TARGET_OPTIONAL, 7.5),
            Bet("doinks_kills", "someone being awarded doinks for many kills", Bet.TARGET_OPTIONAL, 10),
            Bet("doinks_damage", "someone being awarded doinks for high damage", Bet.TARGET_OPTIONAL, 150),
            Bet("doinks_penta", "someone being awarded doinks for getting a pentakill", Bet.TARGET_OPTIONAL, 100),
            Bet("doinks_vision", "someone being awarded doinks for high vision score", Bet.TARGET_OPTIONAL, 25),
            Bet("doinks_kp", "someone being awarded doinks for high KP", Bet.TARGET_OPTIONAL, 40),
            Bet("doinks_monsters", "someone being awarded doinks for securing all epic monsters", Bet.TARGET_OPTIONAL, 50),
            Bet("doinks_cs", "someone being awarded doinks for having more than 8 cs/min", Bet.TARGET_OPTIONAL, 10),
            Bet("most_kills", "someone getting the most kills", Bet.TARGET_REQUIRED, 1),
            Bet("most_damage", "someone doing the most damage", Bet.TARGET_REQUIRED, 1),
            Bet("most_kp", "someone having the highest kill participation", Bet.TARGET_REQUIRED, 1),
            Bet("highest_kda", "someone having the highest KDA", Bet.TARGET_REQUIRED, 1),
        ]

    def get_bet_resolver(self, bet: Bet, game_stats: GameStats, target_id: int = None) -> BetResolver:
        return LoLBetResolver(bet, game_stats, target_id)
