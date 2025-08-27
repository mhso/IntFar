from datetime import datetime
from dataclasses import dataclass
from time import time

from api.game_stats import GameStats, PlayerStats, GameStatsParser
from api.util import format_duration

_ROLE_MAP = {
    "MIDDLE": "mid",
    "TOP": "top",
    "JUNGLE": "jungle",
    "UTILITY": "support",
    "BOTTOM": "adc"
}

_RANKS = [
    "iron",
    "bronze",
    "silver",
    "gold",
    "platinum",
    "emerald",
    "diamond",
    "master",
    "grandmaster",
    "challenger"
]

@dataclass
class LoLPlayerStats(PlayerStats):
    champ_id: int = None
    champ_name: str = None
    damage: int = None
    cs: int = None
    cs_per_min: float = None
    gold: int = None
    vision_wards: int = None
    vision_score: int = None
    steals: int = None
    lane: str = None
    position: str = None
    role: str = None
    rank_solo: str = None
    rank_flex: str = None
    puuid: str = None
    quadrakills: int = None
    pentakills: int = None
    total_time_dead: int = None
    turret_kills: int = None
    inhibitor_kills: int = None
    challenges: dict = None

    @classmethod
    def stats_to_save(cls):
        return super().stats_to_save() + [
            "champ_id",
            "damage",
            "cs",
            "cs_per_min",
            "gold",
            "vision_wards",
            "vision_score",
            "steals",
            "role",
            "rank_solo",
            "rank_flex" 
        ]

    @classmethod
    def stat_quantity_desc(cls):
        stat_quantities = dict(super().stat_quantity_desc())
        stat_quantities.update(
            damage=("most", "least"),
            cs=("most", "least"),
            cs_per_min=("most", "least"),
            gold=("most", "least"),
            vision_wards=("most", "fewest"),
            vision_score=("highest", "lowest"),
            steals=("most", "least"),
            first_blood=("most", "fewest")
        )

        return stat_quantities

    @classmethod
    def formatted_stat_names(cls, capitalize=True):
        formatted = dict(super().formatted_stat_names(capitalize))
        for stat in cls.stats_to_save():
            if stat in formatted or stat == "champ_id":
                continue

            if stat == "cs":
                fmt_stat = stat.upper()
            elif stat == "cs_per_min":
                fmt_stat = "CS Per Min"
            elif stat == "rank_solo":
                fmt_stat = "Solo/Duo" if capitalize else "solo/duo"
            elif stat == "rank_flex":
                fmt_stat = "Flex" if capitalize else "flex"
            else:
                fmt_stat = " ".join(map(lambda s: s.capitalize() if capitalize else s, stat.split("_")))

            formatted[stat] = fmt_stat

        return formatted

    @classmethod
    def get_formatted_stat_value(cls, stat, value) -> str:
        if value is None:
            return "Unknown"

        if isinstance(value, float) and stat in ("damage", "gold"):
            return str(int(value))

        if stat == "role":
            return value.upper() if value == "adc" else value.capitalize()
        elif stat in ("rank_solo", "rank_flex"):
            if value is None:
                return "Unranked"

            division, tier, points = value.split("_")
            return f"{division.capitalize()} {tier}, {points} LP"

        return super().get_formatted_stat_value(stat, value)

@dataclass
class LoLGameStats(GameStats):
    first_blood: int = None
    queue_id: int = None
    team_id: int = None
    damage_by_our_team: int = None
    our_baron_kills: int = None
    our_dragon_kills: int = None
    our_herald_kills: int = None
    our_grub_kills: int = None
    our_atakhan_kills: int = None
    enemy_baron_kills: int = None
    enemy_dragon_kills: int = None
    enemy_herald_kills: int = None
    enemy_atakhan_kills: int = None
    enemy_grub_kills: int = None
    timeline_data: dict = None

    def __post_init__(self):
        super().__post_init__()
        if self.timeline_data is not None:
            self.timeline_data = self.get_filtered_timeline_stats()

    @classmethod
    def stats_to_save(cls):
        return super().stats_to_save() + ["first_blood"]

    def _get_line_coeficient(self, p_1, p_2, x, y):
        slope = (p_2[1] - p_1[1]) / (p_2[0] - p_1[0])
        intercept = (slope * p_1[0] - p_1[1]) * -1

        return slope * x + intercept - y

    def _is_event_in_fountain(self, x, y):
        blueside_p1 = (2920, 7680)
        blueside_p2 = (6720, 4160)
        redside_p1 = (34240, 33600)
        redside_p2 = (38120, 30920)

        blue_side = self.team_id == 100
        if blue_side:
            p_1 = blueside_p1
            p_2 = blueside_p2
        else:
            p_1 = redside_p1
            p_2 = redside_p2

        coef = self._get_line_coeficient(p_1, p_2, x, y)

        if blue_side:
            return coef > 0

        return coef < 0

    def _is_event_on_our_side(self, x, y):
        if x < y: # Top side
            redside_p1 = (2420, 13000)
            redside_p2 = (9026, 8101)
            blueside_p1 = (1273, 12141)
            blueside_p2 = (7861, 7398)
        else: # Bottom side
            redside_p1 = (9026, 8101)
            redside_p2 = (15865, 3546)
            blueside_p1 = (7861, 7398)
            blueside_p2 = (15077, 1922)

        blue_side = self.team_id == 100

        if blue_side: # Blue side
            p_1 = blueside_p1
            p_2 = blueside_p2
        else: # Red side
            p_1 = redside_p1
            p_2 = redside_p2

        coef = self._get_line_coeficient(p_1, p_2, x, y)

        if blue_side:
            return coef > 0

        return coef < 0

    def get_filtered_timeline_stats(self):
        """
        Get interesting timeline related data. This pertains to data that
        changes during the game, such as maximum gold deficit/lead of a team
        during the course of the game.
        """
        puuid_map = {}

        our_team_lower = True

        for stats in self.filtered_player_stats:
            for participant_data in self.timeline_data["participants"]:
                if participant_data["puuid"] == stats.player_id:
                    our_team_lower = participant_data["participantId"] <= 5
                    puuid_map[stats.player_id] = stats.disc_id
                    break

        self.timeline_data["puuid_map"] = puuid_map
        self.timeline_data["ourTeamLower"] = our_team_lower

        participant_dict = {
            entry["participantId"]: self.timeline_data["puuid_map"].get(entry["puuid"])
            for entry in self.timeline_data["participants"]
        }

        biggest_gold_lead = 0
        biggest_gold_deficit = 0
        max_current_gold = {}
        player_total_gold = {}
        any_quadrakills = any(
            player_stats.quadrakills > 0
            for player_stats in self.filtered_player_stats
        )
        curr_multikill = {}
        stolen_penta_victims = {}
        stolen_penta_scrubs = {}
        people_forgetting_items = []
        invade_kills = 0
        anti_invade_kills = 0
        invade_victims = 0
        anti_invade_victims = 0

        # Calculate stats from timeline frames.
        for frame_data in self.timeline_data["frames"]:
            # Tally up our and ememy teams total gold during the game.
            our_total_gold = 0
            enemy_total_gold = 0

            for participant_id in frame_data["participantFrames"]:
                participant_data = frame_data["participantFrames"][participant_id]
                disc_id = participant_dict.get(int(participant_id))
                total_gold = participant_data["totalGold"]
                curr_gold = participant_data["currentGold"]
                our_team = (int(participant_id) > 5) ^ self.timeline_data["ourTeamLower"]

                # Add players gold to total for their team.
                if our_team:
                    our_total_gold += total_gold
                else:
                    enemy_total_gold += total_gold

                if disc_id is None:
                    continue

                # Save the current max gold for the player
                curr_value_for_player = max_current_gold.get(disc_id, 0)
                max_current_gold[disc_id] = max(curr_gold, curr_value_for_player)
                player_total_gold[disc_id] = total_gold

            gold_diff = our_total_gold - enemy_total_gold
            if gold_diff < 0: # Record max gold deficit during the game.
                biggest_gold_deficit = max(abs(gold_diff), biggest_gold_deficit) 
            else: # Record max gold lead during the game.
                biggest_gold_lead = max(gold_diff, biggest_gold_lead)

            if any_quadrakills:
                for disc_id in curr_multikill:
                    if frame_data["timestamp"] - curr_multikill[disc_id]["timestamp"] > 10_000: # 10 secs
                        curr_multikill[disc_id]["streak"] = 0

                # Keep track of multikills for each player
                for event in frame_data.get("events", []):
                    if event["type"] != "CHAMPION_KILL":
                        continue

                    disc_id = participant_dict.get(int(event["killerId"]))
                    if disc_id is None:
                        continue

                    if disc_id not in curr_multikill:
                        curr_multikill[disc_id] = {"streak": 0, "timestamp": 0}

                    curr_multikill[disc_id]["streak"] += 1
                    curr_multikill[disc_id]["timestamp"] = event["timestamp"]

                # Check if someone stole a penta from someone else
                people_with_quadras = list(filter(lambda x: x[1]["streak"] == 4, curr_multikill.items()))

                if people_with_quadras != []:
                    person_with_quadra, streak_dict = people_with_quadras[0]
                    for disc_id in curr_multikill:
                        if disc_id != person_with_quadra and curr_multikill[disc_id]["timestamp"] > streak_dict["timestamp"]:
                            stolen_penta_scrubs[disc_id] = stolen_penta_scrubs.get(disc_id, 0) + 1
                            victim_list = stolen_penta_victims.get(disc_id, [])
                            victim_list.append(person_with_quadra)
                            stolen_penta_victims[disc_id] = victim_list

            if 10_000 < frame_data["timestamp"] < 70_000:
                # Check whether someone left the fountain without buying items
                people_buying_items = set()
                for event in frame_data.get("events", []):
                    if event["type"] == "ITEM_PURCHASED":
                        people_buying_items.add(event["participantId"])

                people_with_no_items = set(int(participant_id) for participant_id in frame_data["participantFrames"]) - people_buying_items
    
                for participant_id in people_with_no_items:
                    part_frame = frame_data["participantFrames"][str(participant_id)]
                    x = part_frame["position"]["x"]
                    y = part_frame["position"]["y"]
                    if not self._is_event_in_fountain(x, y) and (disc_id := participant_dict.get(participant_id)) is not None:
                        people_forgetting_items.append(disc_id)

            if frame_data["timestamp"] < 130_000:
                # Check whether we invaded at the start of the game
                # and either got kills or got killed
                for event in frame_data.get("events", []):
                    if event["type"] != "CHAMPION_KILL":
                        continue

                    our_kill = (int(event["victimId"]) <= 5) ^ self.timeline_data["ourTeamLower"]
                    x = event["position"]["x"]
                    y = event["position"]["y"]

                    if self._is_event_on_our_side(x, y):
                        if our_kill:
                            anti_invade_kills += 1
                        else:
                            anti_invade_victims += 1
                    else:
                        if our_kill:
                            invade_kills += 1
                        else:
                            invade_victims += 1

        # Save all the events to self.timeline_data
        self.timeline_data.update(
            biggest_gold_lead=biggest_gold_lead,
            biggest_gold_deficit=biggest_gold_deficit,
            max_current_gold=max_current_gold,
            player_total_gold=player_total_gold,
            stolen_penta_victims=stolen_penta_victims,
            stolen_penta_scrubs=stolen_penta_scrubs,
            people_forgetting_items=people_forgetting_items,
            invade_kills=invade_kills,
            anti_invade_kills=anti_invade_kills,
            invade_victims=invade_victims,
            anti_invade_victims=anti_invade_victims
        )

        return self.timeline_data

    def get_finished_game_summary(self, disc_id: int):
        """
        Get a brief text that summaries a player's performance in a finished game.

        :param disc_id: Discord ID of the player for whom to get the summary for
        """
        player_stats: LoLPlayerStats = GameStats.find_player_stats(disc_id, self.filtered_player_stats)

        date = datetime.fromtimestamp(self.timestamp).strftime("%Y/%m/%d")
        dt_1 = datetime.fromtimestamp(time())
        dt_2 = datetime.fromtimestamp(time() + self.duration)
        fmt_duration = format_duration(dt_1, dt_2)

        return (
            f"{player_stats.champ_name} with a score of {player_stats.kills}/" +
            f"{player_stats.deaths}/{player_stats.assists} on {date} in a {fmt_duration} long game"
        )

class LoLGameStatsParser(GameStatsParser):
    def __init__(self, game, raw_data, api_client, all_users, guild_id):
        super().__init__(game, raw_data, api_client, all_users, guild_id)

    def parse_data(self) -> GameStats:
        if "participantIdentities" in self.raw_data: # Old match v4 data.
            return self.get_relevant_stats_v4()

        return self.get_relevant_stats()

    def parse_from_database(self, database, game_id: int = None) -> list[GameStats]:
        """
        Get data for a given game, or all games if `game_id` is None, from the database
        and return a list of GameStats objects with the game data.
        """
        all_game_stats, all_player_stats = LoLGameStats.get_stats_from_db(database, LoLPlayerStats, game_id)

        all_stats = []
        for game_stats, player_stats in zip(all_game_stats, all_player_stats):
            all_player_stats = []
            players_in_game = []
            for disc_id in player_stats:
                player_stats[disc_id]["champ_name"] = self.api_client.get_champ_name(player_stats[disc_id]["champ_id"])
                all_player_stats.append(LoLPlayerStats(**player_stats[disc_id]))

                user_game_info = self.all_users[disc_id]
                summ_info = {
                    "disc_id": disc_id,
                    "player_name": [user_game_info.player_name[0]],
                    "player_id": [user_game_info.player_id[0]],
                    "champ_id": player_stats[disc_id],
                }
                players_in_game.append(summ_info)

            all_stats.append(LoLGameStats(self.game, **game_stats, players_in_game=players_in_game, all_player_stats=all_player_stats))

        return all_stats

    def get_relevant_stats_v4(self) -> GameStats:
        """
        Get relevant stats from the given game data and filter the data
        that is relevant for the Discord users that participated in the game.

        This method is used for Riot's older Match API v4, where data is formatted
        differently from v5. This method is only used to get data from older games,
        before Riot migrated to Match API v5.
        """
        kills_per_team = {100: 0, 200: 0}
        damage_per_team = {100: 0, 200: 0}
        player_stats = []
        active_users = []
        first_blood_id = None

        # First figure out what team we were on
        our_team = 100
        for part_info in self.raw_data["participantIdentities"]:
            for participant in self.raw_data["participants"]:
                if part_info["participantId"] == participant["participantId"]:
                    for disc_id in self.all_users.keys():
                        summ_ids = self.all_users[disc_id].player_id
                        if part_info["player"]["summonerId"] in summ_ids:
                            our_team = participant["teamId"]
                            break

        # Collect relevant stats for all players
        for part_info in self.raw_data["participantIdentities"]:
            for participant in self.raw_data["participants"]:
                if participant["teamId"] == our_team and part_info["participantId"] == participant["participantId"]:
                    kills_per_team[participant["teamId"]] += participant["stats"]["kills"]
                    damage_per_team[participant["teamId"]] += participant["stats"]["totalDamageDealtToChampions"]

                    player_disc_id = None
                    for disc_id in self.all_users.keys():
                        summ_ids = self.all_users[disc_id].player_id
                        if part_info["player"]["summonerId"] in summ_ids:
                            player_disc_id = disc_id
                            break

                    # Calculate total CS and KDA
                    total_cs = participant["stats"]["neutralMinionsKilled"] + participant["stats"]["totalMinionsKilled"]
                    kda =  (
                        participant["stats"]["kills"] + participant["stats"]["assists"]
                        if participant["stats"]["deaths"] == 0
                        else (participant["stats"]["kills"] + participant["stats"]["assists"]) / participant["stats"]["deaths"]
                    )

                    # Get player rank
                    solo_rank, flex_rank = parse_player_rank(self.raw_data.get("player_ranks", {}).get(player_disc_id, []))

                    lane = participant["timeline"]["lane"]
                    position = participant["timeline"]["role"]
                    if position == "DUO_SUPPORT":
                        role = "support"
                    else:
                        role = _ROLE_MAP.get(lane)

                    stats_for_player = LoLPlayerStats(
                        game_id=self.raw_data["gameId"],
                        disc_id=player_disc_id,
                        player_id=part_info["player"]["summonerId"],
                        kills=participant["stats"]["kills"],
                        deaths=participant["stats"]["deaths"],
                        assists=participant["stats"]["assists"],
                        kda=kda,
                        champ_id=participant["championId"],
                        champ_name=self.api_client.get_playable_name(participant["championId"]),
                        damage=participant["stats"]["totalDamageDealtToChampions"],
                        cs=total_cs,
                        cs_per_min=(total_cs / self.raw_data["gameDuration"]) * 60,
                        gold=participant["stats"]["goldEarned"],
                        vision_wards=participant["stats"]["visionWardsBoughtInGame"],
                        vision_score=participant["stats"]["visionScore"],
                        lane=lane,
                        position=position,
                        role=role,
                        rank_solo=solo_rank,
                        rank_flex=flex_rank,
                        quadrakills=participant["stats"]["quadraKills"],
                        pentakills=participant["stats"]["pentaKills"],
                        turret_kills=participant["stats"]["turretKills"],
                        inhibitor_kills=participant["stats"]["inhibitorKills"]
                    )
                    player_stats.append(stats_for_player)

                    if participant["stats"]["firstBloodKill"]:
                        first_blood_id = player_disc_id

                    if player_disc_id is not None:
                        summ_data = {
                            "disc_id": disc_id,
                            "player_name": [part_info["player"]["summonerName"]],
                            "player_id": [part_info["player"]["summonerId"]],
                            "champ_id": participant["championId"]
                        }
                        active_users.append(summ_data)

        for stats in player_stats:
            stats.kp = (
                100 if kills_per_team[our_team] == 0
                else int((float(stats.kills + stats.assists) / float(kills_per_team[our_team])) * 100.0)
            )

        game_win = True
        team_id = None
        our_baron_kills = 0
        our_dragon_kills = 0
        our_herald_kills = 0
        enemy_baron_kills = 0
        enemy_dragon_kills = 0
        enemy_herald_kills = 0

        for team in self.raw_data["teams"]:
            if team["teamId"] == our_team:
                our_baron_kills = team["baronKills"]
                our_dragon_kills = team["dragonKills"]
                our_herald_kills = team["riftHeraldKills"]
                game_win = team["win"] == "Win"
                team_id = team["teamId"]
            else:
                enemy_baron_kills = team["baronKills"]
                enemy_dragon_kills = team["dragonKills"]
                enemy_herald_kills = team["riftHeraldKills"]

        return LoLGameStats(
            game=self.game,
            game_id=self.raw_data["gameId"],
            timestamp=int(self.raw_data["gameCreation"] / 1000),
            duration=int(self.raw_data["gameDuration"]),
            win=1 if game_win else -1,
            guild_id=self.guild_id,
            players_in_game=active_users,
            all_player_stats=player_stats,
            map_id=self.raw_data["mapId"],
            first_blood=first_blood_id,
            queue_id=self.raw_data["queueId"],
            team_id=team_id,
            damage_by_our_team=damage_per_team[our_team],
            our_baron_kills=our_baron_kills,
            our_dragon_kills=our_dragon_kills,
            our_herald_kills=our_herald_kills,
            enemy_baron_kills=enemy_baron_kills,
            enemy_dragon_kills=enemy_dragon_kills,
            enemy_herald_kills=enemy_herald_kills,
        )

    def get_relevant_stats(self) -> GameStats:
        """
        Get relevant stats from the given game data and filter the data
        that is relevant for the Discord users that participated in the game.

        This method is used for Riot's newer Match API v5. This is now the standard
        for all new League of Legends games (until a new one comes along).
        """
        kills_per_team = {100: 0, 200: 0}
        damage_per_team = {100: 0, 200: 0}
        player_stats = []
        active_users = []
        first_blood_id = None

        # First figure out what team(s) we were on
        our_team = 100
        for participant in self.raw_data["participants"]:
            for disc_id in self.all_users.keys():
                if participant["puuid"] in self.all_users[disc_id].player_id:
                    our_team = participant["teamId"]
                    break

        # Collect relevant stats for all players
        for participant in self.raw_data["participants"]:
            if participant["teamId"] == our_team:
                kills_per_team[participant["teamId"]] += participant["kills"]
                damage_per_team[participant["teamId"]] += participant["totalDamageDealtToChampions"]

                player_disc_id = None

                for disc_id in self.all_users.keys():
                    if participant["puuid"] in self.all_users[disc_id].player_id:
                        player_disc_id = disc_id
                        break

                # Calculate total CS and KDA
                total_cs = participant["neutralMinionsKilled"] + participant["totalMinionsKilled"]
                kda =  (
                    participant["kills"] + participant["assists"]
                    if participant["deaths"] == 0
                    else (participant["kills"] + participant["assists"]) / participant["deaths"]
                )

                # Get player rank
                solo_rank, flex_rank = parse_player_rank(self.raw_data.get("player_ranks", {}).get(player_disc_id, []))

                stats_for_player = LoLPlayerStats(
                    game_id=self.raw_data["gameId"],
                    disc_id=player_disc_id,
                    player_id=participant["puuid"],
                    kills=participant["kills"],
                    deaths=participant["deaths"],
                    assists=participant["assists"],
                    kda=kda,
                    champ_id=participant["championId"],
                    champ_name=participant["championName"],
                    damage=participant["totalDamageDealtToChampions"],
                    cs=total_cs,
                    cs_per_min=(total_cs / self.raw_data["gameDuration"]) * 60,
                    gold=participant["goldEarned"],
                    vision_wards=participant["visionWardsBoughtInGame"],
                    vision_score=participant["visionScore"],
                    steals=participant["objectivesStolen"],
                    lane=participant["teamPosition"],
                    position=participant["role"],
                    role=_ROLE_MAP[participant["teamPosition"]],
                    rank_solo=solo_rank,
                    rank_flex=flex_rank,
                    quadrakills=participant["quadraKills"],
                    pentakills=participant["pentaKills"],
                    total_time_dead=participant["totalTimeSpentDead"],
                    turret_kills=participant["turretKills"],
                    inhibitor_kills=participant["inhibitorKills"],
                    challenges=participant["challenges"]
                )

                if participant["firstBloodKill"]:
                    first_blood_id = player_disc_id

                player_stats.append(stats_for_player)

                if player_disc_id is not None:
                    summ_data = {
                        "disc_id": player_disc_id,
                        "player_name": [participant["summonerName"]],
                        "player_id": [participant["puuid"]],
                        "champ_id": participant["championId"]
                    }
                    active_users.append(summ_data)

        # Set kill participation
        for stats in player_stats:
            stats.kp = (
                100 if kills_per_team[our_team] == 0
                else int((float(stats.kills + stats.assists) / float(kills_per_team[our_team])) * 100.0)
            )

        team_id = None
        game_win = 1
        our_baron_kills = 0
        our_dragon_kills = 0
        our_herald_kills = 0
        our_grub_kills = 0
        our_atakhan_kills = 0
        enemy_baron_kills = 0
        enemy_dragon_kills = 0
        enemy_herald_kills = 0
        enemy_grub_kills = 0
        enemy_atakhan_kills = 0

        for team in self.raw_data["teams"]:
            objectives = team["objectives"]
            if team["teamId"] == our_team:
                our_baron_kills = objectives["baron"]["kills"]
                our_dragon_kills = objectives["dragon"]["kills"]
                our_herald_kills = objectives["riftHerald"]["kills"]
                our_atakhan_kills = objectives.get("atakhan", {}).get("kills", 0)
                our_grub_kills = objectives["horde"]["kills"]
                game_win = 1 if team["win"] else -1
                team_id = team["teamId"]
            else:
                enemy_baron_kills = objectives["baron"]["kills"]
                enemy_dragon_kills = objectives["dragon"]["kills"]
                enemy_herald_kills = objectives["riftHerald"]["kills"]
                enemy_atakhan_kills = objectives.get("atakhan", {}).get("kills", 0)
                enemy_grub_kills = objectives["horde"]["kills"]

        return LoLGameStats(
            game=self.game,
            game_id=self.raw_data["gameId"],
            timestamp=int(self.raw_data["gameCreation"] / 1000),
            duration=int(self.raw_data["gameDuration"]),
            win=game_win,
            guild_id=self.guild_id,
            players_in_game=active_users,
            all_player_stats=player_stats,
            map_id=self.raw_data["mapId"],
            first_blood=first_blood_id,
            queue_id=self.raw_data["queueId"],
            team_id=team_id,
            damage_by_our_team=damage_per_team[our_team],
            our_baron_kills=our_baron_kills,
            our_dragon_kills=our_dragon_kills,
            our_herald_kills=our_herald_kills,
            our_grub_kills=our_grub_kills,
            our_atakhan_kills=our_atakhan_kills,
            enemy_baron_kills=enemy_baron_kills,
            enemy_dragon_kills=enemy_dragon_kills,
            enemy_herald_kills=enemy_herald_kills,
            enemy_grub_kills=enemy_grub_kills,
            enemy_atakhan_kills=enemy_atakhan_kills,
            timeline_data=self.raw_data["timeline"]
        )

    def get_active_game_summary(self, active_id):
        """
        Get a description about a currently active game for a given player.

        :active_id: The summoner ID that we should extract data for in the game
        """
        champions = {}
        for participant in self.raw_data["participants"]:
            for disc_id in self.all_users.keys():
                user = self.all_users[disc_id]
                active_name = None
                for puuid, summ_name in zip(user.player_id, user.player_name):
                    if puuid == participant["puuid"]:
                        active_name = summ_name
                        break

                if active_name is None:
                    continue

                champ_id = participant["championId"]
                champ_played = self.api_client.get_champ_name(champ_id)
                if champ_played is None:
                    champ_played = "Unknown Champ (Rito pls)"

                champions[participant["puuid"]] = (active_name, champ_played)

        game_start = self.raw_data["gameStartTime"] / 1000
        if game_start > 0:
            now = time()
            dt_1 = datetime.fromtimestamp(game_start)
            dt_2 = datetime.fromtimestamp(now)
            fmt_duration = format_duration(dt_1, dt_2) + " "
        else:
            fmt_duration = ""
        game_mode = self.raw_data["gameMode"]

        response = f"{fmt_duration}in a {game_mode} game, playing {champions[active_id][1]}.\n"
        if len(champions) > 1:
            response += "He is playing with:"
            for other_id in champions:
                if other_id != active_id:
                    name, champ = champions[other_id]
                    response += f"\n- {name} ({champ})"

        return response

def get_player_stats(data, player_ids):
    """
    Get a specific player's stats from a dictionary of game data

    :param data:        Dictionary containing un-filtered data about a finished
                        game fetched from Riot League API
    :param summ_ids:    List of summoner ids belonging to a player,
                        for which to extract stats for
    """
    if "participantIdentities" in data:
        # We have to do this to handle /match/v4 stuff...
        for part_info in data["participantIdentities"]:
            if part_info["player"]["summonerId"] in player_ids:
                for participant in data["participants"]:
                    if part_info["participantId"] == participant["participantId"]:
                        stats = participant["stats"]
                        stats["championId"] = participant["championId"]
                        return stats

    else:
        for participant_data in data["participants"]:
            if participant_data["puuid"] in player_ids:
                return participant_data

    return None

def parse_player_rank(rank_data):
    # Get player rank
    solo_rank = None
    flex_rank = None
    for queue_info in rank_data:
        if queue_info["queueType"] in ("RANKED_SOLO_5x5", "RANKED_FLEX_SR"):
            division = queue_info["tier"].lower()
            tier = queue_info["rank"]
            points = queue_info["leaguePoints"]
            rank = f"{division}_{tier}_{points}"

            if queue_info["queueType"] == "RANKED_SOLO_5x5":
                solo_rank = rank
            else:
                flex_rank = rank

    return solo_rank, flex_rank

def get_rank_value(rank: str):
    if rank is None:
        return 0

    division, tier, points = rank.split("_")
    numerals = ["I", "II", "III", "IV", "V"]
    return (_RANKS.index(division) * 100) + (numerals.index(tier.upper()) * 10) + int(points)
