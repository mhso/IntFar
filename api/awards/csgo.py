from api.award_qualifiers import AwardQualifiers

class CSGOAwardQualifiers(AwardQualifiers):
    @classmethod
    def INTFAR_REASONS(cls):
        return {
            "kda": "Low KDA",
            "deaths": "Many deaths",
            "adr": "Low ADR",
            "score": "Low score"
        }

    @classmethod
    def INTFAR_CRITERIAS(cls):
        return {
            "kda": {
                "lower_threshold": 0.6,
                "death_criteria": 3
            },
            "deaths": {
                "lower_threshold": 9,
                "kda_criteria": 2.1
            },
            "adr": {
                "lower_threshold": 20,
                "takedowns_criteria": 10,
                "structures_criteria": 2,
                "deaths_criteria": 2
            },
            "score": {
                "lower_threshold": 20,
                "kda_criteria": 2.0,
                "secs_lower_threshold": 1200
            }
        }

    @classmethod
    def INTFAR_CRITERIAS_DESC(cls):
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
            "adr": [
                "Having the lowest ADR of the people playing",
                f"Having an ADR of less than {criterias['adr']['lower_threshold']}%",
                f"Having less than {criterias['kp']['takedowns_criteria']} takedowns",
                f"Having less than {criterias['kp']['structures_criteria']} structures destroyed",
                f"Having more than {criterias['kp']['deaths_criteria']} deaths",
            ],
            "score": [
                "Having the lowest score of the people playing",
                f"Having a score of less than {criterias['score']['lower_threshold']}",
                f"Having less than {criterias['score']['kda_criteria']} KDA",
                f"The game being longer than {criterias['score']['secs_lower_threshold'] // 60} minutes",
            ]
        }

    @classmethod
    def DOINKS_REASONS(cls):
        return {
            "kda": "KDA larger than or equal to 10",
            "kills": "20 kills or more",
            "adr": "120 or more ADR",
            "utility": "200 or more utility damage",
            "mvp": "8 or more MVPs",
        }

    @classmethod
    def ALL_FLAVOR_TEXTS(cls):
        return super().ALL_FLAVOR_TEXTS() + [
            "most_deaths",
            "lowest_kda",
            "lowest_kp",
            "lowest_vision",
            "mentions_no_vision_ward",
            "mentions_low_damage",
            "mentions_low_cs_min",
            "mentions_no_epic_monsters",
            "stats_time_spent_dead",
            "stats_objectives_stolen",
            "stats_turrets_killed",
            "timeline_comeback",
            "timeline_throw",
            "timeline_goldkeeper",
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
    def INTFAR_FLAVOR_TEXTS(cls):
        return [
            "most_deaths",
            "lowest_kda",
            "lowest_kp",
            "lowest_vision",
        ]

    @classmethod
    def HONORABLE_MENTIONS_FLAVOR_TEXTS(cls):
        return [
            "mentions_no_vision_ward",
            "mentions_low_damage",
            "mentions_low_cs_min",
            "mentions_no_epic_monsters",
        ]

    @classmethod
    def COOL_STATS_FLAVOR_TEXTS(cls):
        return [
            "stats_time_spent_dead",
            "stats_objectives_stolen",
            "stats_turrets_killed",
        ]

    @classmethod
    def DOINKS_FLAVOR_TEXTS(cls):
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
        return [
            "timeline_comeback",
            "timeline_throw",
            "timeline_goldkeeper",
        ]

    @classmethod
    def GAME_SPECIFIC_FLAVORS(cls):
        flavors = dict(super().GAME_SPECIFIC_FLAVORS()) 
        flavors["timeline"] = cls.TIMELINE_FLAVOR_TEXTS()
        return flavors

    def get_honorable_mentions(self):
        return {} # TODO: Implement

    def get_cool_stats(self):
        return {} # TODO: Implement

    def get_lifetime_stats(self):
        return {} # TODO: Implement
