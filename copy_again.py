import os
from api.database import Database
from api.config import Config
from api.betting import BETTING_IDS

conf_1 = Config()

database_client_1 = Database(conf_1)

conf_2 = Config()
conf_2.database = "resources/copy.db"

if os.path.exists(conf_2.database):
    os.remove(conf_2.database)

database_client_2 = Database(conf_2)

with database_client_1.get_connection() as db_1:
    data_games = db_1.cursor().execute("SELECT * FROM games").fetchall()
    participants = db_1.cursor().execute("SELECT game_id, disc_id, doinks, kills, deaths, assists, kda, kp, champ_id, damage, cs, cs_per_min, gold, vision_wards, vision_score, steals FROM participants").fetchall()
    summoners = db_1.cursor().execute("SELECT * FROM registered_summoners").fetchall()
    balances = db_1.cursor().execute("SELECT * FROM betting_balance").fetchall()
    bets = db_1.cursor().execute("SELECT * FROM bets").fetchall()
    shop_items = db_1.cursor().execute("SELECT * FROM shop_items").fetchall()
    owned_items = db_1.cursor().execute("SELECT * FROM owned_items").fetchall()
    event_sounds = db_1.cursor().execute("SELECT * FROM event_sounds").fetchall()
    champ_lists = db_1.cursor().execute("SELECT * FROM champ_lists").fetchall()
    list_items = db_1.cursor().execute("SELECT * FROM list_items").fetchall()
    missed_games = db_1.cursor().execute("SELECT * FROM missed_games").fetchall()

    with database_client_2.get_connection() as db_2:
        for summ in summoners:
            disc_id = int(summ[0])
            secret = summ[3]
            db_2.cursor().execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", (disc_id, secret, summ[4]))

        for summ in summoners:
            disc_id = int(summ[0])
            db_2.cursor().execute("INSERT OR IGNORE INTO users_lol VALUES (?, ?, ?, ?)", (disc_id, summ[1], summ[2], summ[5]))

        query = "INSERT INTO games_lol VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        for data in data_games:
            db_2.cursor().execute(query, data)

        query = (
            """
            INSERT INTO participants_lol
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        for data in participants:
            db_2.cursor().execute(query, data)

        query = "INSERT OR IGNORE INTO betting_balance(disc_id, tokens) VALUES (?, ?)"
        for data in balances:
            db_2.cursor().execute(query, data)

        query = (
            "INSERT OR IGNORE INTO bets(id, better_id, guild_id, game_id, game, timestamp, event_id, "
            "amount, game_duration, target, ticket, result, payout) "
            "VALUES (?, ?, ?, ?, 'lol', ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for data in bets:
            data = list(data)
            data[6] = BETTING_IDS[data[6]]
            db_2.cursor().execute(query, tuple(data))

        query = "INSERT INTO shop_items VALUES (?, ?, ?, ?)"
        for data in shop_items:
            db_2.cursor().execute(query, data)

        query = "INSERT INTO owned_items VALUES (?, ?, ?)"
        for data in owned_items:
            db_2.cursor().execute(query, data)

        query = "INSERT INTO event_sounds(disc_id, sound, event) VALUES (?, ?, ?)"
        for data in event_sounds:
            db_2.cursor().execute(query, data)

        query = "INSERT INTO champ_lists(id, name, owner_id) VALUES (?, ?, ?)"
        for data in champ_lists:
            db_2.cursor().execute(query, data)

        query = "INSERT INTO list_items(id, champ_id, list_id) VALUES (?, ?, ?)"
        for data in list_items:
            db_2.cursor().execute(query, data)

        query = "INSERT INTO missed_games(game_id, game, guild_id, timestamp) VALUES (?, ?, ?, ?)"
        for data in missed_games:
            game = "lol"
            data = [data[0], game] + list(data[1:])
            db_2.cursor().execute(query, tuple(data))

        db_2.commit()
