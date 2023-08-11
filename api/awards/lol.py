from mhooge_flask.logging import logger

from api.award_qualifiers import AwardQualifiers
from api import util as api_util
from api.config import Config
from api.game_stats import get_outlier
from api.database import Database

class LoLAwardQualifiers(AwardQualifiers):
    def get_big_doinks(self):
        """
        Returns a string describing people who have been redeemed by playing
        exceptionally well.
        Criteria for being redeemed:
            - Having a KDA of 10 or more
            - Getting 20 kills or more
            - Doing more damage than the rest of the team combined
            - Getting a penta-kill
            - Having a vision score of 100+
            - Having a kill-participation of 80%+
            - Securing all epic monsters
            - Getting more than 8 cs/min
        """
        mentions = {} # List of mentioned users for the different criteria.
        formatted_mentions = {}

        for stats in self.parsed_game_stats.filtered_player_stats:
            mention_list = []

            if stats.kda >= 10.0:
                mention_list.append((0, api_util.round_digits(stats.kda)))

            if stats.kills >= 20:
                mention_list.append((1, stats.kills))

            if stats.damage > stats["damage_by_team"] - stats.damage:
                mention_list.append((2, stats.damage))

            if stats.pentakills > 0:
                mention_list.append((3, stats.pentakills))

            if stats.vision_score > 100:
                mention_list.append((4, stats.vision_score))

            if stats.kp > 80:
                mention_list.append((5, stats.kp))

            own_epics = (
                self.parsed_game_stats.our_baron_kills +
                self.parsed_game_stats.our_dragon_kills +
                self.parsed_game_stats.our_herald_kills
            )
            enemy_epics = (
                self.parsed_game_stats.enemy_baron_kills +
                self.parsed_game_stats.enemy_dragon_kills +
                self.parsed_game_stats.enemy_herald_kills
            )

            if stats.lane == "JUNGLE" and stats.role == "NONE" and own_epics > 3 and enemy_epics == 0:
                mention_list.append((6, own_epics))

            if stats.cs_per_min >= 8:
                mention_list.append((7, api_util.round_digits(stats.cs_per_min)))

            if mention_list != []:
                mentions[stats.disc_id] = mention_list
                format_str = ""

                for index in range(len(api_util.DOINKS_REASONS)):
                    has_doinks_for_stats = False
                    for stat_index, _ in mention_list:
                        if stat_index == index:
                            has_doinks_for_stats = True
                            break

                    format_str += ("1" if has_doinks_for_stats else "0")

                formatted_mentions[stats.disc_id] = format_str
                stats.doinks = format_str

        return mentions, formatted_mentions

    def get_honorable_mentions(self):
        """
        Returns players that deserve honorable mentions (questionable stats),
        for stuff that wasn't quite bad enough to be named Int-Far for.
        Honorable mentions are given for:
            - Having 0 control wards purchased
            - Being adc/mid/top/jungle and doing less than 8000 damage
            - Being adc/mid/top and having less than 5 cs/min
            - Being jungle and securing no epic monsters
        """
        mentions = {} # List of mentioned users for the different criteria.
        for stats in self.parsed_game_stats.filtered_player_stats:
            mentions[stats.disc_id] = []

            if self.parsed_game_stats.map_id != 21 and stats.vision_wards <= self.config.mentions_vision_wards:
                mentions[stats.disc_id].append((0, stats.vision_wards))

            if stats.lane != "UTILITY" and stats.damage < self.config.mentions_max_damage:
                mentions[stats.disc_id].append((1, stats.damage))

            if stats.lane != "UTILITY" and stats.lane != "JUNGLE" and stats.cs_per_min < self.config.mentions_max_cs_per_min:
                mentions[stats.disc_id].append((2, api_util.round_digits(stats.cs_per_min)))

            epic_monsters_secured = (
                self.parsed_game_stats.our_baron_kills +
                self.parsed_game_stats.our_dragon_kills +
                self.parsed_game_stats.our_herald_kills
            )

            if stats.lane == "JUNGLE" and stats.role == "NONE" and epic_monsters_secured <= self.config.mentions_epic_monsters:
                mentions[stats.disc_id].append((3, epic_monsters_secured))

        return mentions

    def get_cool_stats(self):
        """
        Returns a list of miscellaneous interesting stats for each player in the game.
        These stats include:
            - Being dead for more than 10 minutes
            - Stealing epic monsters
            - Getting a lot of turret kills
        """
        cool_stats = {}

        for stats in self.parsed_game_stats.filtered_player_stats:
            cool_stats[stats.disc_id] = []

            if stats.total_time_dead >= self.config.stats_min_time_dead:
                time_dead_mins = stats.total_time_dead // 60
                time_dead_secs = stats.total_time_dead % 60
                fmt_str = f"{time_dead_mins} mins"
                if time_dead_secs > 0:
                    fmt_str += f" and {time_dead_secs} secs"

                cool_stats[stats.disc_id].append((0, fmt_str))

            if stats.steals >= self.config.stats_min_objectives_stolen:
                cool_stats[stats.disc_id].append((1, stats.steals))

            if stats.turret_kills >= self.config.stats_min_turrets_killed:
                cool_stats[stats.disc_id].append((2, stats.turret_kills))

        return cool_stats

    def get_lifetime_stats(self, database: Database):
        """
        Returns a list of lifetime awards for each player.
        These events include:
            - A player having played a multiple of 1000 games
            - A player having won a multiple of 1000 games
            - A player having gotten Int-Far a multiple of 100 times
            - A player having gotten Doinks a multiple of 100 times
        """
        lifetime_mentions = {}

        for stats in self.parsed_game_stats:
            lifetime_mentions[stats.disc_id] = []

            game_data = database.get_games_count(self.game, stats.disc_id)
            total_games = game_data[0]
            total_wins = game_data[2]
            total_intfars = database.get_intfar_count(self.game, stats.disc_id)
            total_doinks = database.get_doinks_count(self.game, stats.disc_id)[1]

            values = [total_games, total_wins, total_intfars, total_doinks]
            moduli = [1000, 1000, 100, 100]

            for index, (val, mod) in enumerate(zip(values, moduli)):
                if val > 0 and val % mod == 0:
                    lifetime_mentions[stats.disc_id].append((index, val))

        return lifetime_mentions

    def _intfar_by_kda(self):
        """
        Returns the info of the Int-Far, if this person has a truly terrible KDA.
        This is determined by:
            - KDA being the lowest of the group
            - KDA being less than 1.3
            - Number of deaths being more than 2.
        Returns None if none of these criteria matches a registered person.
        """
        tied_intfars, tied_stats = get_outlier(
            self.parsed_game_stats.all_player_stats, "kda", include_ties=True
        )
        lowest_kda = tied_stats[0].kda
        kda_criteria = self.config.kda_lower_threshold
        death_criteria = self.config.kda_death_criteria

        potential_intfars = []
        for intfar, stats in zip(tied_intfars, tied_stats):
            if lowest_kda < kda_criteria and stats.deaths > death_criteria:
                potential_intfars.append(intfar)

        # Check if all Int-Far candidates are randos (not registered with Int-Far)
        all_intfars_randos = not any(potential_intfars)

        if potential_intfars == [] or all_intfars_randos:
            return (None, None)

        if all_intfars_randos:
            logger.info("Int-Far for low KDA goes to a random!")

        return (potential_intfars, lowest_kda)

    def _intfar_by_deaths(self):
        """
        Returns the info of the Int-Far, if this person has hecking many deaths.
        This is determined by:
            - Having the max number of deaths in the group
            - Number of deaths being more than 9.
            - KDA being less than 2.1
        Returns None if none of these criteria matches a person.
        """
        tied_intfars, tied_stats = get_outlier(
            self.parsed_game_stats.all_player_stats, "deaths", asc=False, include_ties=True
        )
        highest_deaths = tied_stats[0].deaths
        death_criteria = self.config.death_lower_threshold
        kda_criteria = self.config.death_kda_criteria

        potential_intfars = []
        for intfar, stats in zip(tied_intfars, tied_stats):
            if highest_deaths > death_criteria and stats.kda < kda_criteria:
                potential_intfars.append(intfar)

        # Check if all Int-Far candidates are randos (not registered with Int-Far)
        all_intfars_randos = not any(potential_intfars)

        if potential_intfars == [] or all_intfars_randos:
            return (None, None)

        if all_intfars_randos:
            logger.info("Int-Far for many deaths goes to a random!")

        return (potential_intfars, highest_deaths)

    def _intfar_by_kp(self):
        """
        Returns the info of the Int-Far, if this person has very low kill participation.
        This is determined by:
            - Having the lowest KP in the group
            - KP being less than 20
            - Number of kills + assists being less than 10
            - Turrets + Inhibitors destroyed < 2
            - Deaths > 2
        Returns None if none of these criteria matches a person.
        """
        tied_intfars, tied_stats = get_outlier(
            self.parsed_game_stats.filtered_player_stats, "kp", include_ties=True
        )
        lowest_kp = tied_stats[0].kp
        kp_criteria = self.config.kp_lower_threshold
        takedowns_criteria = self.config.kp_takedowns_criteria
        structures_criteria = self.config.kp_structures_criteria
        deaths_criteria = self.config.kp_deaths_criteria

        potential_intfars = []
        for intfar, stats in zip(tied_intfars, tied_stats):
            structures_destroyed = stats.turret_kills + stats.inhibitor_kills

            if (
                lowest_kp < kp_criteria
                and stats.kills + stats.assists < takedowns_criteria
                and stats.deaths > deaths_criteria
                and structures_destroyed < structures_criteria
            ):
                potential_intfars.append(intfar)

        if potential_intfars == []:
            return (None, None)

        return (potential_intfars, lowest_kp)

    def _intfar_by_vision_score(self):
        """
        Returns the info of the Int-Far, if this person has very low kill vision score.
        This is determined by:
            - Game being longer than 20 mins
            - Having the lowest vision score in the group
            - Vision score being less than 9
            - KDA being less than 3
        Returns None if none of these criteria matches a person.
        """
        time_criteria = self.config.vision_secs_lower_threshold

        if self.parsed_game_stats.duration < time_criteria:
            # If game is less than 20 minutes, we don't give out Int-Far for vision score.
            return (None, None)

        tied_intfars, tied_stats = get_outlier(
            self.parsed_game_stats.filtered_player_stats, "vision_score", include_ties=True
        )
        lowest_score = tied_stats[0].vision_score
        vision_criteria = self.config.vision_score_lower_threshold
        kda_criteria = self.config.vision_kda_criteria

        potential_intfars = []
        for intfar, stats in zip(tied_intfars, tied_stats):
            if lowest_score < vision_criteria and stats.kda < kda_criteria:
                potential_intfars.append(intfar)

        if potential_intfars == []:
            return (None, None)

        return (potential_intfars, lowest_score)

    def resolve_intfar_ties(self, intfar_data, max_count):
        """
        Resolve a potential tie in who should be Int-Far. This can happen if two or more
        people meet the same criteria, with the same stats within these criteria.
        If so, the one with either most deaths or least gold gets chosen as Int-Far.
        """
        ties = []
        for disc_id in intfar_data:
            if len(intfar_data[disc_id]) == max_count:
                ties.append(disc_id)

        if len(ties) == 1:
            return ties[0], False, "There are no ties."

        filtered_data = []
        for stats in self.parsed_game_stats.filtered_player_stats:
            if stats.disc_id in ties:
                filtered_data.append(stats)

        sorted_by_deaths = sorted(filtered_data, key=lambda x: x.deaths, reverse=True)
        max_count = sorted_by_deaths[0].deaths
        ties = []
        for stats in sorted_by_deaths:
            if stats.deaths == max_count:
                ties.append(stats.disc_id)
            else:
                break

        if len(ties) == 1:
            return ties[0], True, "Ties resolved by most amount of deaths."

        sorted_by_kda = sorted(filtered_data, key=lambda x: x.kda)
        max_count = sorted_by_kda[0].kda
        ties = []
        for stats in sorted_by_kda:
            if stats.kda == max_count:
                ties.append(disc_id)
            else:
                break

        if len(ties) == 1:
            return ties[0], True, "Ties resolved by lowest KDA."

        sorted_by_gold = sorted(filtered_data, key=lambda x: x.gold)
        return sorted_by_gold[0].disc_id, True, "Ties resolved by fewest gold earned."

    def get_intfar_qualifiers(self):
        intfar_kda_id, kda = self._intfar_by_kda()
        if intfar_kda_id is not None:
            logger.info("Int-Far because of KDA.")

        intfar_deaths_id, deaths = self._intfar_by_deaths()
        if intfar_deaths_id is not None:
            logger.info("Int-Far because of deaths.")

        intfar_kp_id, kp = self._intfar_by_kp()
        if intfar_kp_id is not None:
            logger.info("Int-Far because of kill participation.")

        intfar_vision_id, vision_score = None, None
        if self.parsed_game_stats.map_id != 21:
            intfar_vision_id, vision_score = self._intfar_by_vision_score()
            if intfar_vision_id is not None:
                logger.info("Int-Far because of vision score.")

        return [
            (intfar_kda_id, kda), (intfar_deaths_id, deaths),
            (intfar_kp_id, kp), (intfar_vision_id, vision_score)
        ]

    def get_intfar(self):
        intfar_details = self.get_intfar_qualifiers()

        (
            intfar_data,
            max_count_intfar,
            max_intfar_count
        ) = self.get_intfar_candidates(intfar_details)

        if max_count_intfar is None:
            return None, None, None, None

        (
            final_intfar,
            ties,
            tie_desc
        ) = self.resolve_intfar_ties(intfar_data, max_intfar_count)

        return final_intfar, intfar_data[final_intfar], ties, tie_desc

def get_cool_timeline_events(timeline_data: dict, config: Config):
    """
    Returns a list of cool/embarrasing events that happened during the course of the game.
    These events include:
        - We lost the game after being up by more than 8k gold (the big throw)
        - We won the game after being down by more than 8k gold (the epic comeback)
        - Someone had more than 4000 gold at one point
    """
    # Dictionary that maps from participantId to disc_id
    participant_dict = {
        entry["participantId"]: timeline_data["puuid_map"].get(entry["puuid"])
        for entry in timeline_data["participants"]
    }

    timeline_events = []

    biggest_gold_lead = 0
    biggest_gold_deficit = 0
    too_much_gold = {}

    # Calculate stats from timeline frames.
    for frame_data in timeline_data["frames"]:
        # Tally up our and ememy teams total gold during the game.
        our_total_gold = 0
        enemy_total_gold = 0

        for participant_id in frame_data["participantFrames"]:
            participant_data = frame_data["participantFrames"][participant_id]
            disc_id = participant_dict.get(int(participant_id))
            total_gold = participant_data["totalGold"]
            curr_gold = participant_data["currentGold"]
            our_team = (int(participant_id) > 5) ^ timeline_data["ourTeamLower"]

            # Add players gold to total for their team.
            if our_team:
                our_total_gold += total_gold
            else:
                enemy_total_gold += total_gold

            if (
                disc_id is not None
                and curr_gold > config.timeline_min_curr_gold
                and total_gold < config.timeline_min_total_gold
            ):
                # Player has enough current gold to warrant a mention.
                # If this amount of gold is more than their previous max, save it.
                curr_value_for_player = too_much_gold.get(disc_id, 0)
                too_much_gold[disc_id] = max(curr_gold, curr_value_for_player)

        gold_diff = our_total_gold - enemy_total_gold
        if gold_diff < 0: # Record max gold deficit during the game.
            biggest_gold_deficit = max(abs(gold_diff), biggest_gold_deficit) 
        else: # Record max gold lead during the game.
            biggest_gold_lead = max(gold_diff, biggest_gold_lead)

    if biggest_gold_deficit > config.timeline_min_deficit and timeline_data["gameWon"]: # Epic comeback!
        timeline_events.append((0, biggest_gold_deficit, None))
    elif biggest_gold_lead > config.timeline_min_lead and not timeline_data["gameWon"]: # Huge throw...
        timeline_events.append((1, biggest_gold_lead, None))

    for disc_id in too_much_gold:
        timeline_events.append((2, too_much_gold[disc_id], disc_id))

    return timeline_events
