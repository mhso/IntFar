import os
from api.database import Database
from api.config import Config

conf_1 = Config()

database_client_1 = Database(conf_1)

conf_2 = Config()
conf_2.database = "resources/copy.db"

if os.path.exists(conf_2.database):
    os.remove(conf_2.database)

database_client_2 = Database(conf_2)

with database_client_1.get_connection() as db_1:
    data_games_lol = db_1.cursor().execute("SELECT * FROM games_lol").fetchall()
    data_games_csgo = db_1.cursor().execute("SELECT * FROM games_csgo").fetchall()
    participants_lol = db_1.cursor().execute("SELECT * FROM participants_lol").fetchall()
    participants_csgo = db_1.cursor().execute("SELECT * FROM participants_csgo").fetchall()
    users = db_1.cursor().execute("SELECT * FROM users").fetchall()
    users_lol = db_1.cursor().execute("SELECT * FROM users_lol").fetchall()
    users_csgo = db_1.cursor().execute("SELECT * FROM users_csgo").fetchall()
    balances = db_1.cursor().execute("SELECT * FROM betting_balance").fetchall()
    bets = db_1.cursor().execute("SELECT * FROM bets").fetchall()
    shop_items = db_1.cursor().execute("SELECT * FROM shop_items").fetchall()
    owned_items = db_1.cursor().execute("SELECT * FROM owned_items").fetchall()
    event_sounds = db_1.cursor().execute("SELECT * FROM event_sounds").fetchall()
    champ_lists = db_1.cursor().execute("SELECT * FROM champ_lists").fetchall()
    list_items = db_1.cursor().execute("SELECT * FROM list_items").fetchall()
    missed_games = db_1.cursor().execute("SELECT * FROM missed_games").fetchall()

    with database_client_2.get_connection() as db_2:
        for user in users:
            db_2.cursor().execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?)", user)

        for user in users_lol:
            db_2.cursor().execute("INSERT OR IGNORE INTO users_lol VALUES (?, ?, ?, ?, ?)", user)

        for user in users_csgo:
            db_2.cursor().execute("INSERT OR IGNORE INTO users_csgo VALUES (?, ?, ?, ?, ?, ?, ?)", user)
            db_2.cursor().execute("INSERT OR IGNORE INTO users_cs2 VALUES (?, ?, ?, ?, ?, ?, ?)", user)

        query = "INSERT INTO games_lol VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        for data in data_games_lol:
            db_2.cursor().execute(query, data)

        query = "INSERT INTO games_csgo VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        for data in data_games_csgo:
            db_2.cursor().execute(query, data)

        query = (
            """
            INSERT INTO participants_lol VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        for data in participants_lol:
            db_2.cursor().execute(query, data)

        query = (
            """
            INSERT INTO participants_csgo VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        for data in participants_csgo:
            db_2.cursor().execute(query, data)

        query = "INSERT OR IGNORE INTO betting_balance(disc_id, tokens) VALUES (?, ?)"
        for data in balances:
            db_2.cursor().execute(query, data)

        query = (
            "INSERT OR IGNORE INTO bets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        for data in bets:
            db_2.cursor().execute(query, data)

        query = "INSERT INTO shop_items VALUES (?, ?, ?, ?)"
        for data in shop_items:
            db_2.cursor().execute(query, data)

        query = "INSERT INTO owned_items VALUES (?, ?, ?)"
        for data in owned_items:
            db_2.cursor().execute(query, data)

        query = "INSERT INTO event_sounds(disc_id, game, sound, event) VALUES (?, ?, ?, ?)"
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
            db_2.cursor().execute(query, data)

        db_2.commit()
