import json
import argparse
import os
from glob import glob
from datetime import datetime
from dateutil.relativedelta import relativedelta

from app.routes.soundboard import normalize_sound_volume
from api import award_qualifiers, config, database, riot_api, util
from api.game_stats import get_filtered_stats, get_filtered_timeline_stats
from discbot.commands.util import ADMIN_DISC_ID

class TestFuncs:
    def __init__(self, config, database, riot_api):
        self.config = config
        self.database = database
        self.riot_api = riot_api

    def test_performance_score(self):
        id_dave = 115142485579137029
        id_murt = 172757468814770176
        id_thomas = 219497453374668815
        id_tobber = 235831136733888512
        id_myggen = 248126657028685824
        id_me = 267401734513491969
        id_anton = 347489125877809155

        print(award_qualifiers.get_performance_score(self.database, id_myggen))
        print(award_qualifiers.get_performance_score(self.database, id_murt))
        print(award_qualifiers.get_performance_score(self.database, id_me))
        print(award_qualifiers.get_performance_score(self.database, id_anton))
        print(award_qualifiers.get_performance_score(self.database, id_thomas))
        print(award_qualifiers.get_performance_score(self.database, id_dave))
        print(award_qualifiers.get_performance_score(self.database, id_tobber))

    def test_cool_stats(self):
        game_ids = self.database.get_game_ids()

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

            filtered_stats, _ = get_filtered_stats(self.database.summoners, [], game_info)
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

    def test_unplayed_champs(self):
        all_champs = set(self.riot_api.champ_names.keys())
        played_champs = set(x[0] for x in self.database.get_played_champs(ADMIN_DISC_ID))

        unplayed_champs = [self.riot_api.get_champ_name(champ) for champ in (all_champs - played_champs)]
        for champ in unplayed_champs:
            print(champ)

    def test_tie_stuff(self):
        game_id = 5560333770
        game_data = self.riot_api.get_game_details(game_id)
        filtered = get_filtered_stats(self.database.summoners, [], game_data)[0]
        intfar_data = award_qualifiers.get_intfar(filtered, CONFIG)
        print(intfar_data)

    def test_ifotm_stuff(self):
        intfar_data = self.database.get_intfars_of_the_month()

        print(intfar_data)

    def test_duration(self):
        dt_2 = datetime.now()
        dt_1 = datetime(dt_2.year, dt_2.month - 1, dt_2.day- 3, dt_2.hour, dt_2.minute)
        delta = relativedelta(dt_2, dt_1)

        years = delta.years
        months = delta.months
        days = delta.days
        hours = delta.hours
        minutes = delta.minutes
        seconds = delta.seconds

        response = f"{util.zero_pad(hours)}h, {util.zero_pad(minutes)}m, {util.zero_pad(seconds)}s"
        if minutes == 0:
            response = f"{seconds} seconds"
        else:
            response = f"{util.zero_pad(minutes)} minutes & {util.zero_pad(seconds)} seconds"
        if hours > 0:
            response = f"{util.zero_pad(hours)}h, {util.zero_pad(minutes)}m, {util.zero_pad(seconds)}s"
        if days > 0:
            response = f"{days} days, " + response
        if months > 0:
            response = f"{months} months, " + response
        if years > 0:
            response = f"{years} years, " + response

        print(response)

    def test_timeline(self):
        game_id = 5826515143
        game_data = self.riot_api.get_game_details(game_id)
        timeline_data = self.riot_api.get_game_timeline(game_id)
        filtered = get_filtered_stats(self.database.summoners, [], game_data)[0]
        filtered_timeline = get_filtered_timeline_stats(filtered, timeline_data)

        stats = award_qualifiers.get_cool_timeline_events(filtered_timeline, CONFIG)
        print(stats)

    def test_normalize_sound(self):
        files = glob("app/static/sounds/*.mp3")
        for filename in files:
            normalize_sound_volume(filename)

PARSER = argparse.ArgumentParser()

CONFIG = config.Config()
DATABASE = database.Database(CONFIG)
RIOT_API = riot_api.APIClient(CONFIG)

TEST_RUNNER = TestFuncs(CONFIG, DATABASE, RIOT_API)
FUNCS = [
    func.replace("test_", "")
    for func in TEST_RUNNER.__dir__() if func.startswith("test_")
]

PARSER.add_argument("func", choices=FUNCS)

ARGS = PARSER.parse_args()

FUNC_TO_RUN = TEST_RUNNER.__getattribute__(f"test_{ARGS.func}")

FUNC_TO_RUN()
