import os
from datetime import datetime
import sqlite3
from contextlib import closing
from montly_intfar import TimeZone, MonthlyIntfar
import game_stats

class Database:
    def __init__(self, config):
        self.config = config
        self.summoners = []
        if not os.path.exists(self.config.database):
            self.create_database()

        # Populate summoner names and ids lists with currently registered summoners.
        users = self.get_all_registered_users()
        user_entries = {x[0]: ([], []) for x in users}
        for disc_id, summ_name, summ_id in users:
            user_entries[disc_id][0].append(summ_name)
            user_entries[disc_id][1].append(summ_id)

        for k, v in user_entries.items():
            self.summoners.append((k, v[0], v[1]))

    def get_connection(self):
        return sqlite3.connect(self.config.database)

    def create_database(self):
        with closing(self.get_connection()) as db:
            with open("schema.sql", "r") as f:
                db.cursor().executescript(f.read())
            db.commit()

    def get_registered_user(self, summ_name):
        with closing(self.get_connection()) as db:
            user = db.cursor().execute("SELECT * FROM registered_summoners " +
                                       "WHERE summ_name=?", (summ_name,)).fetchone()
            return user

    def get_all_registered_users(self):
        with closing(self.get_connection()) as db:
            return db.cursor().execute("SELECT disc_id, summ_name, summ_id " +
                                       "FROM registered_summoners").fetchall()

    def add_user(self, summ_name, summ_id, discord_id):
        if self.summoner_from_discord_id(discord_id) is not None:
            for disc_id, summ_names, summ_ids in self.summoners:
                if disc_id == discord_id:
                    summ_names.append(summ_name)
                    summ_ids.append(summ_id)
                    break
        else:
            self.summoners.append((discord_id, [summ_name], [summ_id]))
        with closing(self.get_connection()) as db:
            db.cursor().execute("INSERT INTO registered_summoners(disc_id, summ_name, summ_id) " +
                                "VALUES (?, ?, ?)", (discord_id, summ_name, summ_id))
            db.commit()

    def discord_id_from_summoner(self, name):
        for disc_id, summ_names, summ_ids in self.summoners:
            for (summ_name, summ_id) in zip(summ_names, summ_ids):
                if summ_name.lower() == name:
                    return (disc_id, summ_name, summ_id)
        return None

    def summoner_from_discord_id(self, discord_id):
        for disc_id, summ_names, summ_ids in self.summoners:
            if disc_id == discord_id:
                return (disc_id, summ_names, summ_ids)
        return None

    def get_stat(self, stat, value, best, disc_id, maximize=True):
        aggregator = "MAX" if maximize else "MIN"
        table = "best_stats" if best else "worst_stats"
        query = f"SELECT Count(*), {aggregator}({value}), game_id FROM {table} WHERE {stat}=?"
        with closing(self.get_connection()) as db:
            return db.cursor().execute(query, (disc_id,)).fetchone()

    def get_meta_stats(self):
        query_games = """
        SELECT Count(DISTINCT bs.game_id), timestamp FROM best_stats bs, participants p
        WHERE bs.game_id = p.game_id ORDER BY id
        """
        query_intfars = "SELECT Count(int_far) FROM best_stats WHERE int_far != 'None'"
        query_persons = "SELECT Count(*) FROM participants GROUP BY game_id"
        query_doinks = "SELECT Count(*) FROM participants WHERE doinks != 'None'"
        query_intfar_multis = "SELECT intfar_reason FROM best_stats WHERE intfar_reason != 'None'"
        users = (len(self.summoners),)
        with closing(self.get_connection()) as db:
            game_data = db.cursor().execute(query_games).fetchone()
            intfar_data = db.cursor().execute(query_intfars).fetchone()
            doinks_data = db.cursor().execute(query_doinks).fetchone()
            persons_counts = db.cursor().execute(query_persons)
            intfar_multis_data = db.cursor().execute(query_intfar_multis)
            persons_count = {2: 0, 3: 0, 4: 0, 5: 0}
            for persons in persons_counts:
                persons_count[persons[0]] += 1
            twos_ratio = int((persons_count[2] / game_data[0]) * 100)
            threes_ratio = int((persons_count[3] / game_data[0]) * 100)
            fours_ratio = int((persons_count[4] / game_data[0]) * 100)
            fives_ratio = int((persons_count[5] / game_data[0]) * 100)
            games_ratios = [twos_ratio, threes_ratio, fours_ratio, fives_ratio]

            intfar_counts = [0, 0, 0, 0]
            intfar_multi_counts = {
                1: 0, 2: 0, 3: 0, 4: 0
            }
            for reason in intfar_multis_data:
                amount = 0
                for index, c in enumerate(reason):
                    if c == "1":
                        intfar_counts[index] += 1
                        amount += 1
                if amount > 0:
                    intfar_multi_counts[amount] += 1
            total_intfars = len(intfar_multis_data)
            twos_ratio = int((intfar_counts[0] / total_intfars) * 100)
            threes_ratio = int((intfar_counts[1] / total_intfars) * 100)
            fours_ratio = int((intfar_counts[2] / total_intfars) * 100)
            fives_ratio = int((intfar_counts[3] / total_intfars) * 100)
            intfars_ratios = [twos_ratio, threes_ratio, fours_ratio, fives_ratio]

            twos_ratio = int((intfar_multi_counts[1] / total_intfars) * 100)
            threes_ratio = int((intfar_multi_counts[2] / total_intfars) * 100)
            fours_ratio = int((intfar_multi_counts[3] / total_intfars) * 100)
            fives_ratio = int((intfar_multi_counts[4] / total_intfars) * 100)
            intfar_multis_ratios = [twos_ratio, threes_ratio, fours_ratio, fives_ratio]

            return (game_data + users + intfar_data + doinks_data +
                    (games_ratios, intfars_ratios, intfar_multis_ratios))

    def get_intfars_of_the_month(self):
        tz_cph = TimeZone()
        curr_time = datetime.now(tz_cph)
        current_month = curr_time.month
        min_timestamp = None
        if curr_time.day == 1 and curr_time.hour < MonthlyIntfar.HOUR_OF_ANNOUNCEMENT:
            # Get Int-Far stats for previous month.
            prev_month = 12 if current_month == 1 else current_month - 1
            prev_year = curr_time.year if prev_month != 12 else curr_time.year - 1
            prev_time = curr_time.replace(prev_year, prev_month, 1,
                                          0, 0, 0, 0, tz_cph)
            min_timestamp = int(prev_time.timestamp())
        else:
            # Get Int-Far stats for current month.
            prev_time = curr_time.replace(curr_time.year, current_month, 1,
                                          0, 0, 0, 0, tz_cph)
            min_timestamp = int(prev_time.timestamp())

        max_timestamp = int(curr_time.timestamp())

        query_intfars = """
        SELECT Count(*) as c, int_far FROM best_stats bs, participants p 
        WHERE int_far != 'None' AND bs.game_id=p.game_id AND int_far=disc_id 
        AND timestamp > ? AND timestamp < ? 
        GROUP BY int_far ORDER BY c DESC
        """
        query_games = """
        SELECT Count(*) as c, disc_id FROM best_stats bs, participants p 
        WHERE bs.game_id=p.game_id
        AND timestamp > ? AND timestamp < ? 
        GROUP BY disc_id;
        """
        with closing(self.get_connection()) as db:
            games_per_person = db.cursor().execute(query_games,
                                                   (min_timestamp, max_timestamp)).fetchall()
            intfars_per_person = db.cursor().execute(query_intfars, (min_timestamp, max_timestamp))
            data_per_person = []
            for intfars, intfar_id in intfars_per_person:
                total_games = 0
                for games_played, disc_id in games_per_person:
                    if disc_id == intfar_id:
                        total_games = games_played
                        break
                if total_games < 5: # Disqualify people with less than 5 games played this month.
                    continue
                pct_intfar = int((intfars / total_games) * 100)
                data_per_person.append((intfar_id, total_games, intfars, pct_intfar))
                if len(data_per_person) == 3:
                    return data_per_person
            return data_per_person

    def get_longest_intfar_streak(self, disc_id):
        query = "SELECT int_far FROM best_stats ORDER BY id"
        with closing(self.get_connection()) as db:
            int_fars = db.cursor().execute(query).fetchall()
            max_count = 0
            count = 0
            for int_far in int_fars:
                if int_far[0] is None or disc_id != int_far[0]:
                    count = 0
                else:
                    count += 1
                if count > max_count:
                    max_count = count
            return max_count

    def get_longest_no_intfar_streak(self, disc_id):
        query = """
        SELECT int_far FROM best_stats bs, participants p
        WHERE bs.game_id = p.game_id and disc_id=?
        ORDER BY id
        """
        with closing(self.get_connection()) as db:
            int_fars = db.cursor().execute(query, (disc_id,)).fetchall()
            max_count = 0
            count = 0
            for int_far in int_fars:
                if disc_id == int_far[0]:
                    count = 0
                else:
                    count += 1
                if count > max_count:
                    max_count = count
            return max_count

    def get_current_intfar_streak(self):
        query = "SELECT int_far FROM best_stats ORDER BY id DESC"
        with closing(self.get_connection()) as db:
            int_fars = db.cursor().execute(query).fetchall()
            prev_intfar = int_fars[0][0]
            for count, int_far in enumerate(int_fars[1:], start=1):
                if int_far[0] is None or prev_intfar != int_far[0]:
                    return count, prev_intfar
            return len(int_fars), prev_intfar # All the int-fars is the current int-far!

    def get_intfar_stats(self, disc_id):
        query_total = "SELECT Count(*) FROM participants WHERE disc_id=?"
        query_intfar = "SELECT intfar_reason FROM best_stats WHERE int_far=?"
        with closing(self.get_connection()) as db:
            total_games = db.cursor().execute(query_total, (disc_id,)).fetchone()[0]
            intfar_games = db.cursor().execute(query_intfar, (disc_id,)).fetchall()
            return total_games, intfar_games

    def get_intfar_relations(self, disc_id):
        query_games = """
        SELECT p2.disc_id, Count(*) as c FROM participants p1, participants p2
        WHERE p1.disc_id != p2.disc_id AND p1.game_id = p2.game_id AND p1.disc_id=?
        GROUP BY p1.disc_id, p2.disc_id ORDER BY c DESC;
        """
        query_intfars = """
        SELECT disc_id, Count(*) as c FROM best_stats bs, participants p
        WHERE int_far != 'None' AND bs.game_id=p.game_id AND int_far=?
        GROUP BY disc_id ORDER BY c DESC
        """
        with closing(self.get_connection()) as db:
            games_with_person = {}
            intfars_with_person = {}
            for part_id, intfars in db.cursor().execute(query_intfars, (disc_id,)):
                if disc_id == part_id:
                    continue
                intfars_with_person[part_id] = intfars
            for part_id, games in db.cursor().execute(query_games, (disc_id,)):
                games_with_person[part_id] = games
            return games_with_person, intfars_with_person

    def get_doinks_stats(self, disc_id):
        query = "SELECT doinks FROM participants WHERE doinks != 'None' AND disc_id=?"
        with closing(self.get_connection()) as db:
            return db.cursor().execute(query, (disc_id,)).fetchall()

    def record_stats(self, intfar_id, intfar_reason, doinks, game_id, data, users_in_game):
        kills_by_our_team = data[0][1]["kills_by_team"]
        timestamp = data[0][1]["timestamp"] // 1000
        (min_kills_id, min_kills,
         max_kills_id, max_kills) = game_stats.get_outlier_stat("kills", data)
        (min_deaths_id, min_deaths,
         max_deaths_id, max_deaths) = game_stats.get_outlier_stat("deaths", data)
        max_kda_id, stats = game_stats.get_outlier(data, "kda", asc=False)
        max_kda = game_stats.calc_kda(stats)
        min_kda_id, stats = game_stats.get_outlier(data, "kda", asc=True)
        min_kda = game_stats.calc_kda(stats)
        (min_damage_id, min_damage,
         max_damage_id, max_damage) = game_stats.get_outlier_stat("totalDamageDealtToChampions", data)
        (min_cs_id, min_cs,
         max_cs_id, max_cs) = game_stats.get_outlier_stat("totalMinionsKilled", data)
        (min_gold_id, min_gold,
         max_gold_id, max_gold) = game_stats.get_outlier_stat("goldEarned", data)
        max_kp_id, stats = game_stats.get_outlier(data, "kp", asc=False, total_kills=kills_by_our_team)
        max_kp = game_stats.calc_kill_participation(stats, kills_by_our_team)
        min_kp_id, stats = game_stats.get_outlier(data, "kp", asc=True, total_kills=kills_by_our_team)
        min_kp = game_stats.calc_kill_participation(stats, kills_by_our_team)
        (min_wards_id, min_wards,
         max_wards_id, max_wards) = game_stats.get_outlier_stat("visionWardsBoughtInGame", data)
        (min_vision_id, min_vision,
         max_vision_id, max_vision) = game_stats.get_outlier_stat("visionScore", data)

        self.config.log(
            "Saving best stats:\n"+
            f"{game_id}, {intfar_id}, {intfar_reason}, " +
            f"({max_kills_id} - {max_kills}), ({min_deaths_id} - {min_deaths}), " +
            f"({max_kda_id} - {max_kda}), ({max_damage_id} - {max_damage}), " +
            f"({max_cs_id} - {max_cs}), ({max_gold_id} - {max_gold}), " +
            f"({max_kp_id} - {max_kp}), ({max_wards_id} - {max_wards}), " +
            f"({max_vision_id} - {max_vision})"
        )
        self.config.log(
            "Saving worst stats:\n"+
            f"{game_id}, {intfar_id}, {intfar_reason}, " +
            f"({min_kills_id} - {min_kills}), ({max_deaths_id} - {max_deaths}), " +
            f"({min_kda_id} - {min_kda}), ({min_damage_id} - {min_damage}), " +
            f"({min_cs_id} - {min_cs}), ({min_gold_id} - {min_gold}), " +
            f"({min_kp_id} - {min_kp}), ({min_wards_id} - {min_wards}), " +
            f"({min_vision_id} - {min_vision})"
        )
        self.config.log(
            "Saving participants:\n"+
            f"{game_id}, {users_in_game}, {timestamp}, {doinks}"
        )

        query_prefix = "INSERT INTO "
        query_cols = (
            """
            (game_id, int_far, intfar_reason, kills, kills_id, deaths,
            deaths_id, kda, kda_id, damage, damage_id, cs, cs_id, gold, gold_id,
            kp, kp_id, vision_wards, vision_wards_id, vision_score, vision_score_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        query_best = query_prefix + " best_stats" + query_cols
        query_worst = query_prefix + " worst_stats " + query_cols

        with closing(self.get_connection()) as db:
            db.cursor().execute(query_best, (game_id, intfar_id, intfar_reason, max_kills,
                                             max_kills_id, min_deaths, min_deaths_id, max_kda,
                                             max_kda_id, max_damage, max_damage_id,
                                             max_cs, max_cs_id, max_gold, max_gold_id,
                                             max_kp, max_kp_id, max_wards, max_wards_id,
                                             max_vision, max_vision_id))
            db.cursor().execute(query_worst, (game_id, intfar_id, intfar_reason, min_kills,
                                              min_kills_id, max_deaths, max_deaths_id, min_kda,
                                              min_kda_id, min_damage, min_damage_id,
                                              min_cs, min_cs_id, min_gold, min_gold_id,
                                              min_kp, min_kp_id, min_wards, min_wards_id,
                                              min_vision, min_vision_id))
            query = "INSERT INTO participants(game_id, disc_id, timestamp, doinks) VALUES (?, ?, ?, ?)"
            for disc_id, _, _ in users_in_game:
                doink = doinks.get(disc_id, None)
                db.cursor().execute(query, (game_id, disc_id, timestamp, doink))
            db.commit()
