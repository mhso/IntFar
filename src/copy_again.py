import os
from api.meta_database import MetaDatabase
from api.util import SUPPORTED_GAMES
SUPPORTED_GAMES["csgo"] = "Counter Strike: Global Offensive"
from api.game_databases import get_database_client
from api.config import Config
from api.game_apis.lol import RiotAPIClient

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
        query = f"INSERT OR IGNORE INTO betting_balance VALUES ({get_questionmark_str(balances)})"
        meta_db_2.cursor().executemany(query, balances)

        shop_items = meta_db_1.cursor().execute("SELECT * FROM shop_items").fetchall()
        query = f"INSERT INTO shop_items VALUES ({get_questionmark_str(shop_items)})"
        meta_db_2.cursor().executemany(query, shop_items)

        owned_items = meta_db_1.cursor().execute("SELECT * FROM owned_items").fetchall()
        query = f"INSERT INTO owned_items VALUES ({get_questionmark_str(owned_items)})"
        meta_db_2.cursor().executemany(query, owned_items)

        meta_db_2.commit()

    for game in SUPPORTED_GAMES:
        if os.path.exists(f"{conf_2.database_folder}/{game}.db"):
            os.remove(f"{conf_2.database_folder}/{game}.db")

        game_database_1 = get_database_client(game, conf_1)
        game_database_2 = get_database_client(game, conf_2)

        with game_database_1.get_connection() as game_db_1:
            with game_database_2.get_connection() as game_db_2:
                game_users = game_db_1.cursor().execute(f"SELECT * FROM users").fetchall()
                query = f"INSERT OR IGNORE INTO users VALUES ({get_questionmark_str(game_users)})"
                game_db_2.cursor().executemany(query, game_users)

                games = game_db_1.cursor().execute(f"SELECT * FROM games").fetchall()
                query = f"INSERT OR IGNORE INTO games VALUES ({get_questionmark_str(games)})"
                game_db_2.cursor().executemany(query, games)

                participants = game_db_1.cursor().execute(f"SELECT * FROM participants").fetchall()        
                query = f"INSERT OR IGNORE INTO participants VALUES ({get_questionmark_str(participants)})"
                game_db_2.cursor().executemany(query, participants)

                bets = meta_db_1.cursor().execute("SELECT id, better_id, guild_id, game_id, timestamp, event_id, amount, game_duration, target, ticket, result, payout FROM bets WHERE game=?", (game,)).fetchall()
                if bets != []:
                    query = f"INSERT OR IGNORE INTO bets VALUES ({get_questionmark_str(bets)})"
                    game_db_2.cursor().executemany(query, bets)

                event_sounds = game_db_1.cursor().execute("SELECT * FROM event_sounds").fetchall()
                if event_sounds != []:
                    game_db_2.cursor().executemany(f"INSERT INTO event_sounds VALUES ({get_questionmark_str(event_sounds)})", event_sounds)

                missed_games = game_db_1.cursor().execute("SELECT * FROM missed_games").fetchall()
                if missed_games != []:
                    query = f"INSERT INTO missed_games VALUES ({get_questionmark_str(missed_games)})"
                    game_db_2.cursor().executemany(query, missed_games)

                if game == "lol":
                    champ_lists = game_db_1.cursor().execute("SELECT * FROM champ_lists").fetchall()
                    game_db_2.cursor().executemany("INSERT OR IGNORE INTO champ_lists(id, name, owner_id) VALUES(?, ?, ?)", champ_lists)

                    list_items = game_db_1.cursor().execute("SELECT * FROM list_items").fetchall()
                    game_db_2.cursor().executemany("INSERT OR IGNORE INTO list_items(id, champ_id, list_id) VALUES (?, ?, ?)", list_items)

            game_db_2.commit()
