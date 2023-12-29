from mhooge_flask.logging import logger

from api.award_qualifiers import AwardQualifiers
from api.util import round_digits
from api.game_stats import get_outlier

class LoLAwardQualifiers(AwardQualifiers):
    @classmethod
    def INTFAR_REASONS(cls):
        super().__doc__
        return {
            "kda": "Low KDA",
            "deaths": "Many deaths",
            "kp": "Low KP",
            "vision_score": "Low Vision Score"
        }

    @classmethod
    def INTFAR_CRITERIAS(cls):
        super().__doc__
        return {
            "kda": {
                "lower_threshold": 1.3,
                "death_criteria": 2
            },
            "deaths": {
                "lower_threshold": 9,
                "kda_criteria": 2.1
            },
            "kp": {
                "lower_threshold": 20,
                "takedowns_criteria": 10,
                "structures_criteria": 2,
                "deaths_criteria": 2
            },
            "vision_score": {
                "lower_threshold": 11,
                "kda_criteria": 3.0,
                "secs_lower_threshold": 1200
            }
        }

    @classmethod
    def INTFAR_CRITERIAS_DESC(cls):
        super().__doc__
        criterias = cls.INTFAR_CRITERIAS()
        return {
            "kda": [
                "Having the lowest KDA of the people playing (including randoms)",
                f"Having a KDA of less than {criterias['kda']['lower_threshold']}",
                f"Having more than {criterias['kda']['death_criteria']} deaths",
            ],
            "deaths": [
                "Having the most deaths of the people playing (including randoms)",
                f"Having more than {criterias['deaths']['lower_threshold']} deaths",
                f"Having less than {criterias['deaths']['kda_criteria']} KDA",
            ],
            "kp": [
                "Having the lowest KP of the people playing",
                f"Having a KP of less than {criterias['kp']['lower_threshold']}%",
                f"Having less than {criterias['kp']['takedowns_criteria']} takedowns",
                f"Having less than {criterias['kp']['structures_criteria']} structures destroyed",
                f"Having more than {criterias['kp']['deaths_criteria']} deaths",
            ],
            "vision_score": [
                "Having the lowest vision score of the people playing",
                f"Having less than {criterias['vision_score']['lower_threshold']} vision score",
                f"Having less than {criterias['vision_score']['kda_criteria']} KDA",
                f"The game being longer than {criterias['vision_score']['secs_lower_threshold'] // 60} minutes",
            ]
        }

    @classmethod
    def DOINKS_REASONS(cls):
        super().__doc__
        return {
            "kda": "KDA larger than or equal to 10",
            "kills": "20 kills or more",
            "damage": "Half of the teams damage",
            "penta": "Getting a pentakill",
            "vision_score": "Vision score larger than 100",
            "kp": "Kill participation over 80%",
            "monsters": "Securing all epic monsters (and more than 3)",
            "cs": "More than 8 cs/min"
        }

    @classmethod
    def INTFAR_FLAVOR_TEXTS(cls):
        super().__doc__
        return [
            "lowest_kda",
            "most_deaths",
            "lowest_kp",
            "lowest_vision",
        ]

    @classmethod
    def HONORABLE_MENTIONS_FLAVOR_TEXTS(cls):
        super().__doc__
        return [
            "mentions_no_vision_ward",
            "mentions_low_damage",
            "mentions_low_cs_min",
            "mentions_no_epic_monsters",
        ]

    @classmethod
    def COOL_STATS_FLAVOR_TEXTS(cls):
        super().__doc__
        return [
            "stats_time_spent_dead",
            "stats_objectives_stolen",
            "stats_turrets_killed",
            "stats_quadrakills",
        ]

    @classmethod
    def DOINKS_FLAVOR_TEXTS(cls):
        super().__doc__
        return [
            "doinks_kda",
            "doinks_kills",
            "doinks_damage",
            "doinks_penta",
            "doinks_vision_score",
            "doinks_kp",
            "doinks_jungle",
            "doinks_cs",
        ]

    @classmethod
    def TIMELINE_FLAVOR_TEXTS(cls):
        super().__doc__
        return [
            "timeline_comeback",
            "timeline_throw",
            "timeline_goldkeeper",
            "timeline_pentasteal",
            "timeline_invade_won",
            "timeline_invade_lost",
            "timeline_invade_tied",
            "timeline_anti_invade_won",
            "timeline_anti_invade_lost",
            "timeline_anti_invade_tied",
        ]

    @classmethod
    def GAME_SPECIFIC_FLAVORS(cls):
        super().__doc__
        flavors = dict(super().GAME_SPECIFIC_FLAVORS()) 
        flavors["timeline"] = cls.TIMELINE_FLAVOR_TEXTS()
        return flavors

    @classmethod
    def ALL_FLAVOR_TEXTS(cls):
        """
        Get a list of filenames for all flavor texts for LoL.
        """
        return (
            super().ALL_FLAVOR_TEXTS() + 
            cls.INTFAR_FLAVOR_TEXTS() +
            cls.HONORABLE_MENTIONS_FLAVOR_TEXTS() +
            cls.COOL_STATS_FLAVOR_TEXTS() +
            cls.TIMELINE_FLAVOR_TEXTS() +
            cls.DOINKS_FLAVOR_TEXTS()
        )

    def get_big_doinks(self):
        """
        Returns a string describing people who have earned Doinks
        by playing exceptionally well.
        Criteria for getting doinks in LoL:
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
                mention_list.append((0, round_digits(stats.kda)))

            if stats.kills >= 20:
                mention_list.append((1, stats.kills))

            if stats.damage > self.parsed_game_stats.damage_by_our_team - stats.damage:
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
                mention_list.append((7, round_digits(stats.cs_per_min)))

            if mention_list != []:
                mentions[stats.disc_id] = mention_list
                format_str = ""

                for index in range(len(self.DOINKS_REASONS())):
                    has_doinks_for_stats = False
                    for stat_index, _ in mention_list:
                        if stat_index == index:
                            has_doinks_for_stats = True
                            break

                    format_str += ("1" if has_doinks_for_stats else "0")

                formatted_mentions[stats.disc_id] = format_str

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
                mentions[stats.disc_id].append((2, round_digits(stats.cs_per_min)))

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
            - Getting one or more quadrakills (but no penta)
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

            if stats.quadrakills - stats.pentakills > 0:
                cool_stats[stats.disc_id].append((3, stats.quadrakills))

        return cool_stats

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

        blue_side = self.parsed_game_stats.team_id == 100

        if blue_side: # Blue side
            p_1 = blueside_p1
            p_2 = blueside_p2
        else: # Red side
            p_1 = redside_p1
            p_2 = redside_p2

        slope = (p_2[1] - p_1[1]) / (p_2[0] - p_1[0])
        intercept = (slope * p_1[0] - p_1[1]) * -1

        coef = slope * x + intercept - y
        
        if blue_side:
            return coef > 0

        return coef < 0

    def get_cool_timeline_events(self):
        """
        Returns a list of cool/embarrasing events that happened during the course of the game.
        These events include:
            - We lost the game after being up by more than 8k gold (the big throw)
            - We won the game after being down by more than 8k gold (the epic comeback)
            - Someone had more than 4000 gold at one point
            - Someone stole a pentakill from someone else
        """
        timeline_data = self.parsed_game_stats.get_filtered_timeline_stats(self.parsed_game_stats.timeline_data)

        # Dictionary that maps from participantId to disc_id
        participant_dict = {
            entry["participantId"]: timeline_data["puuid_map"].get(entry["puuid"])
            for entry in timeline_data["participants"]
        }

        timeline_events = []

        biggest_gold_lead = 0
        biggest_gold_deficit = 0
        too_much_gold = {}
        game_win = self.parsed_game_stats.win == 1
        any_quadrakills = any(
            player_stats.quadrakills > 0
            for player_stats in self.parsed_game_stats.filtered_player_stats
        )
        curr_multikill = {}
        stolen_penta_victims = {}
        stolen_penta_scrubs = {}
        invade_kills = 0
        anti_invade_kills = 0
        invade_victims = 0
        anti_invade_victims = 0

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

                if disc_id is None:
                    continue

                if (
                    curr_gold > self.config.timeline_min_curr_gold
                    and total_gold < self.config.timeline_min_total_gold
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

            if frame_data["timestamp"] < 130_000:
                # Check whether we invaded at the start of the game
                # and either got kills or got killed
                for event in frame_data.get("events", []):
                    if event["type"] != "CHAMPION_KILL":
                        continue

                    our_kill = (int(event["victimId"]) < 5) ^ timeline_data["ourTeamLower"]
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

        if biggest_gold_deficit > self.config.timeline_min_deficit and game_win: # Epic comeback!
            timeline_events.append((0, biggest_gold_deficit, None))
        elif biggest_gold_lead > self.config.timeline_min_lead and not game_win: # Huge throw...
            timeline_events.append((1, biggest_gold_lead, None))

        for disc_id in too_much_gold:
            timeline_events.append((2, too_much_gold[disc_id], disc_id))

        for disc_id in stolen_penta_scrubs:
            pentakills = "pentakill" if stolen_penta_scrubs[disc_id] == 1 else "pentakills"
            victim_summ_names = []
            for victim_id in stolen_penta_victims[disc_id]:
                for summ_info in self.parsed_game_stats.players_in_game:
                    if summ_info["disc_id"] == victim_id:
                        victim_summ_names.append(summ_info["summ_name"])
                        break

            victims = " and ".join(victim_summ_names)
            desc = f"{stolen_penta_scrubs[disc_id]} {pentakills} from {victims}"
    
            timeline_events.append((3, desc, disc_id))

        if invade_kills > 0 or invade_victims > 0:
            if invade_kills > invade_victims: # We won an invade
                timeline_events.append((4, invade_kills, None))
            elif invade_kills < invade_victims: # We lost an invade
                timeline_events.append((5, invade_victims, None))
            else: # We got an equal amount of kills in an invade
                timeline_events.append((6, invade_kills, None))

        elif anti_invade_kills > 0 or anti_invade_victims > 0:
            if anti_invade_kills > anti_invade_victims: # We won an anti-invade
                timeline_events.append((7, anti_invade_kills, None))
            elif anti_invade_kills < anti_invade_victims: # We lost an anti-invade
                timeline_events.append((8, anti_invade_victims, None))
            else: # We got an equal amount of kills when being invaded
                timeline_events.append((9, anti_invade_kills, None))

        return timeline_events

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

        if tied_intfars is None: # No data for stat
            return None, None

        lowest_kda = tied_stats[0].kda
        criterias = self.INTFAR_CRITERIAS()["kda"]

        kda_criteria = criterias["lower_threshold"]
        death_criteria = criterias["death_criteria"]

        potential_intfars = []
        for intfar, stats in zip(tied_intfars, tied_stats):
            if lowest_kda < kda_criteria and stats.deaths > death_criteria:
                potential_intfars.append(intfar)


        if potential_intfars == []:
            return (None, None)

        # Check if all Int-Far candidates are randos (not registered with Int-Far)
        all_intfars_randos = not any(potential_intfars)
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

        if tied_intfars is None: # No data for stat
            return None, None

        highest_deaths = tied_stats[0].deaths
        criterias = self.INTFAR_CRITERIAS()["deaths"]

        death_criteria = criterias["lower_threshold"]
        kda_criteria = criterias["kda_criteria"]

        potential_intfars = []
        for intfar, stats in zip(tied_intfars, tied_stats):
            if highest_deaths > death_criteria and stats.kda < kda_criteria:
                potential_intfars.append(intfar)

        if potential_intfars == []:
            return (None, None)

        # Check if all Int-Far candidates are randos (not registered with Int-Far)
        all_intfars_randos = not any(potential_intfars)
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

        if tied_intfars is None: # No data for stat
            return None, None

        lowest_kp = tied_stats[0].kp
        criterias = self.INTFAR_CRITERIAS()["kp"]

        kp_criteria = criterias["lower_threshold"]
        takedowns_criteria = criterias["takedowns_criteria"]
        structures_criteria = criterias["structures_criteria"]
        deaths_criteria = criterias["deaths_criteria"]

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
        criterias = self.INTFAR_CRITERIAS()["vision_score"]
        time_criteria = criterias["secs_lower_threshold"]

        if self.parsed_game_stats.duration < time_criteria:
            # If game is less than 20 minutes, we don't give out Int-Far for vision score.
            return (None, None)

        tied_intfars, tied_stats = get_outlier(
            self.parsed_game_stats.filtered_player_stats, "vision_score", include_ties=True
        )

        if tied_intfars is None: # No data for stat
            return None, None

        lowest_score = tied_stats[0].vision_score

        vision_criteria = criterias["lower_threshold"]
        kda_criteria = criterias["kda_criteria"]

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
