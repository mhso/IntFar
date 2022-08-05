from mhooge_flask.logging import logger

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
        - Having a vision score of 100+
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

        if damage_dealt > stats["damage_by_team"] - damage_dealt:
            mention_list.append((2, damage_dealt))

        if stats["pentaKills"] > 0:
            mention_list.append((3, stats["pentaKills"]))

        if stats["visionScore"] > 100:
            mention_list.append((4, stats["visionScore"]))

        kp = game_stats.calc_kill_participation(stats, stats["kills_by_team"])

        if kp > 80:
            mention_list.append((5, kp))

        own_epics = stats["baronKills"] + stats["dragonKills"] + stats["heraldKills"]
        enemy_epics = stats["enemyBaronKills"] + stats["enemyDragonKills"] + stats["enemyHeraldKills"]

        if stats["lane"] == "JUNGLE" and stats["role"] == "NONE" and own_epics > 3 and enemy_epics == 0:
            mention_list.append((6, own_epics))

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

def get_honorable_mentions(data, config):
    """
    Returns players that deserve honorable mentions (questionable stats),
    for stuff that wasn't quite bad enough to be named Int-Far for.
    Honorable mentions are given for:
        - Having 0 control wards purchased.
        - Being adc/mid/top/jungle and doing less than 8000 damage.
        - Being adc/mid/top and having less than 5 cs/min.
        - Being jungle and securing no epic monsters.
    """
    mentions = {} # List of mentioned users for the different criteria.
    for disc_id, stats in data:
        mentions[disc_id] = []

        if stats["mapId"] != 21 and stats["visionWardsBoughtInGame"] == config.mentions_vision_wards:
            mentions[disc_id].append((0, stats["visionWardsBoughtInGame"]))

        damage_dealt = stats["totalDamageDealtToChampions"]
        if stats["lane"] != "UTILITY" and damage_dealt < config.mentions_max_damage:
            mentions[disc_id].append((1, damage_dealt))

        cs_per_min = stats["csPerMin"]
        if stats["lane"] != "UTILITY" and stats["lane"] != "JUNGLE" and cs_per_min < config.mentions_max_cs_per_min:
            mentions[disc_id].append((2, api_util.round_digits(cs_per_min)))

        epic_monsters_secured = stats["baronKills"] + stats["dragonKills"] + stats["heraldKills"]
        if stats["lane"] == "JUNGLE" and stats["role"] == "NONE" and epic_monsters_secured == config.mentions_epic_monsters:
            mentions[disc_id].append((3, epic_monsters_secured))

    return mentions

def get_cool_stats(data, config):
    cool_stats = {}

    for disc_id, stats in data:
        cool_stats[disc_id] = []

        time_dead = stats["totalTimeSpentDead"]
        if time_dead >= config.stats_min_time_dead:
            time_dead_mins = time_dead // 60
            time_dead_secs = time_dead % 60
            fmt_str = f"{time_dead_mins} mins"
            if time_dead_secs > 0:
                fmt_str += f" and {time_dead_secs} secs"

            cool_stats[disc_id].append((0, fmt_str))

        objectives_stolen = stats["objectivesStolen"]
        if objectives_stolen >= config.stats_min_objectives_stolen:
            cool_stats[disc_id].append((1, objectives_stolen))

        turrets_killed = stats["turretKills"]
        if turrets_killed >= config.stats_min_turrets_killed:
            cool_stats[disc_id].append((2, turrets_killed))

    return cool_stats

def get_cool_timeline_events(data, config):
    """
    Returns a list of cool/embarrasing events that happened during the course of the game.
    These events include:
        - We lost the game after being up by more than 8k gold (the big throw)
        - We won the game after being down by more than 8k gold (the epic comeback)
        - Someone had more than 4000 gold at one point
    """
    # Dictionary that maps from participantId to disc_id
    participant_dict = {
        entry["participantId"]: data["puuid_map"].get(entry["puuid"])
        for entry in data["participants"]
    }

    timeline_events = []

    biggest_gold_lead = 0
    biggest_gold_deficit = 0
    too_much_gold = {}

    # Calculate stats from timeline frames.
    for frame_data in data["frames"]:
        # Tally up our and ememy teams total gold during the game.
        our_total_gold = 0
        enemy_total_gold = 0

        for participant_id in frame_data["participantFrames"]:
            participant_data = frame_data["participantFrames"][participant_id]
            disc_id = participant_dict.get(participant_id)
            total_gold = participant_data["totalGold"]
            curr_gold = participant_data["currentGold"]
            our_team = (int(participant_id) > 5) ^ data["ourTeamLower"]

            # Add players gold to total for their team.
            if our_team:
                our_total_gold += total_gold
            else:
                enemy_total_gold += total_gold

            if disc_id is not None and curr_gold > config.timeline_min_curr_gold:
                # Player has enough current gold to warrant a mention.
                # If this amount of gold is more than their previous max, save it.
                curr_value_for_player = too_much_gold.get(disc_id, 0)
                curr_value_for_player[disc_id] = max(curr_gold, curr_value_for_player)

        gold_diff = our_total_gold - enemy_total_gold
        if gold_diff < 0: # Record max gold deficit during the game.
            biggest_gold_deficit = max(abs(gold_diff), biggest_gold_deficit) 
        else: # Record max gold lead during the game.
            biggest_gold_lead = max(gold_diff, biggest_gold_lead)

    if biggest_gold_deficit > config.timeline_min_deficit and data["gameWon"]: # Epic comeback!
        timeline_events.append((0, biggest_gold_deficit, None))
    elif biggest_gold_lead > config.timeline_min_lead and not data["gameWon"]: # Huge throw...
        timeline_events.append((1, biggest_gold_lead, None))

    for disc_id in too_much_gold:
        timeline_events.append((2, too_much_gold[disc_id], disc_id))

    return timeline_events

def intfar_by_kda(data, config):
    """
    Returns the info of the Int-Far, if this person has a truly terrible KDA.
    This is determined by:
        - KDA being the lowest of the group
        - KDA being less than 1.3
        - Number of deaths being more than 2.
    Returns None if none of these criteria matches a registered person.
    """
    tied_intfars, tied_stats = game_stats.get_outlier(data, "kda", include_ties=True)
    lowest_kda = game_stats.calc_kda(tied_stats[0])
    kda_criteria = config.kda_lower_threshold
    death_criteria = config.kda_death_criteria

    potential_intfars = []
    for intfar, stats in zip(tied_intfars, tied_stats):
        deaths = stats["deaths"]

        if lowest_kda < kda_criteria and deaths > death_criteria:
            potential_intfars.append(intfar)

    # Check if all Int-Far candidates are randos (not registered with Int-Far)
    all_intfars_randos = not any(potential_intfars)

    if all_intfars_randos:
        logger.info("Int-Far for low KDA goes to a random!")

    if potential_intfars == [] or all_intfars_randos:
        return (None, None)

    return (potential_intfars, lowest_kda)

def intfar_by_deaths(data, config):
    """
    Returns the info of the Int-Far, if this person has hecking many deaths.
    This is determined by:
        - Having the max number of deaths in the group
        - Number of deaths being more than 9.
        - KDA being less than 2.1
    Returns None if none of these criteria matches a person.
    """
    tied_intfars, tied_stats = game_stats.get_outlier(
        data, "deaths", asc=False, include_ties=True
    )
    highest_deaths = tied_stats[0]["deaths"]
    death_criteria = config.death_lower_threshold
    kda_criteria = config.death_kda_criteria

    potential_intfars = []
    for intfar, stats in zip(tied_intfars, tied_stats):
        kda = game_stats.calc_kda(stats)

        if highest_deaths > death_criteria and kda < kda_criteria:
            potential_intfars.append(intfar)

    # Check if all Int-Far candidates are randos (not registered with Int-Far)
    all_intfars_randos = not any(potential_intfars)

    if all_intfars_randos:
        logger.info("Int-Far for many deaths goes to a random!")

    if potential_intfars == [] or all_intfars_randos:
        return (None, None)

    return (potential_intfars, highest_deaths)

def intfar_by_kp(data, config):
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
    team_kills = data[0][1]["kills_by_team"]
    tied_intfars, tied_stats = game_stats.get_outlier(data, "kp", total_kills=team_kills, include_ties=True)
    lowest_kp = game_stats.calc_kill_participation(tied_stats[0], team_kills)
    kp_criteria = config.kp_lower_threshold
    takedowns_criteria = config.kp_takedowns_criteria
    structures_criteria = config.kp_structures_criteria
    deaths_criteria = config.kp_deaths_criteria

    potential_intfars = []
    for intfar, stats in zip(tied_intfars, tied_stats):
        structures_destroyed = stats["turretKills"] + stats["inhibitorKills"]
        kills = stats["kills"]
        deaths = stats["deaths"]
        assists = stats["assists"]

        if (lowest_kp < kp_criteria and kills + assists < takedowns_criteria
                and deaths > deaths_criteria and structures_destroyed < structures_criteria):
            potential_intfars.append(intfar)

    if potential_intfars == []:
        return (None, None)

    return (potential_intfars, lowest_kp)

def intfar_by_vision_score(data, config):
    """
    Returns the info of the Int-Far, if this person has very low kill vision score.
    This is determined by:
        - Game being longer than 20 mins
        - Having the lowest vision score in the group
        - Vision score being less than 9
        - KDA being less than 3
    Returns None if none of these criteria matches a person.
    """
    time_criteria = config.vision_secs_lower_threshold

    if data[0][1]["gameDuration"] < time_criteria:
        # If game is less than 20 minutes, we don't give out Int-Far for vision score.
        return (None, None)

    tied_intfars, tied_stats = game_stats.get_outlier(data, "visionScore", include_ties=True)
    lowest_score = tied_stats[0]["visionScore"]
    vision_criteria = config.vision_score_lower_threshold
    kda_criteria = config.vision_kda_criteria

    potential_intfars = []
    for intfar, stats in zip(tied_intfars, tied_stats):
        kda = game_stats.calc_kda(stats)

        if lowest_score < vision_criteria and kda < kda_criteria:
            potential_intfars.append(intfar)

    if potential_intfars == []:
        return (None, None)

    return (potential_intfars, lowest_score)

def resolve_intfar_ties(intfar_data, max_count, game_data):
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
    for disc_id, stats in game_data:
        if disc_id in ties:
            filtered_data.append((disc_id, stats))

    sorted_by_deaths = sorted(filtered_data, key=lambda x: x[1]["deaths"], reverse=True)
    max_count = sorted_by_deaths[0][1]["deaths"]
    ties = []
    for disc_id, stats in sorted_by_deaths:
        if stats["deaths"] == max_count:
            ties.append(disc_id)
        else:
            break

    if len(ties) == 1:
        return ties[0], True, "Ties resolved by most amount of deaths."

    sorted_by_kda = sorted(filtered_data, key=lambda x: game_stats.calc_kda(x[1]))
    max_count = game_stats.calc_kda(sorted_by_deaths[0][1])
    ties = []
    for disc_id, stats in sorted_by_kda:
        if game_stats.calc_kda(stats) == max_count:
            ties.append(disc_id)
        else:
            break

    if len(ties) == 1:
        return ties[0], True, "Ties resolved by lowest KDA."

    sorted_by_gold = sorted(filtered_data, key=lambda x: x[1]["goldEarned"])
    return sorted_by_gold[0][0], True, "Ties resolved by fewest gold earned."

def get_intfar_qualifiers(relevant_stats, filtered_stats, config):
    intfar_kda_id, kda = intfar_by_kda(relevant_stats, config)
    if intfar_kda_id is not None:
        logger.info("Int-Far because of KDA.")

    intfar_deaths_id, deaths = intfar_by_deaths(relevant_stats, config)
    if intfar_deaths_id is not None:
        logger.info("Int-Far because of deaths.")

    intfar_kp_id, kp = intfar_by_kp(filtered_stats, config)
    if intfar_kp_id is not None:
        logger.info("Int-Far because of kill participation.")

    intfar_vision_id, vision_score = None, None
    if filtered_stats[0][1]["mapId"] != 21:
        intfar_vision_id, vision_score = intfar_by_vision_score(filtered_stats, config)
        if intfar_vision_id is not None:
            logger.info("Int-Far because of vision score.")

    return [
        (intfar_kda_id, kda), (intfar_deaths_id, deaths),
        (intfar_kp_id, kp), (intfar_vision_id, vision_score)
    ]

def get_intfar_candidates(intfar_details):
    max_intfar_count = 1
    intfar_counts = {}
    max_count_intfar = None
    qualifier_data = {}

    # Look through details for the people qualifying for Int-Far.
    # The one with most criteria met gets chosen.
    for (index, (tied_intfars, stat_value)) in enumerate(intfar_details):
        if tied_intfars is not None:
            for intfar_disc_id in tied_intfars:
                current_intfar_count = intfar_counts.get(intfar_disc_id, 0) + 1
                intfar_counts[intfar_disc_id] = current_intfar_count

                if current_intfar_count >= max_intfar_count:
                    max_intfar_count = current_intfar_count
                    max_count_intfar = intfar_disc_id

                data_list = qualifier_data.get(intfar_disc_id, [])
                data_list.append((index, stat_value))
                qualifier_data[intfar_disc_id] = data_list

    return qualifier_data, max_count_intfar, max_intfar_count

def get_intfar(relevant_stats, filtered_stats, config):
    intfar_details = get_intfar_qualifiers(relevant_stats, filtered_stats, config)

    (intfar_data,
     max_count_intfar,
     max_intfar_count) = get_intfar_candidates(intfar_details)

    if max_count_intfar is None:
        return None, None, None, None

    (final_intfar,
     ties, tie_desc) = resolve_intfar_ties(intfar_data, max_intfar_count, filtered_stats)

    return final_intfar, intfar_data[final_intfar], ties, tie_desc
