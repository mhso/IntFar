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
    data_games = db_1.cursor().execute("SELECT * FROM games").fetchall()
    data_best = db_1.cursor().execute("SELECT * FROM best_stats").fetchall()
    data_worst = db_1.cursor().execute("SELECT * FROM worst_stats").fetchall()
    participants = db_1.cursor().execute("SELECT * FROM participants").fetchall()
    summoners = db_1.cursor().execute("SELECT * FROM registered_summoners").fetchall()
    balances = db_1.cursor().execute("SELECT * FROM betting_balance").fetchall()
    events = db_1.cursor().execute("SELECT * FROM betting_events").fetchall()
    bets = db_1.cursor().execute("SELECT * FROM bets").fetchall()
    shop_items = db_1.cursor().execute("SELECT * FROM shop_items").fetchall()
    owned_items = db_1.cursor().execute("SELECT * FROM owned_items").fetchall()

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
            db_2.cursor().execute("INSERT OR IGNORE INTO registered_summoners VALUES (?, ?, ?, ?, ?, ?)", (disc_id, summ[1], summ[2], secret, summ[4], 1))
        query = "INSERT INTO games VALUES (?, ?, ?, ?, ?)"
        for data in data_games:
            db_2.cursor().execute(query, data)
        query = query_prefix + "best_stats" + query_cols
        for data in data_best:
            db_2.cursor().execute(query, data)
        query = query_prefix + "worst_stats" + query_cols
        for data in data_worst:
            db_2.cursor().execute(query, data)
        query = "INSERT OR IGNORE INTO participants(game_id, disc_id, doinks) VALUES (?, ?, ?)"
        for data in participants:
            db_2.cursor().execute(query, data)
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
        query = "INSERT OR IGNORE INTO shop_items VALUES (?, ?, ?, ?)"
        for data in shop_items:
            db_2.cursor().execute(query, data)
        query = "INSERT OR IGNORE INTO owned_items VALUES (?, ?, ?)"
        for data in owned_items:
            db_2.cursor().execute(query, data)
        db_2.commit()
