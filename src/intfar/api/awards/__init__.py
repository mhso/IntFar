from intfar.api.util import find_subclasses_in_dir
from intfar.api.award_qualifiers import AwardQualifiers

_GAME_AWARD_HANDLERS: dict[str, AwardQualifiers] = find_subclasses_in_dir("intfar/api/awards", AwardQualifiers)

def get_awards_handler(game, config, api_client, parsed_game_stats) -> AwardQualifiers:
    return _GAME_AWARD_HANDLERS[game](config, api_client, parsed_game_stats)

def get_intfar_reasons(game):
    return _GAME_AWARD_HANDLERS[game].INTFAR_REASONS()

def get_intfar_criterias_desc(game):
    return _GAME_AWARD_HANDLERS[game].INTFAR_CRITERIAS_DESC()

def get_doinks_reasons(game):
    return _GAME_AWARD_HANDLERS[game].DOINKS_REASONS()

def organize_intfar_stats(game, games_played, intfar_reason_ids):
    intfar_reasons = get_intfar_reasons(game)
    intfar_counts = {x: 0 for x in range(len(intfar_reasons))}

    for reason_id in intfar_reason_ids:
        intfar_ids = [int(x) for x in reason_id[0]]
        for index, intfar_id in enumerate(intfar_ids):
            if intfar_id == 1:
                intfar_counts[index] += 1

    pct_intfar = (
        0 if games_played == 0
        else (len(intfar_reason_ids) / games_played) * 100
    )

    return games_played, len(intfar_reason_ids), intfar_counts, pct_intfar

def organize_doinks_stats(game, doinks_reason_ids):
    doinks_reasons = get_doinks_reasons(game)
    doinks_counts = {x: 0 for x in range(len(doinks_reasons))}

    for reason_id in doinks_reason_ids:
        intfar_ids = [int(x) for x in reason_id[0]]
        for index, intfar_id in enumerate(intfar_ids):
            if intfar_id == 1:
                doinks_counts[index] += 1

    return doinks_counts
