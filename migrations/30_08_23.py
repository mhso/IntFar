import os
from api.meta_database import Database
from api.config import Config

BETTING_IDS = {
    "game_win": 0,
    "game_loss": 1,
    "no_intfar": 2,
    "intfar": 3,
    "intfar_kda": 4,
    "intfar_deaths": 5,
    "intfar_kp": 6,
    "intfar_vision": 7,
    "doinks": 8,
    "doinks_kda": 9,
    "doinks_kills": 10,
    "doinks_damage": 11,
    "doinks_penta": 12,
    "doinks_vision": 13,
    "doinks_kp": 14,
    "doinks_monsters": 15,
    "doinks_cs": 16,
    "most_kills": 17,
    "most_damage": 18,
    "most_kp": 19,
    "highest_kda": 20
}

conf_1 = Config()

database_client_1 = Database(conf_1)

conf_2 = Config()
conf_2.database = "../resources/copy.db"

if os.path.exists(conf_2.database):
    os.remove(conf_2.database)

database_client_2 = Database(conf_2)

with database_client_1.get_connection() as db_1:
    data_games = db_1.cursor().execute("SELECT * FROM games").fetchall()
    participants = db_1.cursor().execute("SELECT * FROM participants").fetchall()
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

        seen_users = set()
        for summ in summoners:
            disc_id = int(summ[0])

            main = 1 if disc_id not in seen_users else 0

            seen_users.add(disc_id)
            db_2.cursor().execute("INSERT OR IGNORE INTO users_lol VALUES (?, ?, ?, ?, ?)", (disc_id, summ[1], summ[2], main, summ[5]))

        query = "INSERT INTO games_lol(game_id, timestamp, duration, intfar_id, intfar_reason, first_blood, win, guild_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        for data in data_games:
            db_2.cursor().execute(query, data)

        query = (
            """
            INSERT INTO participants_lol(game_id, disc_id, champ_id, doinks, kills, deaths, assists, kda, damage, cs, cs_per_min, gold, kp, vision_wards, vision_score, steals)
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
            for new_event, old_event in BETTING_IDS.items():
                if int(data[5]) == old_event:
                    data[5] = new_event
                    break
            db_2.cursor().execute(query, tuple(data))

        query = "INSERT INTO shop_items VALUES (?, ?, ?, ?)"
        for data in shop_items:
            db_2.cursor().execute(query, data)

        query = "INSERT INTO owned_items VALUES (?, ?, ?)"
        for data in owned_items:
            db_2.cursor().execute(query, data)

        query = "INSERT INTO event_sounds(disc_id, game, sound, event) VALUES (?, 'lol', ?, ?)"
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
