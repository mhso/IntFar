from datetime import datetime
import pickle
from typing import Literal

from dateutil.relativedelta import relativedelta
from mhooge_flask.database import SQLiteDatabase

from intfar.api.user import User
from intfar.api.config import Config
from intfar.api.util import generate_user_secret

DEFAULT_GAME = "lol"

class MetaDatabase(SQLiteDatabase):
    def __init__(self, config: Config):
        database = f"{config.database_folder}/meta.db"
        schema = f"{config.schema_folder}/meta.sql"
        super().__init__(database, schema, False)
        self.config = config

        self.all_users = self.get_base_users()

    def get_base_users(self):
        query = """
            SELECT
                u.disc_id,
                u.secret,
                dg.game
            FROM users AS u
            LEFT JOIN default_game AS dg
            ON dg.disc_id = u.disc_id
        """
        with self:
            return {x[0]: User(x[0], x[1], default_game=x[2] or DEFAULT_GAME) for x in self.execute_query(query).fetchall()}

    def user_exists(self, discord_id):
        return discord_id in self.all_users

    def add_user(self, discord_id):
        if self.user_exists(discord_id):
            return

        with self:
            query = "INSERT INTO users(disc_id, secret) VALUES (?, ?)"
            secret = generate_user_secret()
            self.execute_query(query, discord_id, secret, commit=False)

            query = "INSERT INTO betting_balance VALUES (?, ?)"
            self.execute_query(query, discord_id, 100)

            self.all_users[discord_id] = User(discord_id, secret)

    def get_client_secret(self, disc_id):
        query = "SELECT secret FROM users WHERE disc_id=?"

        with self:
            return self.execute_query(query, disc_id).fetchone()[0]

    def get_user_from_secret(self, secret):
        query = "SELECT disc_id FROM users WHERE secret=?"

        with self:
            result = self.execute_query(query, secret).fetchone()
            return result[0] if result is not None else None

    def set_default_game(self, disc_id, game):
        with self:
            self.all_users[disc_id]["default_game"] = game
            self.all_users[disc_id].default_game = game

            query = "REPLACE INTO default_game VALUES (?, ?)"
            self.execute_query(query, disc_id, game)

    def add_sound(self, sound, owner_id, timestamp):
        query = "INSERT INTO sounds (sound, owner_id, timestamp) VALUES (?, ?, ?)"
        with self:
            self.execute_query(query, sound, owner_id, timestamp)

    def remove_sound(self, sound):
        query_sound = "DELETE FROM sounds WHERE sound = ?"
        query_hits = "DELETE FROM sound_hits WHERE sound = ?"
        with self:
            self.execute_query(query_sound, sound, commit=False)
            self.execute_query(query_hits, sound)

    def get_weekly_timestamp(self, timestamp: datetime, week_offset: int = 1):
        days = timestamp.weekday()
        end_date = timestamp - relativedelta(days=days, hour=0, minute=0, second=0)

        if week_offset == 0:
            start_date = end_date
            days = 7 - timestamp.weekday()
            end_date = timestamp + relativedelta(days=days, hour=0, minute=0, second=0)
        else:
            start_date = end_date
            for _ in range(week_offset):
                end_date = start_date
                start_date = end_date - relativedelta(days=7)

        return int(start_date.timestamp()), int(end_date.timestamp())

    def add_sound_hit(self, sound: str, timestamp: datetime = None):
        if timestamp is None:
            timestamp = datetime.now()

        date_start, date_end = self.get_weekly_timestamp(timestamp, 0)
        with self:
            query_select = "SELECT plays FROM sound_hits WHERE sound = ? AND start_date = ? AND end_date = ?"

            result = self.execute_query(query_select, sound, date_start, date_end).fetchone()

            if result is None or result[0] is None:
                query = """
                    INSERT INTO sound_hits (sound, start_date, end_date, plays)
                    VALUES (?, ?, ?, 1)
                """
            else:
                query = """
                    UPDATE sound_hits
                    SET plays = plays + 1
                    WHERE sound = ? AND start_date = ? AND end_date = ?
                """
    
            self.execute_query(query, sound, date_start, date_end)

    def get_sounds(self, ordering):
        order_by = "sounds.sound ASC"
        if ordering == "newest":
            order_by = "sounds.timestamp DESC"
        elif ordering == "oldest":
            order_by = "sounds.timestamp ASC"
        elif ordering == "most_played":
            order_by = "total_plays DESC"
        elif ordering == "least_played":
            order_by = "total_plays ASC"

        query = f"""
            SELECT
                sounds.sound,
                owner_id,
                COALESCE(SUM(plays), 0) AS total_plays,
                timestamp
            FROM sounds
            LEFT JOIN sound_hits
            ON sound_hits.sound = sounds.sound
            GROUP BY sounds.sound
            ORDER BY {order_by}
        """
        with self:
            return self.execute_query(query).fetchall()

    def get_sound_owner(self, sound: str):
        query = "SELECT owner_id FROM sounds WHERE sound = ?"
        with self:
            return self.execute_query(query, sound).fetchone() is not None

    def is_valid_sound(self, sound: str):
        query = "SELECT sound FROM sounds WHERE sound = ?"
        with self:
            return self.execute_query(query, sound).fetchone() is not None

    def get_sound_hits(self, sound=None, date_from: int = None, date_to: int = None):
        query = "SELECT "
        params = []
        if sound is None:
            query += "sound, "

        query += "plays FROM sound_hits "
        if date_from is not None:
            query += "WHERE start_date >= ? "
            params.append(date_from)

        if date_to is not None:
            query += f"{'AND' if date_from else 'WHERE'} end_date <= ? "
            params.append(date_to)

        if sound is not None:
            query += f"{'AND' if date_to else 'WHERE'} sound = ? "
            params.append(sound)

        def format_result(cursor):
            return cursor.fetchone() if sound is not None else cursor.fetchall()

        return self.query(query, *params, format_func=format_result)

    def get_weekly_sound_hits(self, date_start, date_end, sound=None):
        query_week = f"""
            WITH hits AS (
                {self.get_sound_hits(sound, date_start, date_end).query}
            )
            SELECT
                hits.sound,
                hits.plays,
                ROW_NUMBER() OVER (ORDER BY hits.plays DESC) AS rank
            FROM hits
        """

        params = [date_start, date_end]
        if sound is not None:
            params.append(sound)

        with self:
            return self.execute_query(query_week, *params).fetchall()

    def get_total_sound_hits(self, sound=None):
        query = "SELECT "
        if sound is None:
            query += "sound, "

        params = []
        query += "SUM(plays) FROM sound_hits GROUP BY sound"
        if sound is not None:
            query += f"WHERE sound = ?"
            params.append(sound)

        def format_result(cursor):
            return cursor.fetchone() if sound is not None else cursor.fetchall()

        return self.query(query, *params, format_func=format_result)

    def get_join_sound(self, disc_id):
        query = "SELECT sound FROM join_sounds WHERE disc_id=?"

        with self:
            result = self.execute_query(query, disc_id).fetchone()

            return result[0] if result is not None else None

    def set_join_sound(self, disc_id, sound):
        query = "REPLACE INTO join_sounds(disc_id, sound) VALUES (?, ?)"

        with self:
            self.execute_query(query, disc_id, sound)

    def remove_join_sound(self, disc_id):
        query = "DELETE FROM join_sounds WHERE disc_id=?"

        with self:
            self.execute_query( query, disc_id)

    def get_token_balance(self, disc_id=None):
        with self:
            query = "SELECT tokens"
            if disc_id is None:
                query += ", disc_id"

            query += " FROM betting_balance "

            params = []
            if disc_id is not None:
                query += "WHERE disc_id=? "
                params.append(disc_id)

            query += "GROUP BY disc_id ORDER BY tokens DESC"

            data = self.execute_query(query, *params).fetchall()

            return data if disc_id is None else data[0][0]

    def get_max_tokens_details(self):
        with self:
            query = """
                SELECT
                    MAX(tokens),
                    disc_id
                FROM betting_balance
            """
            return self.execute_query(query).fetchone()

    def update_token_balance(self, disc_id, amount, increment=True):
        with self:
            sign_str = "+" if increment else "-"
            query = f"UPDATE betting_balance SET tokens=tokens{sign_str}? WHERE disc_id=?"
            self.execute_query(query, amount, disc_id)

    def give_tokens(self, sender, amount, receiver):
        self.update_token_balance(sender, amount, increment=False)
        self.update_token_balance(receiver, amount, increment=True)

    def get_commendations(
        self,
        commend_type: Literal["report", "honor"],
        commended: int | None = None,
        commender: int | None = None
    ):
        query_select = """
            SELECT
                disc_id,
                COUNT(*) AS c,
                commender
            FROM commendations
            WHERE type = ?
        """

        with self:
            params = [commend_type]

            if commended is not None:
                query_select += "AND disc_id = ? "
                params.append(commended)

            if commender is not None:
                query_select += "AND commender = ? "
                params.append(commender)

            if commended is None or commender is None:
                query_select += "GROUP BY"
                if commended is None:
                    query_select += " disc_id"
                if commender is None:
                    if commended is None:
                        query_select += ","
                    query_select += " commender"

            query_select += " ORDER BY c DESC"

            return self.execute_query(query_select, *params).fetchall()

    def get_max_commendation_details(self, commend_type: Literal["report", "honor"]):
        query = """
            SELECT
                MAX(sub.c),
                sub.disc_id
            FROM (
                SELECT
                    disc_id,
                    COUNT(*) AS c
                FROM commendations
                WHERE type = ?
                GROUP BY disc_id
            ) sub
        """

        with self:
            return self.execute_query(query, commend_type).fetchone()

    def commend_user(self, commend_type: Literal["report", "honor"], disc_id: int, commender: int):
        query_update = """
            INSERT INTO commendations
            VALUES (?, ?, ?)
        """

        with self:
            self.execute_query(query_update, disc_id, commend_type, commender)
            total_reports = sum(x[1] for x in self.get_commendations(commend_type, disc_id))
            reports_by_commender = self.get_commendations(commend_type, disc_id, commender)[0][1]

            return total_reports, reports_by_commender

    def add_items_to_shop(self, item_tuples):
        query = "INSERT INTO shop_items(name, price) VALUES (?, ?)"

        with self:
            self.execute_query(query, *item_tuples)

    def get_item_by_name(self, item_name, event):
        table = "shop_items" if event in ("buy", "cancel") else "owned_items"
        fmt_name = f"%{item_name.lower()}%"
        query = f"SELECT DISTINCT(name) FROM {table} WHERE name LIKE ?"

        with self:
            return self.execute_query(query, fmt_name).fetchall()

    def get_items_for_user(self, disc_id):
        query = """
            SELECT
                name,
                COUNT(*)
            FROM owned_items
            WHERE owner_id=?
            GROUP BY name
        """

        with self:
            return self.execute_query(query, disc_id).fetchall()

    def get_items_in_shop(self):
        query = """
            SELECT
                name,
                price,
                COUNT(*)
            FROM shop_items
            GROUP BY
                name,
                price
            ORDER BY price DESC
        """

        with self:
            return self.execute_query(query).fetchall()

    def get_items_matching_price(self, item_name, price, quantity, seller_id=None):
        with self:
            if price is None: # Select the 'quantity' amounts of cheapest items.
                query_price = "SELECT id, price, seller_id FROM shop_items WHERE name=? "
                params = [item_name]
            else: # Select the 'quantity' amounts of items matching 'price'.
                query_price = "SELECT id, price, seller_id FROM shop_items WHERE name=? AND price=? "
                params = [item_name, price]

            if seller_id is not None:
                query_price += "AND seller_id=? "
                params.append(seller_id)

            query_price += "ORDER BY price ASC LIMIT ?"
            params.append(quantity)

            return self.execute_query(query_price, *params).fetchall()

    def buy_item(self, disc_id, item_copies, total_price, item_name):
        with self:
            for _, price, seller_id in item_copies: # Add items to user's inventory.
                query_insert = "INSERT INTO owned_items(name, owner_id) VALUES(?, ?)"
                self.execute_query(query_insert, item_name, disc_id, commit=False)

                # Add payment of item to seller.
                query_update = "UPDATE betting_balance SET tokens=tokens+? WHERE disc_id=?"
                self.execute_query(query_update, price, seller_id, commit=False)

            # Subtract the tokens spent from the user's balance.
            query_update = "UPDATE betting_balance SET tokens=tokens-? WHERE disc_id=?"
            self.execute_query(query_update, total_price, disc_id, commit=False)

            for item in item_copies: # Delete from shop.
                query_delete = "DELETE FROM shop_items WHERE id=?"
                self.execute_query(query_delete, item[0], commit=False)

            self.connection.commit()

    def get_matching_items_for_user(self, disc_id, item_name, quantity):
        with self:
            query_items = """
                SELECT id
                FROM owned_items
                WHERE
                    owner_id=?
                    AND name=?
                LIMIT ?
            """
            return self.execute_query(query_items, disc_id, item_name, quantity).fetchall()

    def sell_item(self, disc_id, item_copies, item_name, price):
        with self:
            query_insert = "INSERT INTO shop_items(name, price, seller_id) VALUES (?, ?, ?)"
            params_insert = [(item_name, price, disc_id) for _ in item_copies]
            self.execute_query(query_insert, *params_insert)

            query_delete = "DELETE FROM owned_items WHERE id=?"
            params_delete = [(item_data[0],) for item_data in item_copies]
            self.execute_query(query_delete, *params_delete)

    def cancel_listings(self, item_ids, item_name, disc_id):
        with self:
            query_insert = "INSERT INTO owned_items(name, owner_id) VALUES (?, ?)"
            params_insert = [(item_name, disc_id) for _ in item_ids]
            self.execute_query(query_insert, *params_insert)

            query_delete = "DELETE FROM shop_items WHERE id=?"
            params_delete = [(item_id,) for item_id in item_ids]
            self.execute_query(query_delete, *params_delete)

    def reset_shop(self):
        with self:
            query_items = "DELETE FROM owned_items"
            self.execute_query(query_items)

            query_balance = "UPDATE betting_balance SET tokens=100"
            self.execute_query(query_balance)

    def get_best_comps(self, participants):
        join_str = "\n".join(
            f"INNER JOIN participants p{i}\nON p{i}.game_id = p{i-1}.game_id"
            for i in range(2, 6)
        )

        where_str = "\nAND ".join(
            f"p{i}.disc_id = {disc_id}"
            for i, disc_id in enumerate(participants, start=1)
        )

        query = f"""
            SELECT
                g.win,
                p1.champ_id,
                p2.champ_id,
                p3.champ_id,
                p4.champ_id,
                p5.champ_id
            FROM participants p1
            {join_str}
            INNER JOIN games g
            ON g.game_id = p1.game_id
            WHERE {where_str}
        """

        with self:
            return self.execute_query(query).fetchall()

    def get_command_result(self, cmd_id, target):
        with self:
            query = "SELECT result, IIF(result IS NULL, 0, 1) FROM command_queue WHERE id=? AND target=?"
            result = self.execute_query(query, cmd_id, target).fetchone()

            done = result is not None and result[1] == 1

            if done:
                result = pickle.loads(result[0])
                query_delete = "DELETE FROM command_queue WHERE id=? AND target=?"
                self.execute_query(query_delete, cmd_id, target)
            else:
                result = None

            return result, done

    def set_command_result(self, cmd_id, target, result):
        with self:
            query = "UPDATE command_queue SET result=? WHERE id=? AND target=?"
            self.execute_query(query, pickle.dumps(result), cmd_id, target)

    def get_queued_commands(self, target):
        with self:
            query = "SELECT id, command, arguments FROM command_queue WHERE target=? AND result IS NULL"
            commands = [
                (command_id, command, pickle.loads(args))
                for command_id, command, args in self.execute_query(query, target)
            ]

            return commands

    def enqueue_command(self, cmd_id, target, command, *arguments):
        with self:
            query = "INSERT INTO command_queue(id, target, command, arguments) VALUES (?, ?, ?, ?)"
            serialized_args = pickle.dumps(list(arguments))

            self.execute_query(query, cmd_id, target, command, serialized_args)

    def clear_command_queue(self):
        with self:
            self.execute_query("DELETE FROM command_queue")

    def clear_tables(self):
        with self:
            query_tables = "SELECT name FROM sqlite_master WHERE type='table'"
            tables = self.execute_query(query_tables).fetchall()

            for table in tables:
                query = f"DELETE FROM {table[0]}"
                self.execute_query(query, commit=False)

            self.connection.commit()
