from api.util import SUPPORTED_GAMES
from api.game_databases import get_database_client
from api.config import Config

config = Config()

def get_questionmark_str(values):
    return ", ".join("?" for _ in values[0])

CREATE_TABLES = {
    "lol": """
        CREATE TABLE [participants] (
            [game_id] NVARCHAR(64) NOT NULL,
            [player_id] NVARCHAR(64) NOT NULL,
            [kills] INTEGER,
            [deaths] INTEGER,
            [assists] INTEGER,
            [doinks] NVARCHAR(10),
            [kda] REAL,
            [kp] INTEGER,
            [champ_id] INTEGER NOT NULL,
            [damage] INTEGER,
            [cs] INTEGER,
            [cs_per_min] REAL,
            [gold] INTEGER,
            [vision_wards] INTEGER,
            [vision_score] INTEGER,
            [steals] INTEGER,
            [role] NVARCHAR(20),
            [rank_solo] NVARCHAR(32),
            [rank_flex] NVARCHAR(32),
            PRIMARY KEY (game_id, player_id)
        );
    """,
    "cs2": """
        CREATE TABLE [participants] (
            [game_id] NVARCHAR(64) NOT NULL,
            [player_id] INTEGER NOT NULL,
            [kills] INTEGER,
            [deaths] INTEGER,
            [assists] INTEGER,
            [doinks] NVARCHAR(10),
            [kda] REAL,
            [kp] INTEGER,
            [mvps] INTEGER,
            [score] INTEGER,
            [headshot_pct] INTEGER,
            [adr] INTEGER,
            [utility_damage] INTEGER,
            [enemies_flashed] INTEGER,
            [teammates_flashed] INTEGER,
            [flash_assists] INTEGER,
            [team_kills] INTEGER,
            [suicides] INTEGER,
            [accuracy] INTEGER,
            [entries] INTEGER,
            [triples] INTEGER,
            [quads] INTEGER,
            [aces] INTEGER,
            [one_v_ones_tried] INTEGER,
            [one_v_ones_won] INTEGER,
            [one_v_twos_tried] INTEGER,
            [one_v_twos_won] INTEGER,
            [one_v_threes_tried] INTEGER,
            [one_v_threes_won] INTEGER,
            [one_v_fours_tried] INTEGER,
            [one_v_fours_won] INTEGER,
            [one_v_fives_tried] INTEGER,
            [one_v_fives_won] INTEGER,
            [rank] INTEGER,
            PRIMARY KEY (game_id, player_id)
        );
    """,
    "csgo": """
        CREATE TABLE [participants] (
            [game_id] NVARCHAR(64) NOT NULL,
            [player_id] INTEGER NOT NULL,
            [kills] INTEGER,
            [deaths] INTEGER,
            [assists] INTEGER,
            [doinks] NVARCHAR(10),
            [kda] REAL,
            [kp] INTEGER,
            [mvps] INTEGER,
            [score] INTEGER,
            [headshot_pct] INTEGER,
            [adr] INTEGER,
            [utility_damage] INTEGER,
            [enemies_flashed] INTEGER,
            [teammates_flashed] INTEGER,
            [flash_assists] INTEGER,
            [team_kills] INTEGER,
            [suicides] INTEGER,
            [accuracy] INTEGER,
            [entries] INTEGER,
            [triples] INTEGER,
            [quads] INTEGER,
            [aces] INTEGER,
            [one_v_ones_tried] INTEGER,
            [one_v_ones_won] INTEGER,
            [one_v_twos_tried] INTEGER,
            [one_v_twos_won] INTEGER,
            [one_v_threes_tried] INTEGER,
            [one_v_threes_won] INTEGER,
            [one_v_fours_tried] INTEGER,
            [one_v_fours_won] INTEGER,
            [one_v_fives_tried] INTEGER,
            [one_v_fives_won] INTEGER,
            [rank] INTEGER,
            PRIMARY KEY (game_id, player_id)
        );
    """
}

for game in SUPPORTED_GAMES:
    with get_database_client(game, config).get_connection() as conn:
        participants = conn.cursor().execute(f"SELECT * FROM participants").fetchall()

        conn.cursor().execute("DROP TABLE participants")
        conn.commit()

        conn.cursor().execute(CREATE_TABLES[game])
        conn.commit()

        query = f"INSERT OR IGNORE INTO participants VALUES ({get_questionmark_str(participants)})"
        conn.cursor().executemany(query, participants)

    # for game in SUPPORTED_GAMES:
    #     if os.path.exists(f"{conf_2.database_folder}/{game}.db"):
    #         os.remove(f"{conf_2.database_folder}/{game}.db")

    #     game_database_1 = get_database_client(game, conf_1)
    #     game_database_2 = get_database_client(game, conf_2)

    #     with game_database_1.get_connection() as game_db_1:
    #         with game_database_2.get_connection() as game_db_2:
    #             game_users = game_db_1.cursor().execute(f"SELECT * FROM users").fetchall()
    #             query = f"INSERT OR IGNORE INTO users VALUES ({get_questionmark_str(game_users)})"
    #             game_db_2.cursor().executemany(query, game_users)

    #             games = game_db_1.cursor().execute(f"SELECT * FROM games").fetchall()
    #             query = f"INSERT OR IGNORE INTO games VALUES ({get_questionmark_str(games)})"
    #             game_db_2.cursor().executemany(query, games)

    #             participants = game_db_1.cursor().execute(f"SELECT * FROM participants").fetchall()        
    #             query = f"INSERT OR IGNORE INTO participants VALUES ({get_questionmark_str(participants)})"
    #             game_db_2.cursor().executemany(query, participants)

    #             bets = meta_db_1.cursor().execute("SELECT id, better_id, guild_id, game_id, timestamp, event_id, amount, game_duration, target, ticket, result, payout FROM bets WHERE game=?", (game,)).fetchall()
    #             if bets != []:
    #                 query = f"INSERT OR IGNORE INTO bets VALUES ({get_questionmark_str(bets)})"
    #                 game_db_2.cursor().executemany(query, bets)

    #             event_sounds = game_db_1.cursor().execute("SELECT * FROM event_sounds").fetchall()
    #             if event_sounds != []:
    #                 game_db_2.cursor().executemany(f"INSERT INTO event_sounds VALUES ({get_questionmark_str(event_sounds)})", event_sounds)

    #             missed_games = game_db_1.cursor().execute("SELECT * FROM missed_games").fetchall()
    #             if missed_games != []:
    #                 query = f"INSERT INTO missed_games VALUES ({get_questionmark_str(missed_games)})"
    #                 game_db_2.cursor().executemany(query, missed_games)

    #             if game == "lol":
    #                 champ_lists = game_db_1.cursor().execute("SELECT * FROM champ_lists").fetchall()
    #                 game_db_2.cursor().executemany("INSERT OR IGNORE INTO champ_lists(id, name, owner_id) VALUES(?, ?, ?)", champ_lists)

    #                 list_items = game_db_1.cursor().execute("SELECT * FROM list_items").fetchall()
    #                 game_db_2.cursor().executemany("INSERT OR IGNORE INTO list_items(id, champ_id, list_id) VALUES (?, ?, ?)", list_items)

    #         game_db_2.commit()
