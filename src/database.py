import os
import sqlite3
from contextlib import closing

class Database:
    def __init__(self, config):
        self.config = config
        self.summoners = []
        if not os.path.exists(self.config.database):
            self.create_database()

        # Populate summoner names and ids lists with currently registered summoners.
        with closing(self.get_connection()) as db:
            users = db.cursor().execute("SELECT * FROM registered_summoners").fetchall()
            for entry in users:
                disc_id = int(entry[0])
                self.summoners.append((disc_id, entry[1], entry[2]))

    def get_connection(self):
        return sqlite3.connect(self.config.database)

    def create_database(self):
        with closing(self.get_connection()) as db:
            with open("schema.sql", "r") as f:
                db.cursor().executescript(f.read())
            db.commit()

    def get_registered_user(self, summ_name):
        with closing(self.get_connection()) as db:
            user = db.cursor().execute("SELECT * FROM registered_summoners " +
                                       "WHERE summ_name=?", (summ_name,)).fetchone()
            return user

    def add_user(self, summ_name, summ_id, discord_id):
        self.summoners.append((summ_name, summ_id, discord_id))
        with closing(self.get_connection()) as db:
            db.cursor().execute("INSERT INTO registered_summoners(disc_id, summ_name, summ_id) " +
                                "VALUES (?, ?, ?)", (discord_id, summ_name, summ_id))
            db.commit()

    def summoner_from_discord_id(self, discord_id):
        for disc_id, summ_name, summ_id in self.summoners:
            if disc_id == discord_id:
                return disc_id, summ_name, summ_id
        return None
