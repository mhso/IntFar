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
        with closing(self.get_connection()) as db:
            users = db.cursor().execute("SELECT * FROM registered_summoners").fetchall()
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

    def add_user(self, summ_name, summ_id, discord_id):
        self.summoners.append((summ_name, summ_id, discord_id))
        with closing(self.get_connection()) as db:
            db.cursor().execute("INSERT INTO registered_summoners(disc_id, summ_name, summ_id) " +
                                "VALUES (?, ?, ?)", (discord_id, summ_name, summ_id))
            db.commit()

    def summoner_from_discord_id(self, discord_id):
        for disc_id, summ_name, summ_id in self.summoners:
            if disc_id == discord_id:
                return disc_id, summ_name, summ_id
        return None

    def get_stat(self, stat, disc_id):
        query = f"SELECT Count(*) FROM game_stats WHERE {stat}=?"
        with closing(self.get_connection()) as db:
            return db.cursor().execute(query, (disc_id,)).fetchone()

    def record_stats(self, intfar_id, game_id, data):
        most_kills_id, stats = game_stats.get_outlier(data, "kills", asc=False)
        most_kills = stats["kills"]
        fewest_deaths_id, stats = game_stats.get_outlier(data, "deaths")
        fewest_deaths = stats["deaths"]
        highest_kda_id, stats = game_stats.get_outlier(data, "kda", asc=False)
        highest_kda = game_stats.calc_kda(stats)
        most_damage_id, stats = game_stats.get_outlier(data, "totalDamageDealtToChampions", asc=False)
        most_damage = stats["totalDamageDealtToChampions"]
        most_cs_id, stats = game_stats.get_outlier(data, "totalMinionsKilled", asc=False)
        most_cs = stats["totalMinionsKilled"]
        most_gold_id, stats = game_stats.get_outlier(data, "goldEarned", asc=False)
        most_gold = stats["goldEarned"]
        highest_kp_id, stats = game_stats.get_outlier(data, "kp", asc=False)
        highest_kp = game_stats.calc_kill_participation(stats, data)
        highest_vision_score_id, stats = game_stats.get_outlier(data, "visionScore", asc=False)
        highest_vision_score = stats["visionScore"]

        query = (
            """
            INSERT INTO game_stats(game_id, int_far, most_kills, most_kills_id,
            fewest_deaths, fewest_deaths_id, highest_kda, highest_kda_id,
            most_damage, most_damage_id, most_cs, most_cs_id, most_gold, most_gold_id,
            highest_kp, highest_kp_id, highest_vision_score, highest_vision_score_id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )

        with closing(self.get_connection()) as db:
            db.cursor().execute(query, (game_id, intfar_id, most_kills, most_kills_id,
                                        fewest_deaths, fewest_deaths_id, highest_kda,
                                        highest_kda_id, most_damage, most_damage_id,
                                        most_cs, most_cs_id, most_gold, most_gold_id,
                                        highest_kp, highest_kp_id, highest_vision_score,
                                        highest_vision_score_id))
            db.commit()
