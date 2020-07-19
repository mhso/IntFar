import os
from datetime import datetime, timezone
import sqlite3
from contextlib import closing
import game_stats

class Database:
    def __init__(self, config):
        self.config = config
        self.summoners = []
        if not os.path.exists(self.config.database):
            self.create_database()

        # Populate summoner names and ids lists with currently registered summoners.
        users = self.get_all_registered_users()
        for entry in users:
            disc_id = int(entry[0])
            self.summoners.append((disc_id, entry[1], entry[2]))

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
        self.summoners.append((discord_id, summ_name, summ_id))
        with closing(self.get_connection()) as db:
            db.cursor().execute("INSERT INTO registered_summoners(disc_id, summ_name, summ_id) " +
                                "VALUES (?, ?, ?)", (discord_id, summ_name, summ_id))
            db.commit()

    def discord_id_from_summoner(self, name):
        for disc_id, summ_name, summ_id in self.summoners:
            if summ_name == name:
                return disc_id, summ_name, summ_id
        return None

    def summoner_from_discord_id(self, discord_id):
        for disc_id, summ_name, summ_id in self.summoners:
            if disc_id == discord_id:
                return disc_id, summ_name, summ_id
        return None

    def get_stat(self, stat, value, best, disc_id, maximize=True):
        aggregator = "MAX" if maximize else "MIN"
        table = "best_stats" if best else "worst_stats"
        query = f"SELECT Count(*), {aggregator}({value}), game_id FROM {table} WHERE {stat}=?"
        with closing(self.get_connection()) as db:
            return db.cursor().execute(query, (disc_id,)).fetchone()

    def get_intfars_of_the_month(self):
        min_time = datetime.utcnow()
        current_month = min_time.month
        next_month = 1 if current_month == 12 else current_month + 1
        min_time = min_time.replace(min_time.year, current_month,
                                    1, 0, 0, 0, 0, timezone.utc)
        max_time = min_time.replace(min_time.year, next_month,
                                    1, 14, 0, 0, 0, timezone.utc)
        min_timestamp = int(min_time.timestamp())
        max_timestamp = int(max_time.timestamp())
        query = "SELECT Count(*) as c, int_far FROM best_stats bs, participants p "
        query += "WHERE int_far != 'None' AND bs.game_id=p.game_id AND int_far=disc_id "
        query += "AND timestamp > ? AND timestamp < ? "
        query += "GROUP BY int_far ORDER BY c DESC LIMIT 3"
        with closing(self.get_connection()) as db:
            return db.cursor().execute(query, (min_timestamp, max_timestamp)).fetchall()

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
        query = "SELECT intfar_reason FROM best_stats WHERE int_far=?"
        with closing(self.get_connection()) as db:
            return db.cursor().execute(query, (disc_id,)).fetchall()

    def record_stats(self, intfar_id, intfar_reason, game_id, data, kills_by_our_team):
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
            db.commit()
