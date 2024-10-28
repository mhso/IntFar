from mhooge_flask.logging import logger

from api.game_data.cs2 import CS2PlayerStats
from api.award_qualifiers import AwardQualifiers
from api.game_stats import get_outlier
from api.util import round_digits

class CS2AwardQualifiers(AwardQualifiers):
    @classmethod
    def INTFAR_REASONS(cls):
        super().__doc__
        return {
            "kda": "Low KDA",
            "mvps": "No MVPs",
            "adr": "Low ADR",
            "score": "Low score"
        }

    @classmethod
    def INTFAR_CRITERIAS(cls):
        super().__doc__
        return {
            "kda": {
                "lower_threshold": 0.5,
                "deaths_criteria": 5
            },
            "mvps": {
                "lower_threshold": 1,
                "kda_criteria": 1.25,
                "rounds_criteria": 12
            },
            "adr": {
                "lower_threshold": 30,
                "deaths_criteria": 3
            },
            "score": {
                "lower_threshold": 20,
                "kda_criteria": 1.25,
                "rounds_criteria": 12
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
                f"Having more than {criterias['kda']['deaths_criteria']} deaths",
            ],
            "mvps": [
                "Having the least mvps of the people playing (including randoms)",
                f"Getting no MVPs in the entire game",
                f"Having less than {criterias['mvps']['kda_criteria']} KDA",
                f"The game had more than {criterias['mvps']['rounds_criteria']} rounds",
            ],
            "adr": [
                "Having the lowest ADR of the people playing",
                f"Having an ADR of less than {criterias['adr']['lower_threshold']}",
                f"Having more than {criterias['adr']['deaths_criteria']} deaths",
            ],
            "score": [
                "Having the lowest score of the people playing",
                f"Having a score of less than {criterias['score']['lower_threshold']}",
                f"Having less than {criterias['score']['kda_criteria']} KDA",
                f"The game had more than {criterias['score']['rounds_criteria']} rounds",
            ]
        }

    @classmethod
    def DOINKS_REASONS(cls):
        super().__doc__
        return {
            "kda": "KDA larger than or equal to 2.5",
            "kills": "25 kills or more",
            "headshot": "Headshot percentage of 60% or higher (min. 8 kills)",
            "adr": "120 or more ADR",
            "utility": "250 or more utility damage",
            "mvp": "6 or more MVPs",
            "entries": "8 or more entry-frags",
            "ace": "Getting an ace",
            "clutch": "Clutching a 1v4",
            "ace_clutch": "Clutching and acing a 1v5"
        }

    @classmethod
    def INTFAR_FLAVOR_TEXTS(cls):
        super().__doc__
        return [
            "lowest_kda",
            "no_mvps",
            "lowest_adr",
            "lowest_score",
        ]

    @classmethod
    def HONORABLE_MENTIONS_FLAVOR_TEXTS(cls):
        super().__doc__
        return [
            "mentions_teamkills",
            "mentions_teamflashes",
            "mentions_suicides",
            "mentions_accuracy",
            "mentions_deaths",
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
            "stats_assists",
            "stats_flashes",
            "stats_4ks",
            "stats_clutches"
        ]

    @classmethod
    def DOINKS_FLAVOR_TEXTS(cls):
        super().__doc__
        return [
            "doinks_kda",
            "doinks_kills",
            "doinks_headshot",
            "doinks_adr",
            "doinks_utility",
            "doinks_mvp",
            "doinks_entries",
            "doinks_ace",
            "doinks_clutch",
            "doinks_ace_clutch",
        ]

    @classmethod
    def TIMELINE_FLAVOR_TEXTS(cls):
        super().__doc__
        return [
            "timeline_comeback",
            "timeline_throw",
        ]

    @classmethod
    def ALL_FLAVOR_TEXTS(cls):
        """
        Get a list of filenames for all flavor texts for CS2.
        """
        return (
            super().ALL_FLAVOR_TEXTS() +
            cls.INTFAR_FLAVOR_TEXTS() +
            cls.HONORABLE_MENTIONS_FLAVOR_TEXTS() +
            cls.COOL_STATS_FLAVOR_TEXTS() +
            cls.TIMELINE_FLAVOR_TEXTS() +
            cls.DOINKS_FLAVOR_TEXTS()
        )

    def get_big_doinks(self) -> tuple[dict[int, list[tuple]], dict[int, str]]:
        """
        Returns a string describing people who have earned Doinks
        by playing exceptionally well.
        Criteria for getting doinks in CS2:
            - Having a KDA of 2.5 or more
            - Getting 25 kills or more
            - Having a headshot percentage of 60% or more
            - Having an ADR of 120 or more
            - Doing 250 or more damage with utility
            - Getting 6 or more MVPs
            - Getting 8 or more entry frags
            - Getting one or more aces
            - Clutching one or more 1v4s
            - Clutching one or more 1v5s
        """
        mentions = {} # List of mentioned users for the different criteria.
        formatted_mentions = {}

        for stats in self.parsed_game_stats.filtered_player_stats:
            mention_list = []

            if stats.kda >= 2.5:
                mention_list.append((0, round_digits(stats.kda)))

            if stats.kills >= 25:
                mention_list.append((1, stats.kills))

            if stats.headshot_pct >= 60 and stats.kills >= 10:
                mention_list.append((2, stats.headshot_pct))

            if stats.adr is not None and stats.adr >= 120:
                mention_list.append((3, stats.adr))

            if stats.utility_damage is not None and stats.utility_damage >= 250:
                mention_list.append((4, stats.utility_damage))

            if stats.mvps >= 6:
                mention_list.append((5, stats.mvps))

            if stats.entries is not None and stats.entries >= 8:
                mention_list.append((6, stats.entries))

            if stats.aces is not None and stats.aces > 0:
                mention_list.append((7, stats.aces))

            if stats.one_v_fours_won is not None and stats.one_v_fours_won > 0:
                mention_list.append((8, stats.one_v_fours_won))

            if stats.one_v_fives_won is not None and stats.one_v_fives_won > 0:
                mention_list.append((9, stats.one_v_fives_won))

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
            - Killing teammates
            - Flashing teammates
            - Suiciding
            - Having very low accuracy
            - Dying in more than 80% of the rounds
        """
        mentions = {} # List of mentioned users for the different criteria.
        for stats in self.parsed_game_stats.filtered_player_stats:
            mentions[stats.disc_id] = []

            if stats.team_kills is not None and stats.team_kills > 1:
                mentions[stats.disc_id].append((0, stats.team_kills))

            if stats.teammates_flashed is not None and stats.teammates_flashed > 15:
                mentions[stats.disc_id].append((1, stats.teammates_flashed))

            if stats.suicides is not None and stats.suicides > 0:
                mentions[stats.disc_id].append((2, stats.suicides))

            if stats.accuracy is not None and stats.accuracy < 10:
                mentions[stats.disc_id].append((3, stats.accuracy))

            total_rounds = self.parsed_game_stats.rounds_us + self.parsed_game_stats.rounds_them
            if stats.deaths / total_rounds > 0.85:
                mentions[stats.disc_id].append((4, int((stats.deaths / total_rounds) * 100)))

        return mentions

    def get_rank_mentions(self, prev_ranks: dict[int, str]) -> dict[int, tuple[int, int]]:
        return {}

    def get_cool_stats(self):
        """
        Returns a list of miscellaneous interesting stats for each player in the game.
        These stats include:
            - Having more than 8 assists
            - Having more than 18 enemies flashed
            - Having more than 1 4K
            - Winning more than 60% of clutches (and being in more than 2)
        """
        cool_stats = {}

        for stats in self.parsed_game_stats.filtered_player_stats:
            cool_stats[stats.disc_id] = []

            if stats.assists > 8:
                cool_stats[stats.disc_id].append((0, stats.assists))

            if stats.enemies_flashed is not None and stats.enemies_flashed > 18:
                cool_stats[stats.disc_id].append((1, stats.enemies_flashed))

            if stats.quads is not None and stats.quads > 1:
                cool_stats[stats.disc_id].append((2, stats.quads))

            clutches_attempted_keys = [
                "one_v_ones_tried",
                "one_v_twos_tried",
                "one_v_threes_tried",
                "one_v_fours_tried",
                "one_v_fives_tried",
            ]
            clutches_won_keys = [
                "one_v_ones_won",
                "one_v_twos_won",
                "one_v_threes_won",
                "one_v_fours_won",
                "one_v_fives_won",
            ]
            if all(getattr(stats, stat) is not None for stat in clutches_attempted_keys + clutches_won_keys):
                num_clutches_attempted = sum(getattr(stats, stat) for stat in clutches_attempted_keys)
                num_clutches_won = sum(getattr(stats, stat) for stat in clutches_won_keys)

                if num_clutches_attempted > 2 and num_clutches_won / num_clutches_attempted > 0.60:
                    clutch_pct = int((num_clutches_won / num_clutches_attempted) * 100)
                    clutch_desc = f"{clutch_pct}% of {num_clutches_attempted}"
                    cool_stats[stats.disc_id].append((3, clutch_desc))

        return cool_stats

    def get_cool_timeline_events(self):
        """
        Returns a list of cool/embarrasing events that happened during the course of the game.
        These events include:
            - We lost the game after being up by more than 7 rounds (the big throw)
            - We won the game after being down by more than 7 rounds (the epic comeback)
        """
        timeline_events = []

        # Epic comeback!
        if self.parsed_game_stats.biggest_deficit > 7 and self.parsed_game_stats.win == 1:
            timeline_events.append((0, self.parsed_game_stats.biggest_deficit, None))

        # Huge throw...
        if self.parsed_game_stats.biggest_lead > 7 and self.parsed_game_stats.win != 1:
            timeline_events.append((1, self.parsed_game_stats.biggest_lead, None))

        return timeline_events

    def _intfar_by_kda(self) -> list[CS2PlayerStats]:
        """
        Returns the info of the Int-Far, if this person has a truly terrible KDA.
        This is determined by:
            - KDA being the lowest of the group
            - KDA being less than 0.5
            - Number of deaths being more than 5
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
        death_criteria = criterias["deaths_criteria"]

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

    def _intfar_by_mvps(self) -> list[CS2PlayerStats]:
        """
        Returns the info of the Int-Far, if this person has least MVPs.
        This is determined by:
            - Having the lowest amount of MVPs in the group
            - Number of MVPs being 0
            - KDA being less than 1.25
            - Rounds played in the game being more than 12
        Returns None if none of these criteria matches a person.
        """
        criterias = self.INTFAR_CRITERIAS()["mvps"]
        rounds_criteria = criterias["rounds_criteria"]

        if self.parsed_game_stats.rounds_us + self.parsed_game_stats.rounds_them <= rounds_criteria:
            # If game lasted less than 16 rounds, we don't give out Int-Far for least MVPs.
            return None

        tied_intfars = get_outlier(
            self.parsed_game_stats.all_player_stats, "mvps", include_ties=True
        )

        if tied_intfars is None: # No data for stat
            return None

        least_mvps = tied_intfars[0].mvps

        mvp_criteria = criterias["lower_threshold"]
        kda_criteria = criterias["kda_criteria"]

        potential_intfars = []
        for stats in tied_intfars:
            if least_mvps < mvp_criteria and stats.kda < kda_criteria:
                potential_intfars.append(stats)

        if potential_intfars == []:
            return None

        # Check if all Int-Far candidates are randos (not registered with Int-Far)
        all_intfars_randos = not any(stats.disc_id for stats in potential_intfars)
        if all_intfars_randos:
            logger.info("Int-Far for least MVPs goes to a random!")

        return potential_intfars

    def _intfar_by_adr(self) -> list[CS2PlayerStats]:
        """
        Returns the info of the Int-Far, if this person has low ADR.
        This is determined by:
            - Having the lowest ADR in the group
            - ADR being less than 30
            - Number of deaths being more than 3
        Returns None if none of these criteria matches a person.
        """
        tied_intfars = get_outlier(
            self.parsed_game_stats.all_player_stats, "adr", include_ties=True
        )

        if tied_intfars is None: # No data for stat
            return None

        lowest_adr = tied_intfars[0].adr
        criterias = self.INTFAR_CRITERIAS()["adr"]

        adr_criteria = criterias["lower_threshold"]
        deaths_criteria = criterias["deaths_criteria"]

        potential_intfars = []
        for stats in tied_intfars:
            if lowest_adr < adr_criteria and stats.deaths > deaths_criteria:
                potential_intfars.append(stats)

        # Check if all Int-Far candidates are randos (not registered with Int-Far)
        all_intfars_randos = not any(stats.disc_id for stats in potential_intfars)

        if potential_intfars == [] or all_intfars_randos:
            return None

        if all_intfars_randos:
            logger.info("Int-Far for lowest ADR goes to a random!")

        return potential_intfars

    def _intfar_by_score(self) -> list[CS2PlayerStats]:
        """
        Returns the info of the Int-Far, if this person has low score.
        This is determined by:
            - Having the lowest score in the group
            - Score being less than 20
            - KDA being less than 1.25
            - Rounds played in the game being more than 12
        Returns None if none of these criteria matches a person.
        """
        criterias = self.INTFAR_CRITERIAS()["score"]
        rounds_criteria = criterias["rounds_criteria"]

        if self.parsed_game_stats.rounds_us + self.parsed_game_stats.rounds_them <= rounds_criteria:
            # If game lasted less than 16 rounds, we don't give out Int-Far for lowest score.
            return None

        tied_intfars = get_outlier(
            self.parsed_game_stats.all_player_stats, "score", include_ties=True
        )

        if tied_intfars is None: # No data for stat
            return None

        lowest_score = tied_intfars[0].score

        score_criteria = criterias["lower_threshold"]
        kda_criteria = criterias["kda_criteria"]

        potential_intfars = []
        for stats in tied_intfars:
            if lowest_score < score_criteria and stats.kda < kda_criteria:
                potential_intfars.append(stats)

        # Check if all Int-Far candidates are randos (not registered with Int-Far)
        all_intfars_randos = not any(stats.disc_id for stats in potential_intfars)

        if potential_intfars == [] or all_intfars_randos:
            return None

        if all_intfars_randos:
            logger.info("Int-Far for lowest score goes to a random!")

        return potential_intfars

    def resolve_intfar_ties(self, intfar_data, max_count):
        """
        Resolve a potential tie in who should be Int-Far. This can happen if two or more
        people meet the same criteria, with the same stats within these criteria.
        If so, the one with either most deaths, lowest kda, or lowest score gets chosen as Int-Far.
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

        sorted_by_score = sorted(ties, key=lambda x: x.score)
        return sorted_by_score[0].disc_id, sorted_by_score[0].player_id, True, "Ties resolved by lowest score."

    def get_intfar_qualifiers(self):
        intfar_kda = self._intfar_by_kda()
        if intfar_kda is not None:
            logger.info("Int-Far because of KDA.")

        intfar_mvps= self._intfar_by_mvps()
        if intfar_mvps is not None:
            logger.info("Int-Far because of MVPs.")

        intfar_adr = self._intfar_by_adr()
        if intfar_adr is not None:
            logger.info("Int-Far because of ADR.")

        intfar_score = self._intfar_by_score()
        if intfar_score is not None:
            logger.info("Int-Far because of score.")

        return [
            ("kda", intfar_kda), ("mvps", intfar_mvps),
            ("adr", intfar_adr), ("score", intfar_score)
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
