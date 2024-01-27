import os
from api.meta_database import MetaDatabase
from api.util import SUPPORTED_GAMES
SUPPORTED_GAMES["csgo"] = "Counter Strike: Global Offensive"
from api.game_databases import get_database_client
from api.config import Config
from api.game_apis.lol import RiotAPIClient
from time import sleep

conf_1 = Config()
conf_1.database_folder = "resources"

meta_database_1 = MetaDatabase(conf_1)

conf_2 = Config()

if os.path.exists(f"{conf_2.database_folder}/meta.db"):
    os.remove(f"{conf_2.database_folder}/meta.db")

meta_database_2 = MetaDatabase(conf_2)

riot_api = RiotAPIClient("lol", conf_1)

def get_questionmark_str(values):
    return ", ".join("?" for _ in values[0])

with meta_database_1.get_connection() as meta_db_1:
    with meta_database_2.get_connection() as meta_db_2:
        users = meta_db_1.cursor().execute("SELECT * FROM users").fetchall()
        query = f"INSERT OR IGNORE INTO users VALUES ({get_questionmark_str(users)})"
        meta_db_2.cursor().executemany(query, users)

        balances = meta_db_1.cursor().execute("SELECT * FROM betting_balance").fetchall()
        query = "INSERT OR IGNORE INTO betting_balance(disc_id, tokens) VALUES (?, ?)"
        meta_db_2.cursor().executemany(query, balances)

        bets = meta_db_1.cursor().execute("SELECT * FROM bets").fetchall()
        query = "INSERT OR IGNORE INTO bets VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        meta_db_2.cursor().executemany(query, bets)

        shop_items = meta_db_1.cursor().execute("SELECT * FROM shop_items").fetchall()
        query = "INSERT INTO shop_items VALUES (?, ?, ?, ?)"
        meta_db_2.cursor().executemany(query, shop_items)

        owned_items = meta_db_1.cursor().execute("SELECT * FROM owned_items").fetchall()
        query = "INSERT INTO owned_items VALUES (?, ?, ?)"
        meta_db_2.cursor().executemany(query, owned_items)

        meta_db_2.commit()

    for game in SUPPORTED_GAMES:
        if os.path.exists(f"{conf_2.database_folder}/{game}.db"):
            os.remove(f"{conf_2.database_folder}/{game}.db")

        game_database = get_database_client(game, conf_2)

        with game_database.get_connection() as game_db:
            game_users = meta_db_1.cursor().execute(f"SELECT * FROM users_{game}").fetchall()

            if game == "lol":
                new_users = []
                for row in game_users:
                    list_row = list(row)
                    summ_info = riot_api.get_summoner_data(row[1])
                    if summ_info is None:
                        print(f"WARNING: Summoner info for {row[1]} is None!")
                        list_row.insert(3, "unknown")
                        continue

                    list_row.insert(3, summ_info["puuid"])
                    sleep(1.5)
                    new_users.append(tuple(list_row))
                game_users = new_users

            query = f"INSERT OR IGNORE INTO users VALUES ({get_questionmark_str(game_users)})"
            game_db.cursor().executemany(query, game_users)

            games = meta_db_1.cursor().execute(f"SELECT * FROM games_{game}").fetchall()
            query = f"INSERT OR IGNORE INTO games VALUES ({get_questionmark_str(games)})"
            game_db.cursor().executemany(query, games)

            participants = meta_db_1.cursor().execute(f"SELECT * FROM participants_{game}").fetchall()
            if game in ("cs2", "lol"):
                participants_swapped = []
                for row in participants:
                    list_row = list(row)
                    temp = list_row[2]
                    for index in range(3, 6):
                        list_row[index-1] = list_row[index]
                    list_row[5] = temp
                    participants_swapped.append(tuple(list_row))
                participants = participants_swapped
        
            query = f"INSERT OR IGNORE INTO participants VALUES ({get_questionmark_str(participants)})"
            game_db.cursor().executemany(query, participants)

            event_sounds = meta_db_1.cursor().execute("SELECT disc_id, sound, event FROM event_sounds WHERE game=?", (game,)).fetchall()
            game_db.cursor().executemany("INSERT INTO event_sounds(disc_id, sound, event) VALUES (?, ?, ?)", event_sounds)

            missed_games = meta_db_1.cursor().execute("SELECT game_id, guild_id, timestamp FROM missed_games").fetchall()
            query = "INSERT INTO missed_games(game_id, guild_id, timestamp) VALUES (?, ?, ?)"
            game_db.cursor().executemany(query, missed_games)

            if game == "lol":
                champ_lists = meta_db_1.cursor().execute("SELECT * FROM champ_lists").fetchall()
                game_db.cursor().executemany("INSERT OR IGNORE INTO champ_lists(id, name, owner_id) VALUES(?, ?, ?)", champ_lists)

                list_items = meta_db_1.cursor().execute("SELECT * FROM list_items").fetchall()
                game_db.cursor().executemany("INSERT OR IGNORE INTO list_items(id, champ_id, list_id) VALUES (?, ?, ?)", list_items)

        game_db.commit()
