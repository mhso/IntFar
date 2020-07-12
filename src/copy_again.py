import json
from contextlib import closing
from database import Database
from config import Config

auth = json.load(open("auth.json"))

conf_1 = Config()

database_client_1 = Database(conf_1)

conf_2 = Config()
conf_2.database = "copy.db"

database_client_2 = Database(conf_2)

with closing(database_client_1.get_connection()) as db_1:
    data_best = db_1.cursor().execute("SELECT * FROM best_stats").fetchall()
    data_worst = db_1.cursor().execute("SELECT * FROM worst_stats").fetchall()
    summoners = db_1.cursor().execute("SELECT * FROM registered_summoners").fetchall()

    query_prefix = "INSERT INTO "
    query_cols = (
        """
        (game_id, int_far, intfar_reason, kills, kills_id, deaths,
        deaths_id, kda, kda_id, damage, damage_id, cs, cs_id, gold, gold_id,
        kp, kp_id, vision_wards, vision_wards_id, vision_score, vision_score_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )

    with closing(database_client_2.get_connection()) as db_2:
        for summ in summoners:
            db_2.cursor().execute("INSERT INTO registered_summoners VALUES (?, ?, ?)", summ)
        query = query_prefix + "best_stats" + query_cols
        for data in data_best:
            db_2.cursor().execute(query, data)
        query = query_prefix + "worst_stats" + query_cols
        for data in data_worst:
            db_2.cursor().execute(query, data)
        db_2.commit()