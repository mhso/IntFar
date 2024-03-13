import json
import argparse
from glob import glob
from datetime import datetime

from dateutil.relativedelta import relativedelta
from api.lan import LAN_PARTIES

from app.routes.soundboard import normalize_sound_volume
from api import award_qualifiers, config, util
from api.meta_database import MetaDatabase
from api.game_database import GameDatabase
from api.game_databases import get_database_client
from api.awards import get_awards_handler
from api.game_data import get_stat_parser, get_formatted_stat_names, get_stat_quantity_descriptions
from api.game_apis.lol import RiotAPIClient
from api.game_apis.cs2 import SteamAPIClient
from discbot.commands.util import ADMIN_DISC_ID
from discbot.discord_bot import DiscordClient

class TestFuncs:
    def __init__(self, config, meta_database: MetaDatabase, game_databases: dict[str, GameDatabase], riot_api):
        self.config = config
        self.meta_database = meta_database
        self.game_databases = game_databases
        self.riot_api = riot_api

    def test_performance_score(self):
        for stuff in self.game_databases["lol"].get_performance_score()():
            print(stuff)

    def test_cool_stats(self):
        game_ids = self.game_databases["lol"].get_game_ids()

        max_count = 20
        threshold = 7
        key = "turretKills"

        histogram = [0 for _ in range(max_count)]

        for game_id in game_ids:
            try:
                with open(f"../resources/data/game_{game_id[0]}.json", "r", encoding="utf-8") as fp:
                    game_info = json.load(fp)
            except FileNotFoundError:
                continue

            relevant_stats, _ = get_relevant_stats(self.database.summoners, [], game_info)
            filtered_stats = get_filtered_stats(relevant_stats)
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
        played_champs = set(x[0] for x in self.game_databases["lol"].get_played_champs(ADMIN_DISC_ID))

        unplayed_champs = [self.riot_api.get_champ_name(champ) for champ in (all_champs - played_champs)]
        for champ in unplayed_champs:
            print(champ)

    def test_intfar_stuff(self):
        game_id = 6803032678
        guild_id = 619073595561213953
        game_data = self.riot_api.get_game_details(game_id)
        parser = get_stat_parser("lol", game_data, self.riot_api, self.game_databases["lol"].game_users, guild_id)
        parsed_stats = parser.parse_data()

        intfar_data = get_awards_handler("lol", self.config, parsed_stats).get_intfar()
        print(intfar_data)

    def test_lan_rework(self):
        lan_info = LAN_PARTIES["december_23"]
        game = "lol"
        stat_quantity_desc = get_stat_quantity_descriptions(game)
        stats_to_get = list(stat_quantity_desc)

        all_stats = self.game_databases["lol"].get_player_stats(
            stats_to_get,
            time_after=lan_info.start_time,
            time_before=lan_info.end_time,
            guild_id=lan_info.guild_id
        )

        stats_to_get.remove("disc_id")

        print(stats_to_get)
        print(all_stats)

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
        game_id = 6788182214
        game = "lol"
        game_data = self.riot_api.get_game_details(game_id)
        parser = get_stat_parser(game, game_data, self.riot_api, self.game_databases["lol"].game_users, 803987403932172359)
        parsed_game_stats = parser.parse_data()
        awards_handler = get_awards_handler(game, self.config, parsed_game_stats)

        timeline_stats = awards_handler.get_cool_timeline_events()
        print(timeline_stats)
        print(awards_handler.get_flavor_text("timeline", 4, "random"))

    def test_normalize_sound(self):
        files = glob("app/static/sounds/*.mp3")
        for filename in files:
            normalize_sound_volume(filename)

    def test_ifotm(self):
        client = DiscordClient(CONFIG, DATABASE, None, {"lol": RIOT_API, "cs2": None})

        client.add_event_listener("ready", client.assign_monthly_intfar_role, "lol", 1, [267401734513491969])
        client.run(CONFIG.discord_token)

    def test_lifetime_stats(self):
        id_dave = 115142485579137029
        id_murt = 172757468814770176
        id_thomas = 219497453374668815
        id_me = 267401734513491969
        id_mads = 331082926475182081
        data = [
            (id_dave, None),
            (id_murt, None),
            (id_thomas, None),
            (id_me, None),
            (id_mads, None),
        ]
        lifetime_stats = award_qualifiers.get_lifetime_stats(data, self.database)
        print(lifetime_stats)

    def test_games_count(self):
        database = self.game_databases["lol"]
        games_count_me = database.get_games_count(115142485579137029)
        games_count_all = database.get_games_count()
        print(games_count_me)
        print(games_count_all)

    async def play_sound(self, sound, client):
        user = client.get_member_safe(267401734513491969, 512363920044982272)
        await client.audio_handler.play_sound(user.voice, sound)

    def test_pyppeteer_stream(self):
        url = "https://www.youtube.com/watch?v=esdTLuEtwNM"
        client = DiscordClient(CONFIG, META_DATABASE, None, RIOT_API)
        client.add_event_listener("ready", self.play_sound, url, client)
        client.run(CONFIG.discord_token)

    def test_monthly_intfar(self):
        stats = self.game_databases["lol"].get_intfar_stats(267401734513491969, True)
        print(stats)

    def test_steam_api(self):
        self.config.steam_2fa_code = input("Steam 2FA Code: ")

        api_client = SteamAPIClient(self.config)
        match_token = "CSGO-6Pntd-wC8iV-ELKBc-bUcdG-pJGrL"

        game_data = api_client.get_game_details(match_token)
        with open("csgo_testdata.json", "w", encoding="utf-8") as fp:
            json.dump(game_data, fp)

        api_client.close()

    def test_steam_stuff(self):
        api_client = SteamAPIClient("csgo", self.config)
        #steam_ids = [76561198014212213, 76561197970416015]
        print(api_client.is_person_ingame(76561197970416015))

    def test_cs_maps(self):
        api_client = SteamAPIClient("csgo", self.config)
        print(api_client.map_names)

    def test_cs_sharecode(self):
        api_client = SteamAPIClient("cs2", self.config)
        user = self.game_databases["cs2"].game_users[267401734513491969]
        print(user.latest_match_token[0])
        next_code = api_client.get_next_sharecode(user.ingame_id[0], user.match_auth_code[0], user.latest_match_token[0])
        print(next_code)

    def test_cs_parse(self):
        self.config.steam_2fa_code = input("Steam 2FA Code: ")
        sharecode = "CSGO-rCDRM-HfoZB-UrbG2-xkiNo-us68F"
        api_client = SteamAPIClient("cs2", self.config)

        game_stats = api_client.get_game_details(sharecode)
        with open(f"data_{sharecode}.json", "w", encoding="utf-8") as fp:
            json.dump(game_stats, fp)

        parser = get_stat_parser("cs2", game_stats, api_client, self.game_databases["cs2"].game_users, 619073595561213953)
        data = parser.parse_data()

    def test_format_stats(self):
        stat_names = get_formatted_stat_names("lol")
        for stat in stat_names:
            print(stat, stat_names[stat])

    def test_quadra_steal(self):
        game_id = "6700149519"
        game = "lol"

        game_stats = self.riot_api.get_game_details(game_id)
        parser = get_stat_parser(game, game_stats, self.riot_api, self.game_databases[game].game_users, 512363920044982272)
        parsed_game_stats = parser.parse_data()
        awards_handler = get_awards_handler(game, self.config, parsed_game_stats)

        timeline_events = awards_handler.get_cool_timeline_events()
        print(timeline_events)

    def test_average_stats(self):
        stats = self.game_databases["lol"].get_average_stat("kda", 267401734513491969, min_games=1)()
        for row in stats:
            print(row)

        print(len(stats), "rows")

    def test_convert_coords(self):
        x = -616
        y = 638

        scaling = 16000 / 2000

        x = (x + 1000) * scaling
        y = (y + 1000) * scaling

        print(x, y)

    def test_items(self):
        with open("../resources/items-14.3.1.json", encoding="utf-8") as fp:
            items = json.load(fp)

        with open("items.txt", "w", encoding="utf-8") as fp:
            for index, item_id in enumerate(items["data"]):
                name = items["data"][item_id]["name"]
                print(name)
                if index > 0:
                    name = "," + name
                fp.write(name)

    def test_weekly_stuff(self):
        timestamp = datetime.now()
        date_start_1, date_end_1 = self.meta_database.get_weekly_timestamp(timestamp, 2)
        week_old = {
            sound: (plays, rank)
            for sound, plays, rank
            in self.meta_database.get_weekly_sound_hits(date_start_1, date_end_1)
        }

        date_start_2, date_end_2 = self.meta_database.get_weekly_timestamp(timestamp, 1)
        week_new = [
            (sound, plays, rank)
            for sound, plays, rank
            in self.meta_database.get_weekly_sound_hits(date_start_2, date_end_2)
        ]

        print(date_start_1, date_end_1)
        print(date_start_2, date_end_2)

        print(week_old)
        print(week_new)

if __name__ == "__main__":
    PARSER = argparse.ArgumentParser()

    CONFIG = config.Config()
    META_DATABASE = MetaDatabase(CONFIG)
    GAME_DATABASES = {game: get_database_client(game, CONFIG) for game in util.SUPPORTED_GAMES}
    RIOT_API = RiotAPIClient("lol", CONFIG)

    TEST_RUNNER = TestFuncs(CONFIG, META_DATABASE, GAME_DATABASES, RIOT_API)
    FUNCS = [
        func.replace("test_", "")
        for func in TEST_RUNNER.__dir__() if func.startswith("test_")
    ]

    PARSER.add_argument("func", choices=FUNCS)

    ARGS = PARSER.parse_args()

    FUNC_TO_RUN = TEST_RUNNER.__getattribute__(f"test_{ARGS.func}")

    FUNC_TO_RUN()
