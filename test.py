import json

from api import award_qualifiers, config, database
from api.game_stats import get_filtered_stats

CONFIG = config.Config()
DATABASE = database.Database(CONFIG)

def test_performance_score():
    id_dave = 115142485579137029
    id_murt = 172757468814770176
    id_thomas = 219497453374668815
    id_tobber = 235831136733888512
    id_myggen = 248126657028685824
    id_me = 267401734513491969
    id_anton = 347489125877809155

    print(award_qualifiers.get_performance_score(DATABASE, id_myggen))
    print(award_qualifiers.get_performance_score(DATABASE, id_murt))
    print(award_qualifiers.get_performance_score(DATABASE, id_me))
    print(award_qualifiers.get_performance_score(DATABASE, id_anton))
    print(award_qualifiers.get_performance_score(DATABASE, id_thomas))
    print(award_qualifiers.get_performance_score(DATABASE, id_dave))
    print(award_qualifiers.get_performance_score(DATABASE, id_tobber))

def test_cool_stats():
    game_ids = DATABASE.get_game_ids()

    max_count = 20
    threshold = 7
    key = "turretKills"

    histogram = [0 for _ in range(max_count)]

    for game_id in game_ids:
        try:
            with open(f"resources/data/game_{game_id[0]}.json", "r", encoding="utf-8") as fp:
                game_info = json.load(fp)
        except FileNotFoundError:
            continue

        filtered_stats, _ = get_filtered_stats(DATABASE.summoners, [], game_info)
        if key not in filtered_stats[0][1]:
            continue

        for _, stats in filtered_stats:
            value = stats[key]
            if value >= 7:
                print(game_id)
            histogram[value] += 1

    total = sum(histogram)
    more_than_threshold = sum(histogram[threshold:])

    print(histogram)
    print(total)
    print(more_than_threshold)

test_performance_score()
