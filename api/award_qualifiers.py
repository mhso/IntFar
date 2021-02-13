from api import game_stats
import api.util as api_util

def get_big_doinks(data):
    """
    Returns a string describing people who have been redeemed by playing
    exceptionally well.
    Criteria for being redeemed:
        - Having a KDA of 10 or more
        - Getting 20 kills or more
        - Doing more damage than the rest of the team combined
        - Getting a penta-kill
        - Having a vision score of 80+
        - Having a kill-participation of 80%+
        - Securing all epic monsters
        - Getting more than 8 cs/min
    """
    mentions = {} # List of mentioned users for the different criteria.
    formatted_mentions = {}
    for disc_id, stats in data:
        mention_list = []
        kda = game_stats.calc_kda(stats)
        if kda >= 10.0:
            mention_list.append((0, api_util.round_digits(kda)))
        if stats["kills"] >= 20:
            mention_list.append((1, stats["kills"]))
        damage_dealt = stats["totalDamageDealtToChampions"]
        if damage_dealt > stats["damage_by_team"]:
            mention_list.append((2, damage_dealt))
        if stats["pentaKills"] > 0:
            mention_list.append((3, None))
        if stats["visionScore"] > 80:
            mention_list.append((4, stats["visionScore"]))
        kp = game_stats.calc_kill_participation(stats, stats["kills_by_team"])
        if kp > 80:
            mention_list.append((5, kp))
        own_epics = stats["baronKills"] + stats["dragonKills"] + stats["heraldKills"]
        enemy_epics = stats["enemyBaronKills"] + stats["enemyDragonKills"] + stats["enemyHeraldKills"]
        if stats["lane"] == "JUNGLE" and own_epics > 3 and enemy_epics == 0:
            mention_list.append((6, kp))
        cs_per_min = stats["csPerMin"]
        if cs_per_min >= 8:
            mention_list.append((7, api_util.round_digits(cs_per_min)))

        if mention_list != []:
            mentions[disc_id] = mention_list
            format_str = ""
            for index in range(len(api_util.DOINKS_REASONS)):
                has_doinks_for_stats = False
                for stat_index, _ in mention_list:
                    if stat_index == index:
                        has_doinks_for_stats = True
                        break

                format_str += ("1" if has_doinks_for_stats else "0")

            formatted_mentions[disc_id] = format_str

    return mentions, formatted_mentions

def get_honorable_mentions(data):
    """
    Returns a string describing honorable mentions (questionable stats),
    that wasn't quite bad enough to be named Int-Far for.
    Honorable mentions are given for:
        - Having 0 control wards purchased.
        - Being adc/mid/top/jungle and doing less than 8000 damage.
        - Being adc/mid/top and having less than 5 cs/min.
        - Being jungle and securing no epic monsters.
    """
    mentions = {} # List of mentioned users for the different criteria.
    for disc_id, stats in data:
        mentions[disc_id] = []
        if stats["mapId"] != 21 and stats["visionWardsBoughtInGame"] == 0:
            mentions[disc_id].append((0, stats["visionWardsBoughtInGame"]))
        damage_dealt = stats["totalDamageDealtToChampions"]
        if stats["role"] != "DUO_SUPPORT" and damage_dealt < 8000:
            mentions[disc_id].append((1, damage_dealt))
        cs_per_min = stats["csPerMin"]
        if stats["role"] != "DUO_SUPPORT" and stats["lane"] != "JUNGLE" and cs_per_min < 5.0:
            mentions[disc_id].append((2, api_util.round_digits(cs_per_min)))
        epic_monsters_secured = stats["baronKills"] + stats["dragonKills"] + stats["heraldKills"]
        if stats["lane"] == "JUNGLE" and epic_monsters_secured == 0:
            mentions[disc_id].append((3, epic_monsters_secured))

    return mentions

def intfar_by_kda(data, config):
    """
    Returns the info of the Int-Far, if this person has a truly terrible KDA.
    This is determined by:
        - KDA being the lowest of the group
        - KDA being less than 1.3
        - Number of deaths being more than 2.
    Returns None if none of these criteria matches a person.
    """
    tied_intfars, stats = game_stats.get_outlier(data, "kda", include_ties=True)
    lowest_kda = game_stats.calc_kda(stats)
    deaths = stats["deaths"]
    kda_criteria = config.kda_lower_threshold
    death_criteria = config.kda_death_criteria
    if lowest_kda < kda_criteria and deaths > death_criteria:
        return (tied_intfars, lowest_kda)
    return (None, None)

def intfar_by_deaths(data, config):
    """
    Returns the info of the Int-Far, if this person has hecking many deaths.
    This is determined by:
        - Having the max number of deaths in the group
        - Number of deaths being more than 9.
        - KDA being less than 2.1
    Returns None if none of these criteria matches a person.
    """
    tied_intfars, stats = game_stats.get_outlier(data, "deaths", asc=False, include_ties=True)
    highest_deaths = stats["deaths"]
    kda = game_stats.calc_kda(stats)
    death_criteria = config.death_lower_threshold
    kda_criteria = config.death_kda_criteria
    if highest_deaths > death_criteria and kda < kda_criteria:
        return (tied_intfars, highest_deaths)
    return (None, None)

def intfar_by_kp(data, config):
    """
    Returns the info of the Int-Far, if this person has very low kill participation.
    This is determined by:
        - Having the lowest KP in the group
        - KP being less than 25
        - Number of kills + assists being less than 10
        - Turrets + Inhibitors destroyed < 3
    Returns None if none of these criteria matches a person.
    """
    team_kills = data[0][1]["kills_by_team"]
    tied_intfars, stats = game_stats.get_outlier(data, "kp", total_kills=team_kills, include_ties=True)
    lowest_kp = game_stats.calc_kill_participation(stats, team_kills)
    kills = stats["kills"]
    assists = stats["assists"]
    structures_destroyed = stats["turretKills"] + stats["inhibitorKills"]
    kp_criteria = config.kp_lower_threshold
    takedowns_criteria = config.kp_takedowns_criteria
    structures_criteria = config.kp_structures_criteria
    if (lowest_kp < kp_criteria and kills + assists < takedowns_criteria
            and structures_destroyed < structures_criteria):
        return (tied_intfars, lowest_kp)
    return (None, None)

def intfar_by_vision_score(data, config):
    """
    Returns the info of the Int-Far, if this person has very low kill vision score.
    This is determined by:
        - Having the lowest vision score in the group
        - Vision score being less than 9
        - KDA being less than 3
    Returns None if none of these criteria matches a person.
    """
    tied_intfars, stats = game_stats.get_outlier(data, "visionScore", include_ties=True)
    lowest_score = stats["visionScore"]
    kda = game_stats.calc_kda(stats)
    vision_criteria = config.vision_score_lower_threshold
    kda_criteria = config.vision_kda_criteria
    if lowest_score < vision_criteria and kda < kda_criteria:
        return (tied_intfars, lowest_score)
    return (None, None)

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
        return ties[0], False, "There are no ties."

    sorted_by_deaths = sorted(filtered_data, key=lambda x: x[1]["deaths"], reverse=True)
    max_count = sorted_by_deaths[0][1]["deaths"]
    ties = []
    for disc_id, stats in sorted_by_deaths:
        if stats["deaths"] == max_count:
            ties.append(disc_id)

    if len(ties) == 1:
        return ties[0], True, "Ties resolved by most amount of deaths."

    sorted_by_kda = sorted(filtered_data, key=lambda x: game_stats.calc_kda(x[1]))
    max_count = game_stats.calc_kda(sorted_by_deaths[0][1])
    ties = []
    for disc_id, stats in sorted_by_kda:
        if game_stats.calc_kda(stats) == max_count:
            ties.append(disc_id)

    if len(ties) == 1:
        return ties[0], True, "Ties resolved by lowest KDA."

    sorted_by_gold = sorted(filtered_data, key=lambda x: x[1]["goldEarned"])
    return sorted_by_gold[0][0], True, "Ties resolved by fewest gold earned."

def get_intfar_details(stats, config):
    intfar_kda_id, kda = intfar_by_kda(stats, config)
    if intfar_kda_id is not None:
        config.log("Int-Far because of KDA.")

    intfar_deaths_id, deaths = intfar_by_deaths(stats, config)
    if intfar_deaths_id is not None:
        config.log("Int-Far because of deaths.")

    intfar_kp_id, kp = intfar_by_kp(stats, config)
    if intfar_kp_id is not None:
        config.log("Int-Far because of kill participation.")

    intfar_vision_id, vision_score = None, None
    if stats[0][1]["mapId"] != 21:
        intfar_vision_id, vision_score = intfar_by_vision_score(stats, config)
        if intfar_vision_id is not None:
            config.log("Int-Far because of vision score.")

    return [
        (intfar_kda_id, kda), (intfar_deaths_id, deaths),
        (intfar_kp_id, kp), (intfar_vision_id, vision_score)
    ]

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

def get_intfar(filtered_stats, config):
    intfar_details = get_intfar_details(filtered_stats, config)
    (intfar_data,
     max_count_intfar,
     max_intfar_count) = get_intfar_qualifiers(intfar_details)

    if max_count_intfar is None:
        return None, None, None, None

    (final_intfar,
     ties, tie_desc) = resolve_intfar_ties(intfar_data, max_intfar_count, filtered_stats)
    return final_intfar, intfar_data[final_intfar], ties, tie_desc
