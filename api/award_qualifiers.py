def get_intfar_details(stats, map_id):
    intfar_kda_id, kda = self.intfar_by_kda(stats)
    if intfar_kda_id is not None:
        self.config.log("Int-Far because of KDA.")

    intfar_deaths_id, deaths = self.intfar_by_deaths(stats)
    if intfar_deaths_id is not None:
        self.config.log("Int-Far because of deaths.")

    intfar_kp_id, kp = self.intfar_by_kp(stats)
    if intfar_kp_id is not None:
        self.config.log("Int-Far because of kill participation.")

    intfar_vision_id, vision_score = None, None
    if map_id != 21:
        intfar_vision_id, vision_score = self.intfar_by_vision_score(stats)
        if intfar_vision_id is not None:
            self.config.log("Int-Far because of vision score.")

    return [
        (intfar_kda_id, kda), (intfar_deaths_id, deaths),
        (intfar_kp_id, kp), (intfar_vision_id, vision_score)
    ]

def resolve_intfar_ties(intfar_data, max_count, game_data):
    """
    Resolve a potential tie in who should be Int-Far. This can happen if two or more
    people meet the same criteria, with the same stats within these criteria.
    If so, the one with either most deaths or least gold gets chosen as Int-Far.
    """
    filtered_data = []
    for disc_id, stats in game_data:
        if disc_id in intfar_data:
            filtered_data.append((disc_id, stats))

    ties = []
    for disc_id in intfar_data:
        if len(intfar_data[disc_id]) == max_count:
            ties.append(disc_id)

    if len(ties) == 1:
        self.config.log("There are no ties.")
        return ties[0]

    self.config.log("There are Int-Far ties!")

    sorted_by_deaths = sorted(filtered_data, key=lambda x: x[1]["deaths"], reverse=True)
    max_count = sorted_by_deaths[0][1]["deaths"]
    ties = []
    for disc_id, stats in sorted_by_deaths:
        if stats["deaths"] == max_count:
            ties.append(disc_id)

    if len(ties) == 1:
        self.config.log("Ties resolved by amount of deaths.")
        return ties[0]

    sorted_by_kda = sorted(filtered_data, key=lambda x: game_stats.calc_kda(x[1]))
    max_count = game_stats.calc_kda(sorted_by_deaths[0][1])
    ties = []
    for disc_id, stats in sorted_by_kda:
        if game_stats.calc_kda(stats) == max_count:
            ties.append(disc_id)

    if len(ties) == 1:
        self.config.log("Ties resolved by KDA.")
        return ties[0]

    self.config.log("Ties resolved by gold earned.")

    sorted_by_gold = sorted(filtered_data, key=lambda x: x[1]["goldEarned"])
    return sorted_by_gold[0][0]

def get_intfar_qualifiers(intfar_details):
    max_intfar_count = 1
    intfar_counts = {}
    max_count_intfar = None
    qualifier_data = {}
    # Look through details for the people qualifying for Int-Far.
    # The one with most criteria met gets chosen.
    for (index, (tied_intfars, stat_value)) in enumerate(intfar_details):
        if tied_intfars is not None:
            for intfar_disc_id in tied_intfars:
                if intfar_disc_id not in intfar_counts:
                    intfar_counts[intfar_disc_id] = 0
                    qualifier_data[intfar_disc_id] = []
                current_intfar_count = intfar_counts[intfar_disc_id] + 1
                intfar_counts[intfar_disc_id] = current_intfar_count
                if current_intfar_count >= max_intfar_count:
                    max_intfar_count = current_intfar_count
                    max_count_intfar = intfar_disc_id
                qualifier_data[intfar_disc_id].append((index, stat_value))

    return qualifier_data, max_count_intfar, max_intfar_count

def get_intfar():
    pass