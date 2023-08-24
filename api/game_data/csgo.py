from dataclasses import dataclass

from awpy.analytics.stats import player_stats as awpy_player_stats

from api.game_stats import GameStats, PlayerStats, GameStatsParser

@dataclass
class CSGOPlayerStats(PlayerStats):
    mvps: int = None
    score: int = None
    headshot_pct: int = None
    adr: int = None
    utility_damage: int = None
    enemies_flashed: int = None
    teammates_flashed: int = None
    flash_assists: int = None
    team_kills: int = None
    suicides: int = None
    accuray: int = None
    entries: int = None
    triples: int = None
    quads: int = None
    pentas: int = None
    one_v_ones: int = None
    one_v_twos: int = None
    one_v_threes: int = None
    one_v_fours: int = None
    one_v_fives: int = None
    rank: str = None

    @classmethod
    def STATS_TO_SAVE(cls):
        return super().STATS_TO_SAVE() + [
            "mvps",
            "score",
            "hsp",
            "adr",
            "ud",
            "ef",
        ]

    @classmethod
    def STAT_QUANTITY_DESC(cls):
        stat_quantities = dict(super().STAT_QUANTITY_DESC())
        stat_quantities.update(
            mvps=("most", "fewest"),
            score=("highest", "lowest"),
            hsp=("highest", "lowest"),
            adr=("highest", "lowest"),
            ud=("most", "least"),
            ef=("most", "fewest"),
        )
        return stat_quantities

@dataclass
class CSGOGameStats(GameStats):
    map_name: str = None
    started_t: bool = None
    rounds_us: int = None
    rounds_them: int = None
    long_match: bool = None

    @classmethod
    def STATS_TO_SAVE(cls):
        return super().STATS_TO_SAVE() + [
            "map_name",
            "started_t",
            "rounds_us",
            "rounds_them",
            "long_match",
        ]

    def get_finished_game_summary(self, disc_id: int) -> str:
        return super().get_finished_game_summary(disc_id)

class CSGOGameStatsParser(GameStatsParser):
    def parse_data(self) -> GameStats:
        player_stats = awpy_player_stats(self.raw_data["gameRounds"])

        for rank_entry in self.raw_data["matchmakingRanks"]:
            steam_id = rank_entry["steamID"]
            player_stats[steam_id]["rank"] = rank_entry["rankOld"]

        started_t = False

        t_side_players = [player["steamID"] for player in self.raw_data["gameRounds"][0]["tSide"]["players"]]
        for steam_id in t_side_players:
            if any(steam_id in self.all_users[disc_id].ingame_id for disc_id in self.all_users):
                started_t = True
                break

        players_on_our_team = {player["steam_id"] for player in self.raw_data["gameRounds"][0]["tSide" if started_t else "ctSide"]["players"]}

        players_in_game = []
        for steam_id in player_stats:
            for disc_id in self.all_users:
                if steam_id in self.all_users[disc_id].ingame_id:
                    user_game_data = {
                        "disc_id": disc_id,
                        "steam_name": player_stats[steam_id]["playerName"],
                        "steam_id": steam_id,
                    }
                    player_stats[steam_id]["disc_id"] = disc_id
                    players_in_game.append(user_game_data)
                    break

        rounds_t = self.raw_data["gameRounds"][-1]["endTScore"]
        rounds_ct = self.raw_data["gameRounds"][-1]["endCTScore"]

        kills_by_our_team = sum(
            player_stats[steam_id]["kills"]
            for steam_id in player_stats
            if player_stats["steamID"] in players_on_our_team
        )

        rounds_us = rounds_t if started_t else rounds_ct
        rounds_them = rounds_ct if started_t else rounds_t
        win_score = 1 if rounds_us > rounds_them else -1
        if rounds_us == rounds_them:
            win_score = 0

        all_player_stats = []
        for steam_id in player_stats:
            player_data = player_stats[steam_id]
            parsed_player_stats = CSGOPlayerStats(
                game_id=self.raw_data["matchID"],
                disc_id=player_data["disc_id"],
                kills=player_data["kills"],
                deaths=player_data["deaths"],
                assists=player_data["assists"],
            )
            all_player_stats.append(parsed_player_stats)

        return CSGOGameStats(
            game=self.game,
            game_id=self.raw_data["matchID"],
            timestamp=self.raw_data["timestamp"],
            duration=self.raw_data["duration"],
            win=win_score,
            guild_id=self.guild_id,
            kills_by_our_team=kills_by_our_team,
            players_in_game=players_in_game,
            all_player_stats=all_player_stats,
            map_name=self.raw_data["mapName"].split("_")[1],
            started_t=started_t,
            rounds_us=rounds_us,
            rounds_them=rounds_them,
            long_match=self.raw_data["serverVars"]["maxRounds"] == 30
        )

    def get_active_game_summary(self, active_id, api_client) -> str:
        return None

    def parse_from_database(self, database, game_id: int) -> GameStats:
        return None
