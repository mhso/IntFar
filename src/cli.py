import asyncio
import inspect
import json
import argparse
from glob import glob
from datetime import datetime
import os

from dateutil.relativedelta import relativedelta
from intfar.api.lan import LAN_PARTIES, insert_bingo_challenges

from intfar.app.routes.soundboard import normalize_sound_volume
from intfar.app.util import get_relative_static_folder
from intfar.api import award_qualifiers, config, util
from intfar.api.meta_database import MetaDatabase
from intfar.api.game_database import GameDatabase
from intfar.api.game_databases import get_database_client
from intfar.api.awards import get_awards_handler
from intfar.api.game_data import get_stat_parser, get_stat_quantity_descriptions, stats_from_database
from intfar.api.game_apis.lol import RiotAPIClient
from intfar.api.game_apis.cs2 import SteamAPIClient
from intfar.discbot.commands.util import ADMIN_DISC_ID
from intfar.discbot.discord_bot import DiscordClient
from intfar.api.data_schema import generate_schema

class TestFuncs:
    def __init__(self, config, meta_database: MetaDatabase, game_databases: dict[str, GameDatabase], riot_api: RiotAPIClient):
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
                with open(f"{self.config.resources_folder}/data/game_{game_id[0]}.json", "r", encoding="utf-8") as fp:
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
        files = glob("intfar/app/static/sounds/*.mp3")
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

    def test_monthly_intfar(self):
        stats = self.game_databases["lol"].get_intfar_stats(267401734513491969, True)
        print(stats)

    async def test_steam_stuff(self):
        api_client = SteamAPIClient("cs2", self.config)
        #steam_ids = [76561198014212213, 76561197970416015]
        print(await api_client.get_player_name("76561197970416015"))

    def test_cs_maps(self):
        api_client = SteamAPIClient("csgo", self.config)
        print(api_client.map_names)

    async def cs_sharecode(self):
        api_client = SteamAPIClient("cs2", self.config)
        user = self.game_databases["cs2"].game_users[ADMIN_DISC_ID]
        sharecode = user.latest_match_token[0]
        print("Now:", sharecode)
        while (sharecode := await api_client.get_next_sharecode(user.player_id[0], user.match_auth_code[0], sharecode)) is not None:
            print("Next:", sharecode)

    async def test_cs_parse(self):
        sharecode = "CSGO-7CowZ-OFhzM-6ytLZ-fXJ2J-Kn6nM"
        api_client = SteamAPIClient("cs2", self.config)

        game_stats = await api_client.get_game_details(sharecode)
        with open(f"data_{sharecode}.json", "w", encoding="utf-8") as fp:
            json.dump(game_stats, fp)

        parser = get_stat_parser("cs2", game_stats, api_client, self.game_databases["cs2"].game_users, 619073595561213953)
        parser.parse_data()

    def test_get_stats(self):
        api_client = SteamAPIClient("cs2", self.config)
        print(stats_from_database("cs2", self.game_databases["cs2"], api_client, 619073595561213953, "CSGO-JPzyG-faFGY-jHDaM-5YQjz-2B3xK"))

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
        with open(f"{self.config.resources_folder}/items-14.3.1.json", encoding="utf-8") as fp:
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

    def test_most_played(self):
        disc_id = 172757468814770176
        # 115142485579137029 dave
        # 331082926475182081 mads
        # 172757468814770176 murt
        # 347489125877809155 nø

        for champ_id, count in self.game_databases["lol"].get_most_played_id(disc_id)():
            champ_name = self.riot_api.get_playable_name(champ_id)
            print(champ_name, count)

    def test_max_kda(self):
        sum_kdas = {}
        players_on_champ = {}
        games_on_champ = {}
        for champ_id in self.riot_api.champ_names:
            for _, kda, games in self.game_databases["lol"].get_average_stat("kda", played_id=champ_id, min_games=1)():
                if games is None:
                    continue

                sum_kdas[champ_id] = sum_kdas.get(champ_id, 0) + kda
                players_on_champ[champ_id] = players_on_champ.get(champ_id, 0) + 1
                games_on_champ[champ_id] = games_on_champ.get(champ_id, 0) + games

        max_kda = 0
        max_kda_champ = None
        total_games = 0
        for champ_id in sum_kdas:
            avg = sum_kdas[champ_id] / players_on_champ[champ_id]
            if avg > max_kda:
                max_kda = avg
                max_kda_champ = champ_id
                total_games = games_on_champ[champ_id]
    
        print(f"{self.riot_api.get_playable_name(max_kda_champ)}: {max_kda} ({total_games} games)")

    def awpy(self):
        from awpy import DemoParser
        match_id = "CSGO-syuCM-w45kr-Hce9x-JM7TZ-FFzQN"
        demo_dem_file = f"{self.config.resources_folder}/data/cs2/{match_id}.dem"
        parser = DemoParser(demofile=demo_dem_file, debug=True)
        demo_game_data = parser.parse()
        os.remove(f"{match_id}.json")
        print(demo_game_data)

    def test_generate_schema(self):
        game = "lol"
        in_file = f"{self.config.resources_folder}/data/game_6950463351.json"
        filename = "game_data.json"
        with open(in_file, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            generate_schema(data, filename, game, self.config)

    def test_synthetic_data(self):
        from intfar.api.game_data.lol import LoLGameStats
        argspec = inspect.getfullargspec(LoLGameStats.__init__)

        args = argspec[0]
        annotations = argspec[-1]
        mandatory_args = args[1:-len(argspec[3])]
        for arg in mandatory_args:
            print(f"{arg}: {annotations[arg].__name__}")

    def insert_bingo_challenges(self):
        insert_bingo_challenges(self.game_databases["lol"], "august_25")

    async def active_game(self):
        user = self.game_databases["lol"].game_users[219497453374668815]
        game_data, active_id = await self.riot_api.get_active_game_for_user(user)
        print(game_data, active_id)

    async def get_puuids(self):
        database = self.game_databases["lol"]
        users = database.game_users
        query = "UPDATE users SET puuid=? WHERE player_id=?"
        with database:
            for disc_id in users:
                print(f"Processing {disc_id}...")
                for summ_id in users[disc_id].player_id:
                    summ_data = await self.riot_api.get_player_data_from_summ_id(summ_id)
                    database.execute_query(query, summ_data["puuid"], summ_id)
                    await asyncio.sleep(2)

    def jeopardy_progress(self):
        total = util.JEOPARDY_REGULAR_ROUNDS * 30 + 1
        done = 0
        with open(f"{self.config.static_folder}/data/jeopardy_questions.json", "r") as fp:
            data = json.load(fp)
            for category in data:
                for tier in data[category]["tiers"]:
                    done += len(tier["questions"])

        print(f"Done with {done}/{total} ({int((done / total) * 100)}%)")

    async def get_raw_lol_data(self):
        game_id = "7451201570"
        data = await self.riot_api.get_game_details(game_id)
        with open("../resources/lol_data.json", "w", encoding="utf-8") as fp:
            json.dump(data, fp)

    def relative_static(self):
        path = "/mnt/d/mhooge/intfar/src/intfar/app/static/avatars/123.png"
        print(get_relative_static_folder(path, self.config))

    async def get_lol_matches(self):
        puuid = "Vg03sswLbwPm1yaJp8ACbObNUCkfJazuq_afJnHrfxZYYy-GvKIipeazQxIjrbqnoNkJFISDuuw9sg"
        matches = await self.riot_api.get_match_history(puuid, 1760825344)
        print(matches)

if __name__ == "__main__":
    PARSER = argparse.ArgumentParser()

    CONFIG = config.Config()
    META_DATABASE = MetaDatabase(CONFIG)
    GAME_DATABASES = {game: get_database_client(game, CONFIG) for game in util.SUPPORTED_GAMES}
    RIOT_API = RiotAPIClient("lol", CONFIG)

    TEST_RUNNER = TestFuncs(CONFIG, META_DATABASE, GAME_DATABASES, RIOT_API)
    FUNCS = [
        func
        for func in TEST_RUNNER.__dir__()
        if not func.startswith("_") and callable(getattr(TEST_RUNNER, func))
    ]

    PARSER.add_argument("func", choices=FUNCS)

    ARGS = PARSER.parse_args()

    func = getattr(TEST_RUNNER, ARGS.func)

    if asyncio.iscoroutinefunction(func):
        asyncio.run(func())
    else:
        func()
