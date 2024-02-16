from sqlite3 import DatabaseError

from mhooge_flask.database import SQLiteDatabase

from api.user import User
from api.config import Config
from api.util import generate_user_secret

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
            query = "INSERT INTO users(disc_id, secret, reports) VALUES (?, ?, ?)"
            secret = generate_user_secret()
            self.execute_query(query, discord_id, secret, 0, commit=False)

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
            return self.execute_query(query, secret).fetchone()[0]

    def set_default_game(self, disc_id, game):
        with self:
            self.all_users[disc_id]["default_game"] = game
            self.all_users[disc_id].default_game = game

            query = "REPLACE INTO default_game VALUES (?, ?)"
            self.execute_query(query, disc_id, game)

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

    def get_reports(self, disc_id=None):
        query_select = """
            SELECT
                disc_id,
                reports
            FROM users
        """

        with self:
            params = []

            if disc_id is not None:
                query_select += "WHERE disc_id = ? "
                params = [disc_id]
            else:
                query_select += "GROUP BY disc_id "

            query_select += "ORDER BY reports DESC"

            return self.execute_query(query_select, *params).fetchall()

    def get_max_reports_details(self):
        query = """
            SELECT
                MAX(reports),
                disc_id
            FROM users
        """

        with self:
            return self.execute_query(query).fetchone()

    def report_user(self, disc_id):
        query_update = """
            UPDATE
                users
            SET reports = reports + 1
            WHERE disc_id = ?
        """

        with self:
            self.execute_query(query_update, disc_id)
            return self.get_reports(disc_id)[0][1]

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
            query = "SELECT result FROM command_queue WHERE id=? AND target=?"
            result = self.execute_query(query, cmd_id, target).fetchone()

            if result is not None and result[0] is not None:
                query_delete = "DELETE FROM command_queue WHERE id=? AND target=?"
                self.execute_query(query_delete, cmd_id, target)

            return None if result is None else result[0]

    def set_command_result(self, cmd_id, target, result):
        with self:
            query = "UPDATE command_queue SET result=? WHERE id=? AND target=?"
            self.execute_query(query, result, cmd_id, target)

    def get_queued_commands(self, target):
        with self:
            query = "SELECT id, command, arguments FROM command_queue WHERE target=? AND result IS NULL"

            return self.execute_query(query, target).fetchall()

    def enqueue_command(self, cmd_id, target, command, *arguments):
        with self:
            query = "INSERT INTO command_queue(id, target, command, arguments) VALUES (?, ?, ?, ?)"
            argument_str = ",".join(str(arg) for arg in arguments)

            self.execute_query(query, cmd_id, target, command, argument_str)

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
