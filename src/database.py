import os
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

    def get_stat(self, stat, best, disc_id):
        table = "best_stats" if best else "worst_stats"
        query = f"SELECT Count(*) FROM {table} WHERE {stat}=?"
        with closing(self.get_connection()) as db:
            return db.cursor().execute(query, (disc_id,)).fetchone()[0]

    def record_stats(self, intfar_id, game_id, data):
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
        max_kp_id, stats = game_stats.get_outlier(data, "kp", asc=False)
        max_kp = game_stats.calc_kda(stats)
        min_kp_id, stats = game_stats.get_outlier(data, "kp", asc=True)
        min_kp = game_stats.calc_kda(stats)
        (min_wards_id, min_wards,
         max_wards_id, max_wards) = game_stats.get_outlier_stat("visionWardsBoughtInGame", data)
        (min_vision_id, min_vision,
         max_vision_id, max_vision) = game_stats.get_outlier_stat("visionScore", data)

        query_prefix = "INSERT INTO "
        query_cols = (
            """
            (game_id, int_far, kills, kills_id, deaths,
            deaths_id, kda, kda_id, damage, damage_id, cs, cs_id, gold, gold_id,
            kp, kp_id, vision_wards, vision_wards_id, vision_score, vision_score_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        query_best = query_prefix + " best_stats" + query_cols
        query_worst = query_prefix + " worst_stats " + query_cols

        with closing(self.get_connection()) as db:
            db.cursor().execute(query_best, (game_id, intfar_id, max_kills, max_kills_id,
                                             min_deaths, min_deaths_id, max_kda,
                                             max_kda_id, max_damage, max_damage_id,
                                             max_cs, max_cs_id, max_gold, max_gold_id,
                                             max_kp, max_kp_id, max_wards, max_wards_id,
                                             max_vision, max_vision_id))
            db.cursor().execute(query_worst, (game_id, intfar_id, min_kills, min_kills_id,
                                              max_deaths, max_deaths_id, min_kda,
                                              min_kda_id, min_damage, min_damage_id,
                                              min_cs, min_cs_id, min_gold, min_gold_id,
                                              min_kp, min_kp_id, min_wards, min_wards_id,
                                              min_vision, min_vision_id))
            db.commit()
