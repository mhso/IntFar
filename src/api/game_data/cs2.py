from dataclasses import dataclass
from datetime import datetime
from dateutil.relativedelta import relativedelta
from time import time
from typing import Union, cast, Literal, Optional

import pandas as pd
from awpy.demo import DemoParser

from mhooge_flask.logging import logger

from api.game_stats import GameStats, PlayerStats, GameStatsParser
from api.util import format_duration

RANKS = [
    "Unranked",
    "Silver 1",
    "Silver 2",
    "Silver 3",
    "Silver 4",
    "Silver Elite",
    "Silver Elite Master",
    "Gold Nova 1",
    "Gold Nova 2",
    "Gold Nova 3",
    "Gold Nova Master",
    "Master Guardian 1",
    "Master Guardian 2",
    "Master Guardian Elite",
    "Distinguished Master Guardian",
    "Legendary Eagle",
    "Legendary Eagle Master",
    "Supreme Master First Class",
    "The Global Elite"
]

# def other_side(side: Literal["CT", "T"]) -> Literal["T", "CT"]:
#     """Takes a cs2 side as input and returns the opposite side in the same formatting

#     Args:
#         side (string): A cs2 team side (t or ct all upper or all lower case)

#     Returns:
#         A string of the opposite team side in the same formatting as the input

#     Raises:
#         ValueError: Raises a ValueError if side not neither 'CT' nor 'T'"""
#     if side == "CT":
#         return "T"
#     elif side == "T":
#         return "CT"
#     raise ValueError("side has to be either 'CT' or 'T'")


# def awpy_player_stats(
#     game_rounds: list[GameRound], return_type: str = "json", selected_side: str = "all"
# ) -> Union[dict[str, PlayerStatistics], pd.DataFrame]:
#     """Generates a stats summary for a list of game rounds as produced by the DemoParser

#     Args:
#         game_rounds (list[GameRound]): List of game rounds as produced by the DemoParser
#         return_type (str, optional): Return format ("json" or "df"). Defaults to "json".
#         selected_side (str, optional): Which side(s) to consider. Defaults to "all".
#             Other options are "CT" and "T"

#     Returns:
#         Union[dict[str, PlayerStatistics],pd.Dataframe]: Dictionary or Dataframe containing player information
#     """
#     player_statistics: dict[str, PlayerStatistics] = {}
#     player_statistics = {}
#     selected_side = selected_side.upper()
#     if selected_side in {"CT", "T"}:
#         selected_side = cast(Literal["CT", "T"], selected_side)
#         active_sides: set[Literal["CT", "T"]] = {selected_side}
#     else:
#         active_sides = {"CT", "T"}
#     for r in game_rounds:
#         # Add players
#         kast: dict[str, dict[str, bool]] = {}
#         round_kills = {}
#         for side in [team.lower() + "Side" for team in active_sides]:
#             side = cast(Literal["ctSide", "tSide"], side)
#             for p in r[side]["players"] or []:
#                 player_key = p["playerName"] if p["steamID"] == 0 else str(p["steamID"])
#                 if player_key not in player_statistics:
#                     player_statistics[player_key] = {
#                         "steamID": p["steamID"],
#                         "playerName": p["playerName"],
#                         "teamName": r[side]["teamName"],
#                         "isBot": p["steamID"] == 0,
#                         "totalRounds": 0,
#                         "kills": 0,
#                         "deaths": 0,
#                         "kdr": 0,
#                         "assists": 0,
#                         "tradeKills": 0,
#                         "tradedDeaths": 0,
#                         "teamKills": 0,
#                         "suicides": 0,
#                         "flashAssists": 0,
#                         "totalDamageGiven": 0,
#                         "totalDamageTaken": 0,
#                         "totalTeamDamageGiven": 0,
#                         "adr": 0,
#                         "totalShots": 0,
#                         "shotsHit": 0,
#                         "accuracy": 0,
#                         "rating": 0,
#                         "kast": 0,
#                         "hs": 0,
#                         "hsPercent": 0,
#                         "firstKills": 0,
#                         "firstDeaths": 0,
#                         "utilityDamage": 0,
#                         "smokesThrown": 0,
#                         "flashesThrown": 0,
#                         "heThrown": 0,
#                         "fireThrown": 0,
#                         "enemiesFlashed": 0,
#                         "teammatesFlashed": 0,
#                         "blindTime": 0,
#                         "plants": 0,
#                         "defuses": 0,
#                         "kills0": 0,
#                         "kills1": 0,
#                         "kills2": 0,
#                         "kills3": 0,
#                         "kills4": 0,
#                         "kills5": 0,
#                         "attempts1v1": 0,
#                         "success1v1": 0,
#                         "attempts1v2": 0,
#                         "success1v2": 0,
#                         "attempts1v3": 0,
#                         "success1v3": 0,
#                         "attempts1v4": 0,
#                         "success1v4": 0,
#                         "attempts1v5": 0,
#                         "success1v5": 0,
#                     }
#                 player_statistics[player_key]["totalRounds"] += 1
#                 kast[player_key] = {}
#                 kast[player_key]["k"] = False
#                 kast[player_key]["a"] = False
#                 kast[player_key]["s"] = True
#                 kast[player_key]["t"] = False
#                 round_kills[player_key] = 0
#         # Calculate kills
#         players_killed: dict[Literal["CT", "T"], set[str]] = {
#             "T": set(),
#             "CT": set(),
#         }
#         is_clutching: set[Optional[str]] = set()
#         for k in r["kills"] or []:
#             killer_key = (
#                 str(k["attackerName"])
#                 if str(k["attackerSteamID"]) == 0
#                 else str(k["attackerSteamID"])
#             )
#             victim_key = (
#                 str(k["victimName"])
#                 if str(k["victimSteamID"]) == 0
#                 else str(k["victimSteamID"])
#             )
#             assister_key = (
#                 str(k["assisterName"])
#                 if str(k["assisterSteamID"]) == 0
#                 else str(k["assisterSteamID"])
#             )
#             flashthrower_key = (
#                 str(k["flashThrowerName"])
#                 if str(k["flashThrowerSteamID"]) == 0
#                 else str(k["flashThrowerSteamID"])
#             )
#             if k["victimSide"] in players_killed:
#                 players_killed[k["victimSide"]].add(victim_key)  # type: ignore[index]
#             # Purely attacker related stats
#             if (
#                 k["attackerSide"] in active_sides
#                 and killer_key in player_statistics
#                 and k["attackerSteamID"]
#             ):
#                 if not k["isSuicide"] and not k["isTeamkill"]:
#                     player_statistics[killer_key]["kills"] += 1
#                     round_kills[killer_key] += 1
#                     kast[killer_key]["k"] = True
#                 if k["isTeamkill"]:
#                     player_statistics[killer_key]["teamKills"] += 1
#                 if k["isHeadshot"]:
#                     player_statistics[killer_key]["hs"] += 1
#             # Purely victim related stats:
#             if victim_key in player_statistics and k["victimSide"] in active_sides:
#                 player_statistics[victim_key]["deaths"] += 1
#                 if victim_key not in kast:
#                     kast[victim_key] = {"k": False, "a": False, "s": False, "t": False}

#                 kast[victim_key]["s"] = False
#                 if k["isSuicide"]:
#                     player_statistics[victim_key]["suicides"] += 1
#             if (
#                 k["victimSide"] in active_sides
#                 # mypy does not understand that after the first part k["victimSide"] is Literal["CT", "T"]
#                 # and that `k["victimSide"].lower() + "Side"` leads to a Literal["ctSide", "tSide"]
#                 and len(r[k["victimSide"].lower() + "Side"]["players"] or [])  # type: ignore[literal-required]
#                 - len(players_killed[k["victimSide"]])  # type: ignore[literal-required, index]
#                 == 1
#             ):
#                 for player in r[k["victimSide"].lower() + "Side"]["players"]:  # type: ignore[literal-required]
#                     clutcher_key = (
#                         str(player["playermName"])
#                         if str(player["steamID"]) == 0
#                         else str(player["steamID"])
#                     )
#                     if (
#                         clutcher_key not in players_killed[k["victimSide"]]  # type: ignore[literal-required, index]
#                         and clutcher_key not in is_clutching
#                         and clutcher_key in player_statistics
#                     ):
#                         is_clutching.add(clutcher_key)
#                         enemies_alive = len(
#                             r[other_side(k["victimSide"]).lower() + "Side"]["players"] or []  # type: ignore
#                         ) - len(
#                             players_killed[other_side(k["victimSide"])]  # type: ignore
#                         )
#                         if enemies_alive > 0:
#                             player_statistics[clutcher_key][
#                                 f"attempts1v{enemies_alive}"  # type: ignore[literal-required]
#                             ] += 1
#                             if r["winningSide"] == k["victimSide"]:
#                                 player_statistics[clutcher_key][
#                                     f"success1v{enemies_alive}"  # type: ignore[literal-required]
#                                 ] += 1
#             if k["isTrade"]:
#                 # A trade is always onto an enemy
#                 # If your teammate kills someone and then you kill them
#                 # -> that is not a trade kill for you
#                 # If you kill someone and then yourself
#                 # -> that is not a trade kill for you
#                 if (
#                     k["attackerSide"] != k["victimSide"]
#                     and k["attackerSide"] in active_sides
#                     and killer_key in player_statistics
#                     and k["attackerSteamID"]
#                 ):
#                     player_statistics[killer_key]["tradeKills"] += 1
#                 # Enemies CAN trade your own death
#                 # If you force an enemy to teamkill their mate after your death
#                 # -> thats a traded death for you
#                 # If you force your killer to kill themselves (in their own molo/nade/fall)
#                 # -> that is a traded death for you
#                 traded_key = (
#                     k["playerTradedName"]
#                     if str(k["playerTradedSteamID"]) == 0
#                     else str(k["playerTradedSteamID"])
#                 )
#                 # In most cases the traded player is on the same team as the trader
#                 # However in the above scenarios the opposite can be the case
#                 # So it is not enough to know that the trading player and
#                 # their side is initialized
#                 if (
#                     k["playerTradedSide"] in active_sides
#                     and traded_key in player_statistics
#                     and k["playerTradedSteamID"]
#                 ):
#                     kast[traded_key]["t"] = True
#                     player_statistics[traded_key]["tradedDeaths"] += 1
#             if (
#                 k["assisterSteamID"]
#                 and k["assisterSide"] != k["victimSide"]
#                 and assister_key in player_statistics
#                 and k["assisterSide"] in active_sides
#             ):
#                 player_statistics[assister_key]["assists"] += 1
#                 kast[assister_key]["a"] = True
#             if (
#                 k["flashThrowerSteamID"]
#                 and k["flashThrowerSide"] != k["victimSide"]
#                 and flashthrower_key in player_statistics
#                 and k["flashThrowerSide"] in active_sides
#             ):
#                 player_statistics[flashthrower_key]["flashAssists"] += 1
#                 kast[flashthrower_key]["a"] = True

#             if k["isFirstKill"] and k["attackerSteamID"]:
#                 if (
#                     k["attackerSide"] in active_sides
#                     and killer_key in player_statistics
#                 ):
#                     player_statistics[killer_key]["firstKills"] += 1
#                 if k["victimSide"] in active_sides and victim_key in player_statistics:
#                     player_statistics[victim_key]["firstDeaths"] += 1

#         for d in r["damages"] or []:
#             attacker_key = (
#                 str(d["attackerName"])
#                 if str(d["attackerSteamID"]) == 0
#                 else str(d["attackerSteamID"])
#             )
#             victim_key = (
#                 str(d["victimName"])
#                 if str(d["victimSteamID"]) == 0
#                 else str(d["victimSteamID"])
#             )
#             # Purely attacker related stats
#             if (
#                 d["attackerSide"] in active_sides
#                 and attacker_key in player_statistics
#                 and d["attackerSteamID"]
#             ):
#                 if not d["isFriendlyFire"]:
#                     player_statistics[attacker_key]["totalDamageGiven"] += d[
#                         "hpDamageTaken"
#                     ]
#                 else:  # d["isFriendlyFire"]:
#                     player_statistics[attacker_key]["totalTeamDamageGiven"] += d[
#                         "hpDamageTaken"
#                     ]
#                 if d["weaponClass"] not in ["Unknown", "Grenade", "Equipment"]:
#                     player_statistics[attacker_key]["shotsHit"] += 1
#                 if d["weaponClass"] == "Grenade":
#                     player_statistics[attacker_key]["utilityDamage"] += d[
#                         "hpDamageTaken"
#                     ]
#             if (
#                 d["victimSteamID"]
#                 and victim_key in player_statistics
#                 and d["victimSide"] in active_sides
#             ):
#                 player_statistics[victim_key]["totalDamageTaken"] += d["hpDamageTaken"]

#         for w in r["weaponFires"] or []:
#             fire_key = (
#                 w["playerName"] if w["playerSteamID"] == 0 else str(w["playerSteamID"])
#             )
#             if fire_key in player_statistics and w["playerSide"] in active_sides:
#                 player_statistics[fire_key]["totalShots"] += 1
#         for f in r["flashes"] or []:
#             flasher_key = (
#                 str(f["attackerName"])
#                 if str(f["attackerSteamID"]) == 0
#                 else str(f["attackerSteamID"])
#             )
#             player_key = (
#                 str(f["playerName"])
#                 if str(f["playerSteamID"]) == 0
#                 else str(f["playerSteamID"])
#             )
#             if (
#                 f["attackerSteamID"]
#                 and flasher_key in player_statistics
#                 and f["attackerSide"] in active_sides
#             ):
#                 if f["attackerSide"] == f["playerSide"]:
#                     player_statistics[flasher_key]["teammatesFlashed"] += 1
#                 else:
#                     player_statistics[flasher_key]["enemiesFlashed"] += 1
#                     player_statistics[flasher_key]["blindTime"] += (
#                         0 if f["flashDuration"] is None else f["flashDuration"]
#                     )
#         for g in r["grenades"] or []:
#             thrower_key = (
#                 g["throwerName"]
#                 if g["throwerSteamID"] == 0
#                 else str(g["throwerSteamID"])
#             )
#             if (
#                 g["throwerSteamID"]
#                 and thrower_key in player_statistics
#                 and g["throwerSide"] in active_sides
#             ):
#                 if g["grenadeType"] == "Smoke Grenade":
#                     player_statistics[thrower_key]["smokesThrown"] += 1
#                 if g["grenadeType"] == "Flashbang":
#                     player_statistics[thrower_key]["flashesThrown"] += 1
#                 if g["grenadeType"] == "HE Grenade":
#                     player_statistics[thrower_key]["heThrown"] += 1
#                 if g["grenadeType"] in ["Incendiary Grenade", "Molotov"]:
#                     player_statistics[thrower_key]["fireThrown"] += 1
#         for b in r["bombEvents"] or []:
#             player_key = (
#                 b["playerName"] if b["playerSteamID"] == 0 else str(b["playerSteamID"])
#             )
#             if b["playerSteamID"] and player_key in player_statistics:
#                 if b["bombAction"] == "plant" and "T" in active_sides:
#                     player_statistics[player_key]["plants"] += 1
#                 if b["bombAction"] == "defuse" and "CT" in active_sides:
#                     player_statistics[player_key]["defuses"] += 1
#         for player, components in kast.items():
#             if any(components.values()):
#                 player_statistics[player]["kast"] += 1
#         for player, n_kills in round_kills.items():
#             if n_kills in range(6):  # 0, 1, 2, 3, 4, 5
#                 player_statistics[player][f"kills{n_kills}"] += 1  # type: ignore[literal-required]

#     for player in player_statistics.values():
#         player["kast"] = round(
#             100 * player["kast"] / player["totalRounds"],
#             1,
#         )
#         player["blindTime"] = round(player["blindTime"], 2)
#         player["kdr"] = round(
#             player["kills"] / player["deaths"]
#             if player["deaths"] != 0
#             else player["kills"],
#             2,
#         )
#         player["adr"] = round(
#             player["totalDamageGiven"] / player["totalRounds"],
#             1,
#         )
#         player["accuracy"] = round(
#             player["shotsHit"] / player["totalShots"]
#             if player["totalShots"] != 0
#             else 0,
#             2,
#         )
#         player["hsPercent"] = round(
#             player["hs"] / player["kills"] if player["kills"] != 0 else 0,
#             2,
#         )
#         impact = (
#             2.13 * (player["kills"] / player["totalRounds"])
#             + 0.42 * (player["assists"] / player["totalRounds"])
#             - 0.41
#         )
#         player["rating"] = (
#             0.0073 * player["kast"]
#             + 0.3591 * (player["kills"] / player["totalRounds"])
#             - 0.5329 * (player["deaths"] / player["totalRounds"])
#             + 0.2372 * (impact)
#             + 0.0032 * (player["adr"])
#             + 0.1587
#         )
#         player["rating"] = round(player["rating"], 2)

#     if return_type == "df":
#         return (
#             pd.DataFrame()
#             .from_dict(player_statistics, orient="index")
#             .reset_index(drop=True)
#         )
#     else:
#       return player_statistics

@dataclass
class CS2PlayerStats(PlayerStats):
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
    accuracy: int = None
    entries: int = None
    triples: int = None
    quads: int = None
    aces: int = None
    one_v_ones_tried: int = None
    one_v_ones_won: int = None
    one_v_twos_tried: int = None
    one_v_twos_won: int = None
    one_v_threes_tried: int = None
    one_v_threes_won: int = None
    one_v_fours_tried: int = None
    one_v_fours_won: int = None
    one_v_fives_tried: int = None
    one_v_fives_won: int = None
    rank: int = None

    @classmethod
    def stats_to_save(cls):
        return super().stats_to_save() + [
            "mvps",
            "score",
            "headshot_pct",
            "adr",
            "utility_damage",
            "enemies_flashed",
            "teammates_flashed",
            "flash_assists",
            "team_kills",
            "suicides",
            "accuracy",
            "entries",
            "triples",
            "quads",
            "aces",
            "one_v_ones_tried",
            "one_v_ones_won",
            "one_v_twos_tried",
            "one_v_twos_won",
            "one_v_threes_tried",
            "one_v_threes_won",
            "one_v_fours_tried",
            "one_v_fours_won",
            "one_v_fives_tried",
            "one_v_fives_won",
            "rank",
        ]

    @classmethod
    def stat_quantity_desc(cls):
        stat_quantities = dict(super().stat_quantity_desc())
        stat_quantities.update(
            mvps=("most", "fewest"),
            score=("highest", "lowest"),
            headshot_pct=("highest", "lowest"),
            adr=("highest", "lowest"),
            utility_damage=("most", "least"),
            enemies_flashed=("most", "fewest"),
            flash_assists=("most", "fewest"),
            team_kills=("most", "fewest"),
            suicides=("most", "fewest"),
            accuracy=("highest", "lowest"),
            entries=("most", "fewest"),
            triples=("most", "fewest"),
            quads=("most", "fewest"),
            aces=("most", "fewest"),
            one_v_ones_tried=("most", "fewest"),
            one_v_ones_won=("most", "fewest"),
            one_v_twos_tried=("most", "fewest"),
            one_v_twos_won=("most", "fewest"),
            one_v_threes_tried=("most", "fewest"),
            one_v_threes_won=("most", "fewest"),
            one_v_fours_tried=("most", "fewest"),
            one_v_fours_won=("most", "fewest"),
            one_v_fives_tried=("most", "fewest"),
            one_v_fives_won=("most", "fewest"),
        )
        return stat_quantities

    @classmethod
    def formatted_stat_names(cls):
        formatted = dict(super().formatted_stat_names())
        for stat in cls.stats_to_save():
            if stat in formatted:
                continue

            if stat == "cs":
                fmt_stat = "MVPs"
            elif stat == "adr":
                fmt_stat = stat.upper()
            elif stat == "team_kills":
                fmt_stat = "Teamkills"
            else:
                fmt_stat = " ".join(map(lambda s: s.capitalize(), stat.split("_")))

            formatted[stat] = fmt_stat

        return formatted

    @classmethod
    def get_formatted_stat_value(cls, stat, value) -> dict[str, str]:
        if isinstance(value, float) and stat in ("mvps", "score", "adr", "utility_damage"):
            return str(int(value))

        fmt_value = super().get_formatted_stat_value(stat, value)

        if stat == "headshot_pct":
            return fmt_value + "%"

        return fmt_value

@dataclass
class CS2GameStats(GameStats):
    map_id: str = None
    map_name: str = None
    started_t: bool = None
    rounds_us: int = None
    rounds_them: int = None
    cs2: bool = False
    biggest_lead: int = None
    biggest_deficit: int = None

    @classmethod
    def stats_to_save(cls):
        return super().stats_to_save() + [
            "map_id",
            "started_t",
            "rounds_us",
            "rounds_them",
        ]

    def get_finished_game_summary(self, disc_id: int) -> str:
        """
        Get a brief text that summaries a player's performance in a finished game.

        :param disc_id: Discord ID of the player for whom to get the summary for
        """
        player_stats: CS2PlayerStats = GameStats.find_player_stats(disc_id, self.filtered_player_stats)

        date = datetime.fromtimestamp(self.timestamp).strftime("%Y/%m/%d")
        dt_1 = datetime.fromtimestamp(time())
        dt_2 = datetime.fromtimestamp(time() + self.duration)
        fmt_duration = format_duration(dt_1, dt_2)

        return (
            f"{self.map_name} with a score of {player_stats.kills}/" +
            f"{player_stats.deaths}/{player_stats.assists} on {date} in a {fmt_duration} long game"
        )

class CS2GameStatsParser(GameStatsParser):
    def parse_data(self) -> GameStats:
        round_stats = self.raw_data["matches"][0]["roundstatsall"]
        demo_parsed = self.raw_data["demo_parse_status"] == "parsed"

        if demo_parsed:
            # Parse stats from demo if demo was valid/recent.
            # First determine if we started on t side
            started_t = False
            t_side_players = [player["steamID"] for player in self.raw_data["gameRounds"][0]["tSide"]["players"]]
            for steam_id in t_side_players:
                if any(int(steam_id) in self.all_users[disc_id].player_id for disc_id in self.all_users.keys()):
                    started_t = True
                    break

            both_teams_stats = parse_rounds()

            # Filter out players not on our team
            player_stats = {}
            for steam_id in both_teams_stats:
                if (int(steam_id) in t_side_players) ^ (not started_t):
                    player_stats[steam_id] = both_teams_stats[steam_id]

            for rank_entry in self.raw_data["matchmakingRanks"]:
                steam_id = str(rank_entry["steamID"])
                if steam_id in player_stats:
                    player_stats[steam_id]["rank"] = rank_entry["rankOld"]

            # Get players in game
            players_in_game = []
            for steam_id in player_stats:
                for disc_id in self.all_users.keys():
                    if int(steam_id) in self.all_users[disc_id].player_id:
                        user_game_data = {
                            "disc_id": disc_id,
                            "steam_name": player_stats[steam_id]["playerName"],
                            "steam_id": int(steam_id),
                        }
                        player_stats[steam_id]["disc_id"] = disc_id
                        players_in_game.append(user_game_data)
                        break

            # Get total rounds on t side and on ct side
            rounds_t = self.raw_data["gameRounds"][-1]["endTScore"]
            rounds_ct = self.raw_data["gameRounds"][-1]["endCTScore"]

            # Get our round count, enemy round count, and who won
            rounds_us = rounds_ct if started_t else rounds_t
            rounds_them = rounds_t if started_t else rounds_ct

            if rounds_us + rounds_them < 12: # Swap scores if game finished before halftime
                rounds_us, rounds_them = rounds_them, rounds_us

            win_score = 1 if rounds_us > rounds_them else -1
            if rounds_us == rounds_them:
                win_score = 0

            account_id_map = {self.api_client.get_account_id(int(steam_id)): steam_id for steam_id in player_stats}

            map_id = self.raw_data["mapName"].split("_")[-1]
            if not map_id:
                game_type = round_stats[-1]["reservation"]["gameType"]
                map_id = self.api_client.get_map_id(game_type)

            logger.bind(event="cs2_map_id").info(f"Game type: {game_type}, map ID: {map_id}")

        else: # Parse (a subset of) stats from basic game data
            # Get players in game from the round were most players are present (in case of disconnects)
            max_player_round = 0
            max_players = 0
            for index, round_data in enumerate(round_stats):
                players_in_round = len(round_data["reservation"]["accountIds"])
                if players_in_round > max_players:
                    max_players = players_in_round
                    max_player_round = index

            # Get users in game and map account ids to discord ids
            account_id_map = {}
            players_in_game = []
            started_t = False
            for disc_id in self.all_users.keys():
                for steam_id, steam_name in zip(self.all_users[disc_id].player_id, self.all_users[disc_id].player_name):
                    account_id = self.api_client.get_account_id(int(steam_id))
                    try:
                        index = round_stats[max_player_round]["reservation"]["accountIds"].index(account_id)
                        started_t = index > 4
                        account_id_map[account_id] = disc_id
                        user_game_data = {
                            "disc_id": disc_id,
                            "steam_name": steam_name,
                            "steam_id": int(steam_id),
                        }
                        players_in_game.append(user_game_data)
                        break

                    except ValueError:
                        pass

            game_type = round_data["reservation"]["gameType"]

            start_index = 5 if started_t else 0
            for account_id in round_stats[max_player_round]["reservation"]["accountIds"][start_index:start_index+5]:
                if account_id not in account_id_map:
                    account_id_map[account_id] = None

            round_data = round_stats[-1]
            account_ids = round_data["reservation"]["accountIds"]

            player_stats = {}
            for index, account_id in enumerate(round_stats[max_player_round]["reservation"]["accountIds"]):
                if started_t ^ (index < 5):
                    player_stats[account_id] = {"disc_id": account_id_map[account_id]}

            # Get kills, assists, deaths, and headshot percentage
            stats_to_collect = ["kills", "assists", "deaths", "enemyHeadshots"]
            for stat in stats_to_collect:
                source_stat = "enemyKills" if stat == "kills" else stat
                for index, stat_value in enumerate(round_data[source_stat]):
                    if started_t ^ (index < 5):
                        player_stats[account_ids[index]][stat] = stat_value

            for account_id in player_stats:
                player_stats[account_id]["hsPercent"] = player_stats[account_id]["enemyHeadshots"] / player_stats[account_id]["kills"]

            # Get total rounds on t side and on ct side
            rounds_ct = round_data["teamScores"][0]
            rounds_t = round_data["teamScores"][1]

            # Get our round count, enemy round count, and who won
            rounds_us = rounds_t if started_t else rounds_ct
            rounds_them = rounds_ct if started_t else rounds_t
            win_score = 1 if rounds_us > rounds_them else -1
            if rounds_us == rounds_them:
                win_score = 0

            # Get map ID
            map_id = self.api_client.get_map_id(game_type)
            print("game_type:", game_type, flush=True)
            print("map_id:", map_id, flush=True)

        # Get total kills by our teamn
        kills_by_our_team = sum(
            player_stats[key]["kills"]
            for key in player_stats
        )

        # Get MVPs for each player
        mvps = dict(zip(round_stats[-1]["reservation"]["accountIds"], round_stats[-1]["mvps"]))
        for account_id in mvps:
            if account_id in account_id_map:
                key = account_id_map[account_id] if demo_parsed else account_id 
                player_stats[key]["mvps"] = mvps[account_id]

        # Get scores of each player
        scores = dict(zip(round_stats[-1]["reservation"]["accountIds"], round_stats[-1]["scores"]))
        for account_id in scores:
            if account_id in account_id_map:
                key = account_id_map[account_id] if demo_parsed else account_id 
                player_stats[key]["scores"] = scores[account_id]

        # Get the biggest lead and deficit throughout the course of the game
        biggest_lead = 0
        biggest_deficit = 0
        for round_data in round_stats:
            rounds_ct = round_data["teamScores"][0]
            rounds_t = round_data["teamScores"][1]

            rounds_us = rounds_t if started_t else rounds_ct
            rounds_them = rounds_ct if started_t else rounds_t

            lead = rounds_us - rounds_them
            deficit = rounds_them - rounds_us

            if lead > biggest_lead:
                biggest_lead = lead
            elif deficit > biggest_deficit:
                biggest_deficit = deficit

        # Add it all to player stats
        all_player_stats = []
        for steam_or_account_id in player_stats:
            player_data = player_stats[steam_or_account_id]

            kda = (
                player_data["kills"] + player_data["assists"]
                if player_data["deaths"] == 0
                else (player_data["kills"] + player_data["assists"]) / player_data["deaths"]
            )
            kp = (
                100 if kills_by_our_team == 0
                else int((float(player_data["kills"] + player_data["assists"]) / float(kills_by_our_team)) * 100.0)
            )
            accuracy = player_data.get("accuracy")
            if accuracy is not None:
                accuracy = int(accuracy * 100)

            rank = player_data.get("rank")
            if rank is not None:
                rank = RANKS.index(player_data["rank"])

            parsed_player_stats = CS2PlayerStats(
                game_id=self.raw_data["matchID"],
                disc_id=player_data.get("disc_id"),
                player_id=steam_or_account_id,
                kills=player_data["kills"],
                deaths=player_data["deaths"],
                assists=player_data["assists"],
                kda=kda,
                kp=kp,
                mvps=player_data["mvps"],
                score=player_data["scores"],
                headshot_pct=int(player_data["hsPercent"] * 100),
                adr=player_data.get("adr"),
                utility_damage=player_data.get("utilityDamage"),
                enemies_flashed=player_data.get("enemiesFlashed"),
                teammates_flashed=player_data.get("teammatesFlashed"),
                flash_assists=player_data.get("flashAssists"),
                team_kills=player_data.get("teamKills"),
                suicides=player_data.get("suicides"),
                accuracy=accuracy,
                entries=player_data.get("firstKills"),
                triples=player_data.get("kills3"),
                quads=player_data.get("kills4"),
                aces=player_data.get("kills5"),
                one_v_ones_tried=player_data.get("attempts1v1"),
                one_v_ones_won=player_data.get("success1v1"),
                one_v_twos_tried=player_data.get("attempts1v2"),
                one_v_twos_won=player_data.get("success1v2"),
                one_v_threes_tried=player_data.get("attempts1v3"),
                one_v_threes_won=player_data.get("success1v3"),
                one_v_fours_tried=player_data.get("attempts1v4"),
                one_v_fours_won=player_data.get("success1v4"),
                one_v_fives_tried=player_data.get("attempts1v5"),
                one_v_fives_won=player_data.get("success1v5"),
                rank=rank,
            )
            all_player_stats.append(parsed_player_stats)

        timestamp = self.raw_data["matches"][0]["matchtime"]
        duration = round_stats[-1]["matchDuration"]
        map_name = self.api_client.get_map_name(map_id)

        return CS2GameStats(
            game=self.game,
            game_id=self.raw_data["matchID"],
            timestamp=timestamp,
            duration=duration,
            win=win_score,
            guild_id=self.guild_id,
            players_in_game=players_in_game,
            all_player_stats=all_player_stats,
            map_id=map_id,
            map_name=map_name,
            started_t=int(started_t),
            rounds_us=rounds_us,
            rounds_them=rounds_them,
            biggest_lead=biggest_lead,
            biggest_deficit=biggest_deficit
        )

    def parse_from_database(self, database, game_id: int = None) -> list[GameStats]:
        """
        Get data for a given game, or all games if `game_id` is None, from the database
        and return a list of GameStats objects with the game data.
        """
        all_game_stats, all_player_stats = CS2GameStats.get_stats_from_db(database, CS2PlayerStats, game_id)

        all_stats = []
        for game_stats, player_stats in zip(all_game_stats, all_player_stats):
            game_stats["map_name"] = self.api_client.get_map_name(game_stats["map_id"])

            all_player_stats = []
            players_in_game = []
            for disc_id in player_stats:
                player_stats[disc_id]["player_id"] = database.game_users[disc_id].player_id[0]
                all_player_stats.append(CS2PlayerStats(**player_stats[disc_id]))

                user_game_info = self.all_users[disc_id]
                game_info = {
                    "disc_id": disc_id,
                    "steam_name": user_game_info.player_name[0],
                    "steam_id": user_game_info.player_id[0],
                }
                players_in_game.append(game_info)

            all_stats.append(CS2GameStats(self.game, **game_stats, players_in_game=players_in_game, all_player_stats=all_player_stats))

        return all_stats

    def get_active_game_summary(self, active_id: int) -> str:
        """
        Get a description about a currently active game for a given player.

        :active_id: The Steam ID that we should extract data for in the game
        """
        other_players = []
        for disc_id in self.all_users.keys():
            for steam_id, player_name in zip(self.all_users[disc_id].player_id, self.all_users[disc_id].player_name):
                if steam_id != active_id and self.api_client.get_account_id(steam_id) in self.raw_data["accountIds"]:
                    other_players.append(player_name)

        game_start = self.raw_data["gameStartTime"]
        if "watchableMatchInfos" in self.raw_data:
            seconds = self.raw_data["watchableMatchInfos"][0]["tvTime"]

            now = datetime.now()
            game_start = now - relativedelta(seconds=seconds)

            dt_1 = datetime.fromtimestamp(game_start)
            dt_2 = datetime.fromtimestamp(now)
            fmt_duration = format_duration(dt_1, dt_2) + " "
        else:
            fmt_duration = ""

        map_name = self.api_client.get_map_name(self.raw_data["gameMap"])

        response = f"{fmt_duration}in a game on {map_name}.\n"

        if len(other_players) > 1:
            response += "He is playing with:"
            for other_name in other_players:
                response += f"\n - {other_name}"

        return response
