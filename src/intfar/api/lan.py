from datetime import datetime
from typing import Dict

from intfar.api.game_stats import PostGameStats
from intfar.api.game_data import get_stat_quantity_descriptions
from intfar.api.game_data.lol import LoLGameStats
from intfar.api.game_databases.lol import LoLGameDatabase
from intfar.api.util import GUILD_MAP

TESTING = False

class LANInfo:
    def __init__(self, start_time: float, end_time: float, participants: Dict[int, str], guild_name: str):
        self.start_time = start_time
        self.end_time = end_time
        self.participants = participants
        match guild_name:
            case "core": self.guild_name = "CoreNibbas"
            case "nibs": self.guild_name = "LeagueNibbas"
            case "circus": self.guild_name = "DanishCircus"

        self.guild_id = GUILD_MAP[guild_name]

LAN_PARTIES = {
    # "october_19": LANInfo(
    #     datetime(2019, 4, 12, 12, 0, 0).timestamp(),
    #     datetime(2019, 4, 13, 12, 0, 0).timestamp(),
    #     {
    #         115142485579137029: "Dave",
    #         274654800182902785: "Mogens",
    #         267401734513491969: "Gual",
    #         331082926475182081: "Muds",
    #         347489125877809155: "Nønø"
    #     },
    #     "nibs"
    # ),
    "august_20": LANInfo(
        datetime(2020, 8, 3, 14, 0, 0).timestamp(),
        datetime(2020, 8, 4, 12, 0, 0).timestamp(),
        {
            115142485579137029: "Dave",
            172757468814770176: "Murt",
            267401734513491969: "Gual",
            331082926475182081: "Muds",
            347489125877809155: "Nønø"
        },
        "nibs"
    ),
    "march_21": LANInfo(
        datetime(2021, 3, 31, 12, 0, 0).timestamp(),
        datetime(2021, 4, 1, 12, 0, 0).timestamp(),
        {
            115142485579137029: "Dave",
            172757468814770176: "Murt",
            267401734513491969: "Gual",
            331082926475182081: "Muds",
            347489125877809155: "Nønø"
        },
        "core"
    ),
    "october_21": LANInfo(
        datetime(2021, 10, 30, 14, 0, 0).timestamp(),
        datetime(2021, 10, 31, 12, 0, 0).timestamp(),
        {
            115142485579137029: "Dave",
            172757468814770176: "Murt",
            267401734513491969: "Gual",
            331082926475182081: "Muds",
            347489125877809155: "Nønø"
        },
        "core"
    ),
    "april_22": LANInfo(
        datetime(2022, 4, 15, 14, 0, 0).timestamp(),
        datetime(2022, 4, 16, 12, 0, 0).timestamp(),
        {
            115142485579137029: "Dave",
            172757468814770176: "Murt",
            267401734513491969: "Gual",
            331082926475182081: "Muds",
            347489125877809155: "Nønø"
        },
        "core"
    ),
    "september_23": LANInfo(
        datetime(2023, 9, 9, 14, 0, 0).timestamp(),
        datetime(2023, 9, 10, 18, 0, 0).timestamp(),
        {
            115142485579137029: "Dave",
            172757468814770176: "Murt",
            267401734513491969: "Gual",
            331082926475182081: "Muds",
            347489125877809155: "Nønø"
        },
        "core"
    ),
    "december_23": LANInfo(
        datetime(2023, 12, 30, 13, 0, 0).timestamp(),
        datetime(2023, 12, 31, 3, 0, 0).timestamp(),
        {
            115142485579137029: "Dave",
            172757468814770176: "Murt",
            267401734513491969: "Gual",
            331082926475182081: "Muds",
            347489125877809155: "Nønø"
        },
        "core"
    ),
    "april_24": LANInfo(
        datetime(2024, 4, 27, 10, 0, 0).timestamp(),
        datetime(2024, 4, 28, 10, 0, 0).timestamp(),
        {
            115142485579137029: "Dave",
            172757468814770176: "Murt",
            267401734513491969: "Gual",
            331082926475182081: "Muds",
            347489125877809155: "Nønø"
        },
        "core"
    ),
    "august_24": LANInfo(
        datetime(2024, 8, 17, 10, 0, 0).timestamp(),
        datetime(2024, 8, 18, 10, 0, 0).timestamp(),
        {
            115142485579137029: "Dave",
            172757468814770176: "Murt",
            267401734513491969: "Gual",
            331082926475182081: "Muds",
            347489125877809155: "Nønø"
        },
        "core"
    ),
    "february_25": LANInfo(
        datetime(2025, 2, 8, 11, 0, 0).timestamp(),
        datetime(2025, 2, 9, 12, 0, 0).timestamp(),
        {
            115142485579137029: "Dave",
            172757468814770176: "Murt",
            267401734513491969: "Gual",
            331082926475182081: "Muds",
            347489125877809155: "Nønø"
        },
        "core"
    ),
    "april_25": LANInfo(
        datetime(2025, 4, 26, 9, 0, 0).timestamp(),
        datetime(2025, 4, 27, 12, 0, 0).timestamp(),
        {
            115142485579137029: "Dave",
            172757468814770176: "Murt",
            267401734513491969: "Gual",
            331082926475182081: "Muds",
            347489125877809155: "Nønø"
        },
        "core"
    ),
    "august_25": LANInfo(
        datetime(2025, 8, 23, 8, 0, 0).timestamp(),
        datetime(2025, 8, 24, 14, 0, 0).timestamp(),
        {
            115142485579137029: "Dave",
            172757468814770176: "Murt",
            267401734513491969: "Gual",
            331082926475182081: "Muds",
            219497453374668815: "Thommy"
        },
        "nibs"
    ),
    "december_25": LANInfo(
        datetime(2025, 12, 20, 8, 0, 0).timestamp(),
        datetime(2025, 12, 21, 10, 0, 0).timestamp(),
        {
            115142485579137029: "Dave",
            172757468814770176: "Murt",
            267401734513491969: "Gual",
            331082926475182081: "Muds",
            347489125877809155: "Nønø"
        },
        "core"
    )
}
LATEST_LAN_PARTY: str = max(LAN_PARTIES.keys(), key=lambda k: LAN_PARTIES[k].start_time)

def is_lan_ongoing(timestamp: float, guild_id=None):
    lan_data = list(filter(
        lambda x: timestamp > LAN_PARTIES[x].start_time and timestamp < LAN_PARTIES[x].end_time,
        LAN_PARTIES
    ))

    if lan_data == []:
        return False

    latest_lan_info = LAN_PARTIES[lan_data[0]]

    # Check if guild_id matches, if given.
    return guild_id is None or guild_id == latest_lan_info.guild_id

def get_latest_lan_info():
    return LAN_PARTIES[LATEST_LAN_PARTY]

def get_tilt_value(recent_games):
    # Tilt value ranges from 0-12
    tilt_value = 0
    max_value = 12
    max_contribution = 4
    min_contribution = 1
    win_contribution = -0.75
    prev_result = -1
    streak = 1
    for index, result in enumerate(recent_games):
        tilt_contribution = max(index - (len(recent_games) - max_contribution - 1), min_contribution)
        if index > 0:
            if prev_result == result:
                streak += 1
            else:
                streak = 1

            tilt_contribution *= (streak // 2)

        if result == 1:
            tilt_contribution *= win_contribution

        tilt_value += tilt_contribution

        prev_result = result

    # Clamp value to between 0-12
    tilt_value = max(min(tilt_value, max_value), 0)

    colors = [
        "rgb(124, 252, 0)", "rgb(156, 252, 0)", "rgb(188, 253, 0)",
        "rgb(220, 253, 0)", "rgb(252, 253, 0)", "rgb(252, 223, 0)",
        "rgb(253, 191, 0)", "rgb(254, 159, 0)", "rgb(254, 128, 0)",
        "rgb(254, 96, 0)", "rgb(254, 64, 0)", "rgb(255, 0, 0)"
    ]
    color = colors[min(round(tilt_value), 11)]

    # Convert to percent.
    return int((tilt_value / max_value) * 100), color

def get_average_stats(database: LoLGameDatabase, lan_info: LANInfo):
    game = "lol"
    stat_quantity_desc = get_stat_quantity_descriptions(game)
    stats_to_get = list(stat_quantity_desc)

    stats_to_get.remove("first_blood")
    stats_to_get.remove("steals")

    all_stats = database.get_player_stats(
        stats_to_get,
        time_after=lan_info.start_time,
        time_before=lan_info.end_time,
        guild_id=lan_info.guild_id
    )

    stats_to_get.remove("player_id")
    stats_to_get.remove("disc_id")

    if all_stats == []:
        return None

    grouped_by_player = {}
    for stats in all_stats:
        disc_id = stats[0]
        if disc_id not in grouped_by_player:
            grouped_by_player[disc_id] = []

        grouped_by_player[disc_id].append(stats[2:])

    all_avg_stats = {key: [] for key in stats_to_get}
    for disc_id in grouped_by_player:
        avg_stats = [0 for _ in stats_to_get]

        for stat_tuple in grouped_by_player[disc_id]:
            for index, stat_value in enumerate(stat_tuple):
                avg_stats[index] += stat_value if stat_value is not None else 0

        for index, sum_value in enumerate(avg_stats):
            all_avg_stats[stats_to_get[index]].append((disc_id, sum_value / len(grouped_by_player[disc_id])))

    for key in all_avg_stats:
        reverse = False if key == "deaths" else True
        all_avg_stats[key].sort(key=lambda x: x[1], reverse=reverse)

    return all_avg_stats

# BINGO SOLVER FUNCS
class BingoSolver:
    def __init__(self, challenge_id: str, post_game_data: PostGameStats, progress: int):
        self.post_game_data = post_game_data
        self.progress = progress
        self.completed_by = None
        self.parsed_data: LoLGameStats = post_game_data.parsed_game_stats

        # Dynamically call function that resolves challenge with 'challenge_id'
        getattr(self, challenge_id)()

    def big_lead(self):
        gold_us = 0
        gold_them = 0
        participants = self.parsed_data.timeline_data["frames"][-1]["participantFrames"]
        for participant_id in participants:
            team_id = 100 if int(participant_id) < 6 else 200
            if team_id == self.parsed_data.team_id:
                gold_us += participants[participant_id]["totalGold"]
            else:
                gold_them += participants[participant_id]["totalGold"]

        if self.parsed_data.win == 1 and gold_us - gold_them >= 8000:
            self.progress = 1

    def bounty_gold(self):
        self.progress += sum(player.challenges["bountyGold"] for player in self.parsed_data.filtered_player_stats)

    def buff_steals(self):
        self.progress += sum(player.challenges["buffsStolen"] for player in self.parsed_data.filtered_player_stats)

    def damage_dealt(self):
        self.progress += sum(player.damage for player in self.parsed_data.filtered_player_stats)

    def dives(self):
        self.progress += sum(player.challenges["killsNearEnemyTurret"] for player in self.parsed_data.filtered_player_stats)

    def doinks(self):
        for player in self.parsed_data.filtered_player_stats:
            if player.doinks:
                self.progress += sum(map(int, player.doinks))

    def dragon_souls(self):
        for frame_data in self.parsed_data.timeline_data["frames"]:
            for event in frame_data.get("events", []):
                if (
                    event["type"] == "DRAGON_SOUL_GIVEN"
                    and event["teamId"] == self.parsed_data.team_id
                ):
                    self.progress += 1
                    return

    def early_baron(self):
        for frame_data in self.parsed_data.timeline_data["frames"]:
            for event in frame_data.get("events", []):
                if (
                    event["type"] == "ELITE_MONSTER_KILL"
                    and event["monsterType"] == "BARON_NASHOR"
                    and event.get("teamId", None) == self.parsed_data.team_id
                    and event["timestamp"] / 1000 / 60 < 28
                ):
                    self.progress = 1
                    return

    def elder_dragon(self):
        for frame_data in self.parsed_data.timeline_data["frames"]:
            for event in frame_data.get("events", []):
                if (
                    event["type"] == "ELITE_MONSTER_KILL"
                    and event.get("teamId") == self.parsed_data.team_id
                    and event["monsterType"] == "DRAGON"
                    and event["monsterSubType"] == "ELDER_DRAGON"
                ):
                    self.progress = 1
                    return

    def fast_win(self):
        if self.parsed_data.win == 1 and self.parsed_data.duration <= 22 * 60:
            self.progress = 1

    def flawless_ace(self):
        if any(player.challenges["flawlessAces"] for player in self.parsed_data.filtered_player_stats):
            self.progress = 1

    def fountain_kill(self):
        for player in self.parsed_data.filtered_player_stats:
            if player.challenges["takedownsInEnemyFountain"] > 0:
                self.progress = 1
                self.completed_by = player.disc_id
                return

    def invade_kills(self):
        self.progress += self.parsed_data.timeline_data["invade_kills"] + self.parsed_data.timeline_data["anti_invade_kills"]

    def jungle_doinks(self):
        for player in self.parsed_data.filtered_player_stats:
            if player.doinks and player.doinks[6] == "1":
                self.progress = 1
                self.completed_by = player.disc_id
                break

    def killing_sprees(self):
        self.progress += sum(player.challenges["killingSprees"] for player in self.parsed_data.filtered_player_stats)

    def kills(self):
        self.progress += sum(player.kills for player in self.parsed_data.filtered_player_stats)

    def outnumbered_kills(self):
        self.progress += sum(player.challenges["outnumberedKills"] for player in self.parsed_data.filtered_player_stats)

    def atakhan_kills(self):
        self.progress += self.parsed_data.our_atakhan_kills

    def solo_kills(self):
        self.progress += sum(player.challenges["soloKills"] for player in self.parsed_data.filtered_player_stats)

    def spells_casted(self):
        self.progress += sum(player.challenges["abilityUses"] for player in self.parsed_data.filtered_player_stats)

    def spells_dodged(self):
        self.progress += sum(player.challenges["skillshotsDodged"] for player in self.parsed_data.filtered_player_stats)

    def spells_hit(self):
        self.progress += sum(player.challenges["skillshotsHit"] for player in self.parsed_data.filtered_player_stats)

    def steals(self):
        for player in self.parsed_data.filtered_player_stats:
            if player.steals > 0:
                self.progress += player.steals
                self.completed_by = player.disc_id

    def two_barons(self):
        if self.parsed_data.our_baron_kills >= 2:
            self.progress = 1

    def wins(self):
        if self.parsed_data.win == 1:
            self.progress += 1

# BINGO CHALLENGES
BINGO_WIDTH = 5
BINGO_CHALLENGE_NAMES = {
    "big_lead": ("Win With 8K Lead", 1),
    "bounty_gold": ("Shutdown Gold", 4000),
    "buff_steals": ("Buffs Stolen", 10),
    "damage_dealt": ("Damage Dealt", 1_000_000),
    "dives": ("Dive Kills", 5),
    "doinks": ("Doinks", 10),
    "dragon_souls": ("Dragon Souls", 3),
    "early_baron": ("Baron Before 28 Mins", 1),
    "elder_dragon": ("Elder Dragon", 1),
    "fast_win": ("Win before 22 Mins", 1),
    "flawless_ace": ("Flawless Ace", 1),
    "fountain_kill": ("Fountain Kill", 1),
    "invade_kills": ("Invade Kills", 5),
    "jungle_doinks": ("Jungle Doinks", 1),
    "killing_sprees": ("Killing Sprees", 10),
    "kills": ("Kills", 100),
    "outnumbered_kills": ("Outnumbered Kills", 5),
    "atakhan_kills": ("Atakhan Kills", 4),
    "solo_kills": ("Solo Kills", 10),
    "spells_casted": ("Spell Casts", 5000),
    "spells_dodged": ("Skillshots Dodged", 200),
    "spells_hit": ("Skillshots Hit", 500),
    "steals": ("Objective Steals", 2),
    "two_barons": ("Two Barons, One Game", 1),
    "wins": ("Won Games", 5),
}

def get_random_challenges(database: LoLGameDatabase):
    return database.get_new_bingo_challenges(BINGO_WIDTH ** 2)

def get_current_bingo_challenges(database: LoLGameDatabase, lan_date: str):
    return [
        {
            "id": id,
            "name": name,
            "progress": progress,
            "new_progress": bool(new_progress),
            "total": total,
            "completed": bool(completed),
            "completed_by": completed_by,
            "notification_sent": bool(notification_sent),
            "bingo": False
        }
        for id, name, progress, new_progress, total, completed, completed_by, notification_sent
        in database.get_active_bingo_challenges(lan_date)
    ]

def update_bingo_progress(database: LoLGameDatabase, post_game_stats: PostGameStats):
    active_challenges = get_current_bingo_challenges(database, LATEST_LAN_PARTY)

    with database:
        for challenge_data in active_challenges:
            if challenge_data["completed"]:
                continue

            solver = BingoSolver(challenge_data["id"], post_game_stats, challenge_data["progress"])
            completed = solver.progress >= challenge_data["total"]
            progress = solver.progress
            completed_by = solver.completed_by

            database.update_bingo_challenge(
                challenge_data["id"],
                LATEST_LAN_PARTY,
                min(progress, challenge_data["total"]),
                progress > challenge_data["progress"],
                completed,
                completed_by
            )

def insert_bingo_challenges(database: LoLGameDatabase, date: str):
    for index, challenge_id in enumerate(BINGO_CHALLENGE_NAMES):
        commit = index == len(BINGO_CHALLENGE_NAMES) - 1
        database.insert_bingo_challenge(challenge_id, date, *BINGO_CHALLENGE_NAMES[challenge_id], commit=commit)
