from datetime import datetime
from dataclasses import dataclass
import time

from api.game_stats import GameStats, PlayerStats, GameStatsParser
from api.riot_api import RiotAPIClient
from api.util import format_duration

@dataclass
class LoLPlayerStats(PlayerStats):
    champ_id: int
    damage: int
    cs: int
    cs_per_min: float
    gold: int
    vision_wards: int
    vision_score: int
    steals: int
    lane: str
    role: str
    pentakills: int
    total_time_dead: int
    turret_kills: int
    inhibitor_kills: int
    puuid: str

    @classmethod
    def STATS_TO_SAVE():
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
    def STAT_QUANTITY_DESC():
        stat_quantities = dict(super().STAT_QUANTITY_DESC())
        stat_quantities.update(
            damage=("most", "least"),
            cs=("most", "least"),
            cs_per_min=("most", "least"),
            gold=("most", "least"),
            vision_wards=("most", "fewest"),
            vision_score=("highest", "lowest"),
            steals=("most", "least"),
            first_blood=("most", "least")
        )
        return stat_quantities

@dataclass
class LoLGameStats(GameStats):
    first_blood: int
    map_id: int
    team_id: int
    damage_by_our_team: int
    our_baron_kills: int
    our_dragon_kills: int
    our_herald_kills: int
    enemy_baron_kills: int
    enemy_dragon_kills: int
    enemy_herald_kills: int

    @classmethod
    def STATS_TO_SAVE():
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

class LoLGameStatsParser(GameStatsParser):
    def __init__(self, game, data_dict, all_users, guild_id):
        super().__init__(game, data_dict, all_users, guild_id)

    def parse_data(self) -> GameStats:
        if "participantIdentities" in self.raw_data: # Old match v4 data.
            return self.get_relevant_stats_v4()

        return self.get_relevant_stats()

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
        our_team = 100
        player_stats = []
        active_users = []

        for part_info in self.raw_data["participantIdentities"]:
            for participant in self.raw_data["participants"]:
                if part_info["participantId"] == participant["participantId"]:
                    kills_per_team[participant["teamId"]] += participant["stats"]["kills"]
                    damage_per_team[participant["teamId"]] += participant["stats"]["totalDamageDealtToChampions"]

                    for disc_id in self.all_users:
                        summ_ids = self.all_users[disc_id].ingame_id
                        if part_info["player"]["summonerId"] in summ_ids:
                            our_team = participant["teamId"]
                            stats_for_player = LoLPlayerStats(
                                kills=participant["stats"]["kills"],
                                deaths=participant["stats"]["deaths"],
                                assists=participant["stats"]["assists"],
                                champ_id=participant["championId"],
                                damage=participant["stats"]["totalDamageDealtToChampions"],
                                cs=participant["stats"]["neutralMinionsKilled"] + participant["stats"]["totalMinionsKilled"],
                                cs_per_min=(participant["stats"]["totalCs"] / self.raw_data["gameDuration"]) * 60,
                                gold=participant["stats"]["goldEarned"],
                                vision_wards=participant["stats"]["visionWardsBoughtInGame"],
                                vision_score=participant["stats"]["visionScore"],
                                steals=participant["stats"]["objectivesStolen"],
                                lane=participant["stats"]["role"],
                                role=participant["stats"]["role"],
                                pentakills=participant["stats"]["pentaKills"],
                                total_time_dead=participant["stats"]["totalTimeSpentDead"],
                                turret_kills=participant["stats"]["turretKills"],
                                inhibitor_kills=participant["stats"]["inhibitorKills"],
                                puuid=participant["stats"]["puuid"]
                            )
                            player_stats.append((disc_id, stats_for_player))

                            summ_data = (
                                disc_id, part_info["player"]["summonerName"],
                                part_info["player"]["summonerId"], participant["championId"]
                            )
                            active_users.append(summ_data)

        first_blood_id = None
        game_win = True
        team_id = None
        our_baron_kills = 0
        our_dragon_kills = 0
        our_herald_kills = 0
        enemy_baron_kills = 0
        enemy_dragon_kills = 0
        enemy_herald_kills = 0

        for disc_id, stats in player_stats:
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

            if stats["firstBloodKill"]:
                first_blood_id = disc_id

        return LoLGameStats(
            game=self.game,
            game_id=self.raw_data["gameId"],
            timestamp=self.raw_data["gameCreation"],
            duration=int(self.raw_data["gameDuration"]),
            win=int(game_win),
            kills_by_our_team=kills_per_team[our_team],
            guild_id=self.guild_id,
            players_in_game=active_users,
            all_player_stats=player_stats,
            first_blood=first_blood_id,
            map_id=self.raw_data["mapId"],
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
        our_team = 100
        player_stats = []
        active_users = []

        for participant in self.raw_data["participants"]:
            kills_per_team[participant["teamId"]] += participant["kills"]
            damage_per_team[participant["teamId"]] += participant["totalDamageDealtToChampions"]

            player_disc_id = None

            for disc_id in self.all_users:
                if participant["summonerId"] in self.all_users[disc_id].ingame_id:
                    player_disc_id = disc_id
                    break

            if player_disc_id is not None:
                our_team = participant["teamId"]

            stats_for_player = LoLPlayerStats(
                kills=participant["kills"],
                deaths=participant["deaths"],
                assists=participant["assists"],
                champ_id=participant["championId"],
                damage=participant["totalDamageDealtToChampions"],
                cs=participant["neutralMinionsKilled"] + participant["totalMinionsKilled"],
                cs_per_min=(participant["totalCs"] / self.raw_data["gameDuration"]) * 60,
                gold=participant["goldEarned"],
                vision_wards=participant["visionWardsBoughtInGame"],
                vision_score=participant["visionScore"],
                steals=participant["objectivesStolen"],
                lane=participant["lane"],
                role=participant["role"],
                pentakills=participant["pentaKills"],
                total_time_dead=participant["totalTimeSpentDead"],
                turret_kills=participant["turretKills"],
                inhibitor_kills=participant["inhibitorKills"],
                puuid=participant["puuid"]
            )

            player_stats.append((player_disc_id, stats_for_player))

            if player_disc_id is not None:
                summ_data = (
                    player_disc_id, participant["summonerName"],
                    participant["summonerId"], participant["championId"]
                )
                active_users.append(summ_data)

        first_blood_id = None
        game_win = True
        team_id = None
        our_baron_kills = 0
        our_dragon_kills = 0
        our_herald_kills = 0
        enemy_baron_kills = 0
        enemy_dragon_kills = 0
        enemy_herald_kills = 0

        for disc_id, stats in player_stats:
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

            if stats["firstBloodKill"]:
                first_blood_id = disc_id

        return LoLGameStats(
            game=self.game,
            game_id=self.raw_data["gameId"],
            timestamp=self.raw_data["gameCreation"],
            duration=int(self.raw_data["gameDuration"]),
            win=int(game_win),
            kills_by_our_team=kills_per_team[our_team],
            guild_id=self.guild_id,
            players_in_game=active_users,
            all_player_stats=player_stats,
            first_blood=first_blood_id,
            map_id=self.raw_data["mapId"],
            team_id=team_id,
            damage_by_our_team=damage_per_team[our_team],
            our_baron_kills=our_baron_kills,
            our_dragon_kills=our_dragon_kills,
            our_herald_kills=our_herald_kills,
            enemy_baron_kills=enemy_baron_kills,
            enemy_dragon_kills=enemy_dragon_kills,
            enemy_herald_kills=enemy_herald_kills,
        )

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

def get_finished_game_summary(
    data: dict,
    summ_ids: list[str],
    riot_api: RiotAPIClient
):
    """
    Get a brief text that summaries a player's performance in a finished game.

    :param data:        Dictionary containing un-filtered data about a finished
                        game fetched from Riot League API
    :param summ_ids:    List of summoner ids belonging to a player,
                        for which to get the summary for
    :parma riot_api:    Riot API client instance
    """
    stats = get_player_stats(data, summ_ids)

    champ_played = riot_api.get_champ_name(stats["championId"])
    if champ_played is None:
        champ_played = "Unknown Champ (Rito pls)"

    date = datetime.fromtimestamp(data["gameCreation"] / 1000.0).strftime("%Y/%m/%d")
    duration = data["gameDuration"]
    dt_1 = datetime.fromtimestamp(time())
    dt_2 = datetime.fromtimestamp(time() + duration)
    fmt_duration = format_duration(dt_1, dt_2)

    return (
        f"{champ_played} with a score of {stats['kills']}/" +
        f"{stats['deaths']}/{stats['assists']} on {date} in a {fmt_duration} long game"
    )

def get_active_game_summary(data, summ_id, summoners, riot_api):
    """
    Extract data about a currently active game.

    :param data:    Data aquired from Riot's API about an active game
    :summ_id:       The summoner ID that we should extract data for in the game
    :summoners:     List of summoners/users that are registered with Int-Far.
                    Any summoners in the game not part of this list is filtered out
    :riot_api       Riot API Client instance. Used to get champion name of the player
    """
    champions = {}
    users_in_game = []
    for participant in data["participants"]:
        for disc_id, _, summoner_ids in summoners:
            if participant["summonerId"] in summoner_ids:
                champ_id = participant["championId"]
                champ_played = riot_api.get_champ_name(champ_id)
                if champ_played is None:
                    champ_played = "Unknown Champ (Rito pls)"
                champions[participant["summonerId"]] = (participant["summonerName"], champ_played)
                users_in_game.append((disc_id, champ_id))

    game_start = data["gameStartTime"] / 1000
    if game_start > 0:
        now = time()
        dt_1 = datetime.fromtimestamp(game_start)
        dt_2 = datetime.fromtimestamp(now)
        fmt_duration = format_duration(dt_1, dt_2) + " "
    else:
        fmt_duration = ""
    game_mode = data["gameMode"]

    response = f"{fmt_duration}in a {game_mode} game, playing {champions[summ_id][1]}.\n"
    if len(champions) > 1:
        response += "He is playing with:"
        for other_id in champions:
            if other_id != summ_id:
                name, champ = champions[other_id]
                response += f"\n - {name} ({champ})"

    return response, users_in_game
