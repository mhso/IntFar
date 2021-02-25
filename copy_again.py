import json
from contextlib import closing
from api.database import Database
from api.config import Config

auth = json.load(open("discbot/auth.json"))

conf_1 = Config()

database_client_1 = Database(conf_1)

conf_2 = Config()
conf_2.database = "copy.db"

database_client_2 = Database(conf_2)

with database_client_1.get_connection() as db_1:
    data_best = db_1.cursor().execute("SELECT * FROM best_stats").fetchall()
    data_worst = db_1.cursor().execute("SELECT * FROM worst_stats").fetchall()
    participants = db_1.cursor().execute("SELECT * FROM participants").fetchall()
    summoners = db_1.cursor().execute("SELECT * FROM registered_summoners").fetchall()
    balances = db_1.cursor().execute("SELECT * FROM betting_balance").fetchall()
    events = db_1.cursor().execute("SELECT * FROM betting_events").fetchall()
    bets = db_1.cursor().execute("SELECT * FROM bets").fetchall()

    query_prefix = "INSERT INTO "
    query_cols = (
        """
        (id, game_id, first_blood, kills, kills_id, deaths,
        deaths_id, kda, kda_id, damage, damage_id, cs, cs_id, cs_per_min, cs_per_min_id,
        gold, gold_id, kp, kp_id, vision_wards, vision_wards_id, vision_score, vision_score_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )

    with database_client_2.get_connection() as db_2:
        for summ in summoners:
            disc_id = int(summ[0])
            secret = summ[3]
            db_2.cursor().execute("INSERT OR IGNORE INTO registered_summoners VALUES (?, ?, ?, ?, ?)", (disc_id, summ[1], summ[2], secret, summ[4]))
        for data in data_best:
            query = "INSERT INTO games VALUES (?, ?, ?, ?, ?)"
            db_2.cursor().execute(query, (data[1], 0, data[2], data[3], 619073595561213953))
        for data in participants:
            query = "UPDATE games SET timestamp=? WHERE game_id=?"
            db_2.cursor().execute(query, (data[2], data[0]))
        query = query_prefix + "best_stats" + query_cols
        for data in data_best:
            reshaped_data = data[:2] + data[4:]
            db_2.cursor().execute(query, reshaped_data)
        query = query_prefix + "worst_stats" + query_cols
        for data in data_worst:
            reshaped_data = data[:2] + data[4:]
            db_2.cursor().execute(query, reshaped_data)
        query = "INSERT OR IGNORE INTO participants(game_id, disc_id, doinks) VALUES (?, ?, ?)"
        for data in participants:
            reshaped = data[:2] + (data[3],)
            db_2.cursor().execute(query, reshaped)
        query = "INSERT OR IGNORE INTO betting_balance(disc_id, tokens) VALUES (?, ?)"
        for data in balances:
            db_2.cursor().execute(query, data)
        query = "INSERT OR IGNORE INTO betting_events(id, max_return) VALUES (?, ?)"
        for data in events:
            db_2.cursor().execute(query, data)
        query = (
            "INSERT OR IGNORE INTO bets(id, better_id, guild_id, game_id, timestamp, event_id, "
            "amount, game_duration, target, ticket, result, payout) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for data in bets:
            db_2.cursor().execute(query, data)
        db_2.commit()
