import shutil
from api.config import Config
from api.meta_database import MetaDatabase

conf_1 = Config()
conf_2 = Config()
conf_2.database_folder = f"{conf_2.database_folder}/test"

shutil.copy(f"{conf_1.database_folder}/meta.db", f"{conf_2.database_folder}/meta.db")

meta_database_1 = MetaDatabase(conf_1)
meta_database_2 = MetaDatabase(conf_2)

with meta_database_1.get_connection() as meta_db_1:
    with meta_database_2.get_connection() as meta_db_2:
        meta_db_2.execute("ALTER TABLE users DROP COLUMN reports")
        meta_db_2.execute("CREATE TABLE commendations (disc_id INTEGER NOT NULL, type NVARCHAR NOT NULL, commender INTEGER)")

        # reports_to_insert = []
        # for disc_id, reports in meta_db_1.execute("SELECT disc_id, reports FROM users"):
        #     for r in range(reports):
        #         reports_to_insert.append((disc_id, "report"))

        # meta_db_2.executemany("INSERT INTO commendations (disc_id, type) VALUES (?, ?)", reports_to_insert)
        meta_db_2.commit()
