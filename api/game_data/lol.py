from datetime import datetime
from dataclasses import dataclass
from time import time

from api.game_stats import GameStats, PlayerStats, GameStatsParser
from api.util import format_duration

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
    role: str = None
    quadrakills: int = None
    pentakills: int = None
    total_time_dead: int = None
    turret_kills: int = None
    inhibitor_kills: int = None
    puuid: str = None

    @classmethod
    def STATS_TO_SAVE(cls):
        return super().STATS_TO_SAVE() + [
            "champ_id",
            "damage",
            "cs",
            "cs_per_min",
            "gold",
            "vision_wards",
            "vision_score",
            "steals"
        ]

    @classmethod
    def STAT_QUANTITY_DESC(cls):
        stat_quantities = dict(super().STAT_QUANTITY_DESC())
        stat_quantities.update(
            damage=("most", "least"),
            cs=("most", "least"),
            cs_per_min=("most", "least"),
            gold=("most", "least"),
            vision_wards=("most", "fewest"),
            vision_score=("highest", "lowest"),
            steals=("most", "least"),
        )
        return stat_quantities

@dataclass
class LoLGameStats(GameStats):
    first_blood: int = None
    map_id: int = None
    queue_id: int = None
    team_id: int = None
    damage_by_our_team: int = None
    our_baron_kills: int = None
    our_dragon_kills: int = None
    our_herald_kills: int = None
    enemy_baron_kills: int = None
    enemy_dragon_kills: int = None
    enemy_herald_kills: int = None

    @classmethod
    def STATS_TO_SAVE(cls):
        return super().STATS_TO_SAVE() + ["first_blood"]

    def get_filtered_timeline_stats(self, timeline_data: dict):
        """
        Get interesting timeline related data. This pertains to data that
        changes during the game, such as maximum gold deficit/lead of a team
        during the course of the game.
        """
        puuid_map = {}

        our_team_lower = True

        for stats in self.filtered_player_stats:
            puuid = stats.puuid
            for participant_data in timeline_data["participants"]:
                if participant_data["puuid"] == puuid:
                    our_team_lower = participant_data["participantId"] <= 5
                    puuid_map[puuid] = stats.disc_id
                    break

        timeline_data["puuid_map"] = puuid_map
        timeline_data["ourTeamLower"] = our_team_lower

        return timeline_data

    def get_finished_game_summary(self, disc_id: int):
        """
        Get a brief text that summaries a player's performance in a finished game.

        :param disc_id: Discord ID of the player for whom to get the summary for
        """
        player_stats: LoLPlayerStats = self.find_player_stats(disc_id, self.filtered_player_stats)

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

    def parse_from_database(self, database, game_id: int) -> GameStats:
        game_stats, player_stats = LoLGameStats.get_stats_from_db(self.game, game_id, database, LoLPlayerStats)

        all_player_stats = []
        players_in_game = []
        for disc_id in player_stats:
            player_stats[disc_id]["champ_name"] = self.api_client.get_champ_name(player_stats[disc_id]["champ_id"])
            all_player_stats.append(LoLPlayerStats(**player_stats[disc_id]))

            user_game_info = self.all_users[disc_id]
            summ_info = {
                "disc_id": disc_id,
                "summ_name": user_game_info.ingame_name[0],
                "summ_id": user_game_info.ingame_id[0],
                "champion_id": player_stats[disc_id],
            }
            players_in_game.append(summ_info)

        return LoLGameStats(self.game, **game_stats, players_in_game=players_in_game, all_player_stats=all_player_stats)

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
                        summ_ids = self.all_users[disc_id].ingame_id
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
                        summ_ids = self.all_users[disc_id].ingame_id
                        if part_info["player"]["summonerId"] in summ_ids:
                            player_disc_id = disc_id
                            break

                    kda =  (
                        participant["stats"]["kills"] + participant["stats"]["assists"]
                        if participant["stats"]["deaths"] == 0
                        else (participant["stats"]["kills"] + participant["stats"]["assists"]) / participant["stats"]["deaths"]
                    )

                    stats_for_player = LoLPlayerStats(
                        game_id=self.raw_data["gameId"],
                        disc_id=player_disc_id,
                        kills=participant["stats"]["kills"],
                        deaths=participant["stats"]["deaths"],
                        assists=participant["stats"]["assists"],
                        kda=kda,
                        champ_id=participant["championId"],
                        champ_name=participant["stats"]["championName"],
                        damage=participant["stats"]["totalDamageDealtToChampions"],
                        cs=participant["stats"]["neutralMinionsKilled"] + participant["stats"]["totalMinionsKilled"],
                        cs_per_min=(participant["stats"]["totalCs"] / self.raw_data["gameDuration"]) * 60,
                        gold=participant["stats"]["goldEarned"],
                        vision_wards=participant["stats"]["visionWardsBoughtInGame"],
                        vision_score=participant["stats"]["visionScore"],
                        steals=participant["stats"]["objectivesStolen"],
                        lane=participant["stats"]["role"],
                        role=participant["stats"]["role"],
                        quadrakills=participant["stats"]["quadraKills"],
                        pentakills=participant["stats"]["pentaKills"],
                        total_time_dead=participant["stats"]["totalTimeSpentDead"],
                        turret_kills=participant["stats"]["turretKills"],
                        inhibitor_kills=participant["stats"]["inhibitorKills"],
                        puuid=participant["stats"]["puuid"]
                    )
                    player_stats.append(stats_for_player)

                    if participant["stats"]["firstBloodKill"]:
                        first_blood_id = disc_id

                    if player_disc_id is not None:
                        summ_data = {
                            "disc_id": disc_id,
                            "summ_name": part_info["player"]["summonerName"],
                            "summ_id": part_info["player"]["summonerId"],
                            "champion_id": participant["championId"]
                        }
                        active_users.append(summ_data)

        for stats in player_stats:
            stats.kp = (
                100 if kills_per_team[our_team] == 0
                else int((float(stats.kills + stats.assists) / float(kills_per_team[our_team])) * 100.0)
            )

        first_blood_id = None
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
            first_blood=first_blood_id,
            map_id=self.raw_data["mapId"],
            queue_id=self.raw_data["queueId"],
            team_id=team_id,
            damage_by_our_team=damage_per_team[our_team],
            our_baron_kills=our_baron_kills,
            our_dragon_kills=our_dragon_kills,
            our_herald_kills=our_herald_kills,
            enemy_baron_kills=enemy_baron_kills,
            enemy_dragon_kills=enemy_dragon_kills,
            enemy_herald_kills=enemy_herald_kills,
            timeline_data=self.raw_data["timeline"]
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

        # First figure out what team we were on
        our_team = 100
        for participant in self.raw_data["participants"]:
            for disc_id in self.all_users.keys():
                if participant["summonerId"] in self.all_users[disc_id].ingame_id:
                    our_team = participant["teamId"]
                    break

        # Collect relevant stats for all players
        for participant in self.raw_data["participants"]:
            if participant["teamId"] == our_team:
                kills_per_team[participant["teamId"]] += participant["kills"]
                damage_per_team[participant["teamId"]] += participant["totalDamageDealtToChampions"]

                player_disc_id = None

                for disc_id in self.all_users.keys():
                    if participant["summonerId"] in self.all_users[disc_id].ingame_id:
                        player_disc_id = disc_id
                        break

                total_cs = participant["neutralMinionsKilled"] + participant["totalMinionsKilled"]
                kda =  (
                    participant["kills"] + participant["assists"]
                    if participant["deaths"] == 0
                    else (participant["kills"] + participant["assists"]) / participant["deaths"]
                )

                stats_for_player = LoLPlayerStats(
                    game_id=self.raw_data["gameId"],
                    disc_id=player_disc_id,
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
                    role=participant["role"],
                    quadrakills=participant["quadraKills"],
                    pentakills=participant["pentaKills"],
                    total_time_dead=participant["totalTimeSpentDead"],
                    turret_kills=participant["turretKills"],
                    inhibitor_kills=participant["inhibitorKills"],
                    puuid=participant["puuid"],
                )

                if participant["firstBloodKill"]:
                    first_blood_id = player_disc_id

                player_stats.append(stats_for_player)

                if player_disc_id is not None:
                    summ_data = {
                        "disc_id": player_disc_id,
                        "summ_name": participant["summonerName"],
                        "summ_id": participant["summonerId"],
                        "champion_id": participant["championId"]
                    }
                    active_users.append(summ_data)

        # Set kill participation
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
            objectives = team["objectives"]
            if team["teamId"] == our_team:
                our_baron_kills = objectives["baron"]["kills"]
                our_dragon_kills = objectives["dragon"]["kills"]
                our_herald_kills = objectives["riftHerald"]["kills"]
                game_win = team["win"]
                team_id = team["teamId"]
            else:
                enemy_baron_kills = objectives["baron"]["kills"]
                enemy_dragon_kills = objectives["dragon"]["kills"]
                enemy_herald_kills = objectives["riftHerald"]["kills"]

        return LoLGameStats(
            game=self.game,
            game_id=self.raw_data["gameId"],
            timestamp=int(self.raw_data["gameCreation"] / 1000),
            duration=int(self.raw_data["gameDuration"]),
            win=int(game_win),
            guild_id=self.guild_id,
            players_in_game=active_users,
            all_player_stats=player_stats,
            first_blood=first_blood_id,
            map_id=self.raw_data["mapId"],
            queue_id=self.raw_data["queueId"],
            team_id=team_id,
            damage_by_our_team=damage_per_team[our_team],
            our_baron_kills=our_baron_kills,
            our_dragon_kills=our_dragon_kills,
            our_herald_kills=our_herald_kills,
            enemy_baron_kills=enemy_baron_kills,
            enemy_dragon_kills=enemy_dragon_kills,
            enemy_herald_kills=enemy_herald_kills,
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
                if participant["summonerId"] in self.all_users[disc_id].ingame_id:
                    champ_id = participant["championId"]
                    champ_played = self.api_client.get_champ_name(champ_id)
                    if champ_played is None:
                        champ_played = "Unknown Champ (Rito pls)"
                    champions[participant["summonerId"]] = (participant["summonerName"], champ_played)

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
                    response += f"\n - {name} ({champ})"

        return response

def get_player_stats(data, summ_ids):
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
            if part_info["player"]["summonerId"] in summ_ids:
                for participant in data["participants"]:
                    if part_info["participantId"] == participant["participantId"]:
                        stats = participant["stats"]
                        stats["championId"] = participant["championId"]
                        return stats

    else:
        for participant_data in data["participants"]:
            if participant_data["summonerId"] in summ_ids:
                return participant_data

    return None
