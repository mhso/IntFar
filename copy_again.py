from api.database import Database
from api.config import Config

conf_1 = Config()

database_client_1 = Database(conf_1)

conf_2 = Config()
conf_2.database = "resources/copy.db"

database_client_2 = Database(conf_2)

with database_client_1.get_connection() as db_1:
    data_games = db_1.cursor().execute("SELECT * FROM games").fetchall()
    participants = db_1.cursor().execute("SELECT * FROM participants").fetchall()
    summoners = db_1.cursor().execute("SELECT * FROM registered_summoners").fetchall()
    balances = db_1.cursor().execute("SELECT * FROM betting_balance").fetchall()
    events = db_1.cursor().execute("SELECT * FROM betting_events").fetchall()
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
            db_2.cursor().execute("INSERT OR IGNORE INTO registered_summoners VALUES (?, ?, ?, ?, ?, ?)", (disc_id, summ[1], summ[2], secret, summ[4], summ[5]))

        query = "INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        for data in data_games:
            db_2.cursor().execute(query, data)

        query = (
            """
            INSERT INTO participants
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        for data in participants:
            data_list = list(data)

            kills = data_list[4]
            deaths = data_list[5]
            kda = data_list[6]

            if kills is None or deaths is None:
                assists = None
            else:
                if deaths == 0:
                    assists = kda - kills
                else:
                    assists = round(kda * deaths - kills)

            data_list_1 = data_list[:6]
            data_list_2 = data_list[6:]
            data_list = data_list_1 + [assists] + data_list_2

            db_2.cursor().execute(query, tuple(data_list))

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

        query = "INSERT INTO missed_games(game_id, guild_id, timestamp) VALUES (?, ?, ?)"
        for data in missed_games:
            db_2.cursor().execute(query, data)

        db_2.commit()
