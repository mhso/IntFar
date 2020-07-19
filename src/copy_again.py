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

MISSING_DATA = [
    (4699244357, [267401734513491969, 347489125877809155], 1594302808),
    (4699431747, [267401734513491969, 347489125877809155], 1594311660),
    (4700352835, [267401734513491969, 115142485579137029], 1594336522),
    (4700852765, [267401734513491969, 115142485579137029], 1594387154),
    (4700945429, [267401734513491969, 115142485579137029], 4700945429),
    (4700957091, [267401734513491969, 331082926475182081], 1594393569),
    (4701065219, [267401734513491969, 331082926475182081], 1594397255),
    (4701070701, [267401734513491969, 331082926475182081], 1594395443),
    (4701224965, [267401734513491969, 331082926475182081], 1594401471),
    (4703085411, [115142485579137029, 172757468814770176], 1594496508),
    (4703181863, [115142485579137029, 172757468814770176], 1594498880),
    (4703179211, [115142485579137029, 172757468814770176], 1594501873),
    (4704366761, [267401734513491969, 115142485579137029, 172757468814770176, 331082926475182081, 255425791276482572], 1594580323),
    (4704416984, [267401734513491969, 115142485579137029, 172757468814770176, 331082926475182081, 255425791276482572], 1594582891),
    (4705933274, [267401734513491969, 115142485579137029, 331082926475182081], 1594657583),
    (4705987732, [267401734513491969, 115142485579137029, 331082926475182081], 1594663936),
    (4707697313, [267401734513491969, 115142485579137029, 172757468814770176, 331082926475182081, 219497453374668815], 1594758376),
    (4707904607, [267401734513491969, 115142485579137029, 172757468814770176, 331082926475182081, 219497453374668815], 1594760242),
    (4707900399, [267401734513491969, 115142485579137029, 172757468814770176, 331082926475182081], 1594762485),
    (4708067752, [267401734513491969, 115142485579137029, 331082926475182081], 1594765126),
    (4709377775, [267401734513491969, 115142485579137029, 331082926475182081], 1594845393),
    (4709464241, [267401734513491969, 115142485579137029, 331082926475182081], 1594848293),
    (4709591924, [267401734513491969, 115142485579137029, 331082926475182081], 1594851448),
    (4711750347, [267401734513491969, 115142485579137029, 331082926475182081], 1594987242),
    (4711750347, [267401734513491969, 115142485579137029, 331082926475182081], 1594989522)
]

with closing(database_client_1.get_connection()) as db_1:
    data_best = db_1.cursor().execute("SELECT * FROM best_stats").fetchall()
    data_worst = db_1.cursor().execute("SELECT * FROM worst_stats").fetchall()
    summoners = db_1.cursor().execute("SELECT * FROM registered_summoners").fetchall()

    query_prefix = "INSERT INTO "
    query_cols = (
        """
        (id, game_id, int_far, intfar_reason, kills, kills_id, deaths,
        deaths_id, kda, kda_id, damage, damage_id, cs, cs_id, gold, gold_id,
        kp, kp_id, vision_wards, vision_wards_id, vision_score, vision_score_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
    )

    with closing(database_client_2.get_connection()) as db_2:
        for summ in summoners:
            disc_id = int(summ[0])
            db_2.cursor().execute("INSERT INTO registered_summoners VALUES (?, ?, ?)", (disc_id, summ[1], summ[2]))
        query = query_prefix + "best_stats" + query_cols
        for data in data_best:
            db_2.cursor().execute(query, data)
        query = query_prefix + "worst_stats" + query_cols
        for data in data_worst:
            db_2.cursor().execute(query, data)
        query = "INSERT INTO participants(game_id, disc_id, timestamp) VALUES (?, ?, ?)"
        for game_id, participants, timestamp in MISSING_DATA:
            for disc_id in participants:
                db_2.cursor().execute(query, (game_id, disc_id, timestamp))
        db_2.commit()
