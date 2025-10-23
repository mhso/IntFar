from mhooge_flask.logging import logger

from api.game_data.lol import LoLPlayerStats
from api.award_qualifiers import AwardQualifiers
from api.util import round_digits
from api.game_stats import get_outlier
from api.game_database import GameDatabase

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
            "damage": "Half of the teams damage (and more than 10k)",
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
    def RANK_MENTIONS_FLAVOR_TEXTS(cls):
        super().__doc__
        return [
            "rank_demotion",
            "rank_promotion",
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
            "timeline_no_items",
            "timeline_invade_won",
            "timeline_invade_lost",
            "timeline_invade_tied",
            "timeline_anti_invade_won",
            "timeline_anti_invade_lost",
            "timeline_anti_invade_tied",
        ]

    @classmethod
    def ALL_FLAVOR_TEXTS(cls):
        """
        Get a list of filenames for all flavor texts for LoL.
        """
        return (
            super().ALL_FLAVOR_TEXTS() + 
            cls.INTFAR_FLAVOR_TEXTS() +
            cls.HONORABLE_MENTIONS_FLAVOR_TEXTS() +
            cls.RANK_MENTIONS_FLAVOR_TEXTS() +
            cls.COOL_STATS_FLAVOR_TEXTS() +
            cls.TIMELINE_FLAVOR_TEXTS() +
            cls.DOINKS_FLAVOR_TEXTS()
        )

    def get_lifetime_stats(self, database: GameDatabase):
        """
        Returns a list of LoL-specific lifetime awards for each player.
        These events include:
            - A player having played a multiple of 100 games on a champion
            - A player having played every champion
        """
        lifetime_mentions = super().get_lifetime_stats(database)

        for stats in self.parsed_game_stats.filtered_player_stats:
            games_on_champ = database.get_played_count(stats.disc_id, stats.champ_id)
            unique_champs = len(database.get_played_ids(stats.disc_id))

            if games_on_champ % 100 == 0:
                champ_name = self.api_client.get_playable_name(stats.champ_id)
                description = f"{games_on_champ}th game on {champ_name}"
                lifetime_mentions[stats.disc_id].append((4, description))

            elif games_on_champ == 1 and unique_champs == self.api_client.playable_count:
                lifetime_mentions[stats.disc_id].append((5, unique_champs))

        return lifetime_mentions

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

            if stats.damage > 10_000 and stats.damage > self.parsed_game_stats.damage_by_our_team - stats.damage:
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
                self.parsed_game_stats.our_herald_kills +
                self.parsed_game_stats.our_atakhan_kills +
                (1 if self.parsed_game_stats.our_grub_kills >= 2 else 0)
            )
            enemy_epics = (
                self.parsed_game_stats.enemy_baron_kills +
                self.parsed_game_stats.enemy_dragon_kills +
                self.parsed_game_stats.enemy_herald_kills +
                self.parsed_game_stats.enemy_atakhan_kills +
                (1 if self.parsed_game_stats.enemy_grub_kills >= 2 else 0)
            )

            if stats.lane == "JUNGLE" and stats.position == "NONE" and own_epics > 3 and enemy_epics == 0:
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

            if stats.lane == "JUNGLE" and stats.position == "NONE" and epic_monsters_secured <= self.config.mentions_epic_monsters:
                mentions[stats.disc_id].append((3, epic_monsters_secured))

        return mentions

    def get_rank_mentions(self, prev_ranks: dict[int, tuple[str, str]]) -> dict[int, tuple[int, int]]:
        curr_ranks = {
            stats.disc_id: (stats.rank_solo, stats.rank_flex)
            for stats in self.parsed_game_stats.filtered_player_stats
        }

        divisions = [
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

        rank_mentions = {}
        for disc_id in curr_ranks:
            for prev_rank, curr_rank in zip(prev_ranks[disc_id], curr_ranks[disc_id]):
                if prev_rank is None or curr_rank is None:
                    continue

                prev_division = divisions.index(prev_rank.split("_")[0])
                curr_division = divisions.index(curr_rank.split("_")[0])
                if curr_division < prev_division: # Demotion
                    rank_mentions[disc_id] = (0, curr_division)
                elif curr_division > prev_division: # Promotion
                    rank_mentions[disc_id] = (1, curr_division - 1)

        return rank_mentions

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

            if stats.total_time_dead and stats.total_time_dead >= self.config.stats_min_time_dead:
                time_dead_mins = stats.total_time_dead // 60
                time_dead_secs = stats.total_time_dead % 60
                fmt_str = f"{time_dead_mins} mins"
                if time_dead_secs > 0:
                    fmt_str += f" and {time_dead_secs} secs"

                cool_stats[stats.disc_id].append((0, fmt_str))

            if stats.steals and stats.steals >= self.config.stats_min_objectives_stolen:
                cool_stats[stats.disc_id].append((1, stats.steals))

            if stats.turret_kills >= self.config.stats_min_turrets_killed:
                cool_stats[stats.disc_id].append((2, stats.turret_kills))

            if stats.quadrakills - stats.pentakills > 0:
                cool_stats[stats.disc_id].append((3, stats.quadrakills))

        return cool_stats

    def get_cool_timeline_events(self):
        """
        Returns a list of cool/embarrasing events that happened during the course of the game.
        These events include:
            - We lost the game after being up by more than 8k gold (the big throw)
            - We won the game after being down by more than 8k gold (the epic comeback)
            - Someone had more than 4000 gold at one point
            - Someone stole a pentakill from someone else
        """
        timeline_events = []
        game_win = self.parsed_game_stats.win == 1

        # Max gold lead and deficit
        biggest_gold_lead = self.parsed_game_stats.timeline_data["biggest_gold_lead"]
        biggest_gold_deficit = self.parsed_game_stats.timeline_data["biggest_gold_deficit"]
        if biggest_gold_deficit > self.config.timeline_min_deficit and game_win: # Epic comeback!
            timeline_events.append((0, biggest_gold_deficit, None))
        elif biggest_gold_lead > self.config.timeline_min_lead and not game_win: # Huge throw...
            timeline_events.append((1, biggest_gold_lead, None))

        # Max current gold for player
        max_curr_gold = self.parsed_game_stats.timeline_data["max_current_gold"]
        player_total_gold = self.parsed_game_stats.timeline_data["player_total_gold"]
        for disc_id in max_curr_gold:
            if (
                max_curr_gold[disc_id] > self.config.timeline_min_curr_gold
                and player_total_gold[disc_id] < self.config.timeline_min_total_gold
            ):
                timeline_events.append((2, max_curr_gold[disc_id], disc_id))

        # Stolen pentakills
        stolen_penta_scrubs = self.parsed_game_stats.timeline_data["stolen_penta_scrubs"]
        stolen_penta_victims = self.parsed_game_stats.timeline_data["stolen_penta_victims"]
        for disc_id in stolen_penta_scrubs:
            pentakills = "pentakill" if stolen_penta_scrubs[disc_id] == 1 else "pentakills"
            victim_summ_names = []
            for victim_id in stolen_penta_victims[disc_id]:
                for summ_info in self.parsed_game_stats.players_in_game:
                    if summ_info["disc_id"] == victim_id:
                        victim_summ_names.append(summ_info["player_name"][0])
                        break

            victims = " and ".join(victim_summ_names)
            desc = f"{stolen_penta_scrubs[disc_id]} {pentakills} from {victims}"
    
            timeline_events.append((3, desc, disc_id))

        # People forgetting to buy items at the start of the game
        people_forgetting_items = self.parsed_game_stats.timeline_data["people_forgetting_items"]
        for disc_id in people_forgetting_items:
            timeline_events.append((4, None, disc_id))

        # Invade kills and deaths
        invade_kills = self.parsed_game_stats.timeline_data["invade_kills"]
        anti_invade_kills = self.parsed_game_stats.timeline_data["anti_invade_kills"]
        invade_victims = self.parsed_game_stats.timeline_data["invade_victims"]
        anti_invade_victims = self.parsed_game_stats.timeline_data["anti_invade_victims"]

        invade_most_relevant = invade_kills + invade_victims > anti_invade_kills + anti_invade_victims

        if invade_most_relevant and (invade_kills > 0 or invade_victims > 0):
            if invade_kills > invade_victims: # We won an invade
                timeline_events.append((5, invade_kills, None))
            elif invade_kills < invade_victims: # We lost an invade
                timeline_events.append((6, invade_victims, None))
            else: # We got an equal amount of kills in an invade
                timeline_events.append((7, invade_kills, None))

        elif anti_invade_kills > 0 or anti_invade_victims > 0:
            if anti_invade_kills > anti_invade_victims: # We won an anti-invade
                timeline_events.append((8, anti_invade_kills, None))
            elif anti_invade_kills < anti_invade_victims: # We lost an anti-invade
                timeline_events.append((9, anti_invade_victims, None))
            else: # We got an equal amount of kills when being invaded
                timeline_events.append((10, anti_invade_kills, None))

        return timeline_events

    def _intfar_by_kda(self) -> list[LoLPlayerStats]:
        """
        Returns the info of the Int-Far, if this person has a truly terrible KDA.
        This is determined by:
            - KDA being the lowest of the group
            - KDA being less than 1.3
            - Number of deaths being more than 2.
        Returns None if none of these criteria matches a registered person.
        """
        tied_intfars = get_outlier(
            self.parsed_game_stats.all_player_stats, "kda", include_ties=True
        )

        if tied_intfars is None: # No data for stat
            return None

        lowest_kda = tied_intfars[0].kda
        criterias = self.INTFAR_CRITERIAS()["kda"]

        kda_criteria = criterias["lower_threshold"]
        death_criteria = criterias["death_criteria"]

        potential_intfars = []
        for stats in tied_intfars:
            if lowest_kda < kda_criteria and stats.deaths > death_criteria:
                potential_intfars.append(stats)

        if potential_intfars == []:
            return None

        # Check if all Int-Far candidates are randos (not registered with Int-Far)
        all_intfars_randos = not any(stats.disc_id for stats in potential_intfars)
        if all_intfars_randos:
            logger.info("Int-Far for low KDA goes to a random!")

        return potential_intfars

    def _intfar_by_deaths(self) -> list[LoLPlayerStats]:
        """
        Returns the info of the Int-Far, if this person has hecking many deaths.
        This is determined by:
            - Having the max number of deaths in the group
            - Number of deaths being more than 9.
            - KDA being less than 2.1
        Returns None if none of these criteria matches a person.
        """
        tied_intfars = get_outlier(
            self.parsed_game_stats.all_player_stats, "deaths", asc=False, include_ties=True
        )

        if tied_intfars is None: # No data for stat
            return None

        highest_deaths = tied_intfars[0].deaths
        criterias = self.INTFAR_CRITERIAS()["deaths"]

        death_criteria = criterias["lower_threshold"]
        kda_criteria = criterias["kda_criteria"]

        potential_intfars = []
        for stats in tied_intfars:
            if highest_deaths > death_criteria and stats.kda < kda_criteria:
                potential_intfars.append(stats)

        if potential_intfars == []:
            return None

        # Check if all Int-Far candidates are randos (not registered with Int-Far)
        all_intfars_randos = not any(stats.disc_id for stats in potential_intfars)
        if all_intfars_randos:
            logger.info("Int-Far for many deaths goes to a random!")

        return potential_intfars

    def _intfar_by_kp(self) -> list[LoLPlayerStats]:
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
        tied_intfars = get_outlier(
            self.parsed_game_stats.filtered_player_stats, "kp", include_ties=True
        )

        if tied_intfars is None: # No data for stat
            return None, None

        lowest_kp = tied_intfars[0].kp
        criterias = self.INTFAR_CRITERIAS()["kp"]

        kp_criteria = criterias["lower_threshold"]
        takedowns_criteria = criterias["takedowns_criteria"]
        structures_criteria = criterias["structures_criteria"]
        deaths_criteria = criterias["deaths_criteria"]

        potential_intfars = []
        for stats in tied_intfars:
            structures_destroyed = stats.turret_kills + stats.inhibitor_kills

            if (
                lowest_kp < kp_criteria
                and stats.kills + stats.assists < takedowns_criteria
                and stats.deaths > deaths_criteria
                and structures_destroyed < structures_criteria
            ):
                potential_intfars.append(stats)

        if potential_intfars == []:
            return None

        return potential_intfars

    def _intfar_by_vision_score(self) -> list[LoLPlayerStats]:
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
            return None

        tied_intfars = get_outlier(
            self.parsed_game_stats.filtered_player_stats, "vision_score", include_ties=True
        )

        if tied_intfars is None: # No data for stat
            return None

        lowest_score = tied_intfars[0].vision_score

        vision_criteria = criterias["lower_threshold"]
        kda_criteria = criterias["kda_criteria"]

        potential_intfars = []
        for stats in tied_intfars:
            if lowest_score < vision_criteria and stats.kda < kda_criteria:
                potential_intfars.append(stats)

        if potential_intfars == []:
            return None

        return potential_intfars

    def resolve_intfar_ties(self, intfar_data, max_count):
        """
        Resolve a potential tie in who should be Int-Far. This can happen if two or more
        people meet the same criteria, with the same stats within these criteria.
        If so, the one with either most deaths or least gold gets chosen as Int-Far.
        If so, the one with either most deaths, lowest kda, or least gold gets chosen as Int-Far.
        """
        ties = []
        for player_id in intfar_data:
            if len(intfar_data[player_id]) == max_count:
                for stats in self.parsed_game_stats.all_player_stats:
                    if stats.player_id == player_id:
                        ties.append(stats)
                        break

        if len(ties) == 1:
            return ties[0].disc_id, ties[0].player_id, False, "There are no ties."

        sorted_by_deaths = sorted(ties, key=lambda x: x.deaths, reverse=True)
        max_count = sorted_by_deaths[0].deaths

        ties = []
        for stats in sorted_by_deaths:
            if stats.deaths == max_count:
                ties.append(stats)
            else:
                break

        if len(ties) == 1:
            return ties[0].disc_id, ties[0].player_id, True, "Ties resolved by most amount of deaths."

        sorted_by_kda = sorted(ties, key=lambda x: x.kda)
        max_count = sorted_by_kda[0].kda
        ties = []
        for stats in sorted_by_kda:
            if stats.kda == max_count:
                ties.append(stats)
            else:
                break

        if len(ties) == 1:
            return ties[0].disc_id, ties[0].player_id, True, "Ties resolved by lowest KDA."

        sorted_by_gold = sorted(ties, key=lambda x: x.gold)
        return sorted_by_gold[0].disc_id, sorted_by_gold[0].player_id, True, "Ties resolved by fewest gold earned."

    def get_intfar_qualifiers(self):
        intfar_kda = self._intfar_by_kda()
        if intfar_kda is not None:
            logger.info("Int-Far because of KDA.")

        intfar_deaths = self._intfar_by_deaths()
        if intfar_deaths is not None:
            logger.info("Int-Far because of deaths.")

        intfar_kp = self._intfar_by_kp()
        if intfar_kp is not None:
            logger.info("Int-Far because of kill participation.")

        intfar_vision = None
        if self.parsed_game_stats.map_id != 21:
            intfar_vision = self._intfar_by_vision_score()
            if intfar_vision is not None:
                logger.info("Int-Far because of vision score.")

        return [
            ("kda", intfar_kda), ("deaths", intfar_deaths),
            ("kp", intfar_kp), ("vision_score", intfar_vision)
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
            intfar_disc_id,
            intfar_player_id,
            ties,
            tie_desc
        ) = self.resolve_intfar_ties(intfar_data, max_intfar_count)

        return intfar_disc_id, intfar_data.get(intfar_player_id), ties, tie_desc
