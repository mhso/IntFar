from api.game_database import GameDatabase
from api.config import Config
from sqlite3 import Cursor, IntegrityError

class LoLGameDatabase(GameDatabase):
    def __init__(self, game: str, config: Config):
        super().__init__(game, config)

    @property
    def game_user_params(self):
        return ["puuid"]

    def get_played_count_for_stat(self, stat, maximize, disc_id):
        aggregator = "MAX" if maximize else "MIN"

        query = f"""
            SELECT
                sub2.champ_id,
                MAX(c)
            FROM (
                SELECT
                    sub.champ_id,
                    COUNT(*) AS c
                FROM (
                    SELECT
                        {aggregator}({stat}) AS c,
                        p.champ_id,
                        p.disc_id
                    FROM participants AS p
                    INNER JOIN games AS g
                    ON g.game_id = p.game_id
                    INNER JOIN users AS u
                    ON u.disc_id = p.disc_id
                    WHERE u.active = 1
                    GROUP BY p.game_id
                ) sub
                WHERE disc_id = ?
                GROUP BY champ_id
            ) sub2
        """

        with self:
            return self.execute_query(query, disc_id).fetchone()

    def get_average_stat(self, stat, disc_id=None, champ_id=None, min_games=10):
        params = []
        player_condition = ""
        champ_condition = ""

        if champ_id is not None:
            params = [champ_id] * 2
            champ_condition = "WHERE p.champ_id=?"

        if disc_id is not None:
            params.append(disc_id)
            player_condition = "AND played.disc_id=?"

        if stat == "first_blood":
            query = f"""
                SELECT
                    played.disc_id,
                    first_bloods.c / played.c AS avg_val,
                    CAST(played.c AS int)
                FROM (
                    SELECT
                        g.first_blood,
                        CAST(COUNT(DISTINCT g.game_id) as REAL) AS c
                    FROM games AS g
                    INNER JOIN participants AS p
                        ON p.game_id = g.game_id
                        AND p.disc_id = g.first_blood
                    {champ_condition}
                    GROUP BY g.first_blood
                ) first_bloods
                INNER JOIN
                (
                    SELECT
                        p.disc_id,
                        CAST(COUNT(DISTINCT g.game_id) as REAL) AS c
                    FROM games AS g
                    LEFT JOIN participants AS p
                        ON g.game_id = p.game_id
                    {champ_condition}
                    GROUP BY p.disc_id
                ) played
                    ON played.disc_id = first_bloods.first_blood
                INNER JOIN users AS u
                    ON u.disc_id = played.disc_id
                WHERE u.active = 1
                    AND played.c >= {min_games}
                    {player_condition}
                GROUP BY played.disc_id
                ORDER BY avg_val DESC
            """

        else:
            query = f"""
                SELECT
                    played.disc_id,
                    stat_values.s / played.c AS avg_val,
                    CAST(played.c AS int)
                FROM (
                    SELECT
                        disc_id,
                        SUM({stat}) AS s
                    FROM participants AS p
                    {champ_condition}
                    GROUP BY p.disc_id
                ) stat_values
                INNER JOIN (
                    SELECT
                        disc_id,
                        CAST(COUNT(DISTINCT g.game_id) as real) AS c
                    FROM games AS g
                    LEFT JOIN participants AS p
                        ON g.game_id = p.game_id
                    {champ_condition}
                    GROUP BY p.disc_id
                ) played
                ON played.disc_id = stat_values.disc_id
                INNER JOIN users AS u
                ON u.disc_id = played.disc_id
                WHERE u.active = 1
                    AND played.c >= {min_games}
                {player_condition}
                GROUP BY played.disc_id
                ORDER BY avg_val DESC
            """

        def format_result(cursor: Cursor):
            result = cursor.fetchall()
            return result or [(disc_id, None, None)]

        return self.query(query, *params, format_func=format_result)

    def get_played_with_most_doinks(self, disc_id):
        query = f"""
            SELECT sub.champ_id, MAX(sub.c) FROM (
                SELECT
                    COUNT(DISTINCT p.game_id) AS c,
                    champ_id
                FROM participants AS p
                WHERE
                    p.disc_id=?
                    AND p.doinks IS NOT NULL
                GROUP BY champ_id
            ) sub
        """

        with self:
            return self.execute_query(query, disc_id).fetchone()

    def get_played_with_most_intfars(self, disc_id):
        query = """
            SELECT sub.champ_id, MAX(sub.c) FROM (
                SELECT
                    COUNT(DISTINCT p.game_id) AS c,
                    champ_id
                FROM games AS g
                JOIN participants AS p
                ON p.game_id = g.game_id
                    AND g.intfar_id = p.disc_id
                WHERE
                    g.intfar_id IS NOT NULL
                    AND g.intfar_id = ?
                GROUP BY champ_id
            ) sub
        """

        with self:
            return self.execute_query(query, disc_id).fetchone()

    def get_played_ids(self, disc_id=None, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "disc_id", disc_id)

        query = f"""
            SELECT DISTINCT champ_id
            FROM participants AS p
            JOIN games AS g
                ON p.game_id = g.game_id
                {delim_str}
        """

        with self:
            return self.execute_query(query, *params).fetchall()

    def get_played_winrate(self, disc_id, champ_id):
        query = f"""
            SELECT
                (wins.c / played.c) * 100 AS wr,
                played.c AS gs
            FROM (
                SELECT
                    CAST(COALESCE(COUNT(DISTINCT g.game_id), 0) as real) AS c,
                    champ_id
                FROM games AS g
                LEFT JOIN participants AS p
                    ON g.game_id = p.game_id
                WHERE
                    disc_id = ?
                    AND champ_id = ?
                    AND win = 1
            ) wins,
            (
                SELECT
                    CAST(COUNT(DISTINCT g.game_id) as real) AS c,
                    champ_id
                FROM games AS g
                LEFT JOIN participants AS p
                    ON g.game_id = p.game_id
                WHERE
                    disc_id = ?
                    AND champ_id = ?
            ) played
            WHERE wins.champ_id = played.champ_id OR wins.champ_id IS NULL
        """

        with self:
            params = [disc_id, champ_id] * 2
            return self.execute_query(query, *params).fetchone()

    def get_min_or_max_winrate_played(self, disc_id, best, included_champs=None, return_top_n=1, min_games=10):
        sort_order = "DESC" if best else "ASC"
        if included_champs is not None:
            champs_condition = (
                f"AND played.champ_id IN (" +
                ",\n".join(map(str, included_champs)) +
                ")"
            )
        else:
            champs_condition = ""

        query = f"""
            SELECT
                sub.wr,
                CAST(sub.gs as integer),
                sub.champ
            FROM (
                SELECT
                    (wins.c / played.c) * 100 AS wr,
                    played.c AS gs,
                    played.champ_id as champ
                FROM (
                    SELECT
                        CAST(COUNT(DISTINCT g.game_id) as real) AS c,
                        champ_id
                    FROM games AS g
                    LEFT JOIN participants AS p 
                        ON g.game_id = p.game_id
                    WHERE
                        disc_id = ?
                        AND win = 1
                    GROUP BY champ_id
                    ORDER BY champ_id
               ) wins,
               (
                SELECT
                    CAST(COUNT(DISTINCT g.game_id) as real) AS c,
                    champ_id
                FROM games AS g
                LEFT JOIN participants AS p
                    ON g.game_id = p.game_id
                WHERE disc_id = ?
                GROUP BY champ_id
                ORDER BY champ_id
               ) played
               WHERE
                    wins.champ_id = played.champ_id
                    AND played.c > {min_games}
                    {champs_condition}
            ) sub
            ORDER BY
                sub.wr {sort_order},
                sub.gs DESC
            LIMIT {return_top_n}
        """

        with self:
            params = [disc_id] * 2
            result = self.execute_query(query, *params).fetchall()

            if return_top_n == 1:
                result = result[0] if result != [] else None

            if result is None and min_games == 10:
                # If no champs are found with min 10 games, try again with 5.
                return self.get_min_or_max_winrate_played(disc_id, best, included_champs, return_top_n, min_games=5)

            return result

    def create_list(self, disc_id, name):
        query = "INSERT INTO champ_lists(name, owner_id) VALUES (?, ?)"

        with self:
            try:
                self.execute_query( query, name, disc_id)
                return True, self.execute_query("SELECT last_insert_rowid()").fetchone()[0]
            except IntegrityError: # Duplicate list inserted.
                return False, None

    def rename_list(self, list_id, new_name):
        query = "UPDATE champ_lists SET name=? WHERE id=?"

        with self:
            self.execute_query(query, new_name, list_id)

    def delete_list(self, list_id):
        with self:
            query = "DELETE FROM list_items WHERE list_id=?"
            self.execute_query(query, list_id)

            query = "DELETE FROM champ_lists WHERE id=?"
            self.execute_query(query, list_id)

    def get_lists(self, disc_id=None):
        query = """
            SELECT
                champ_lists.id,
                champ_lists.owner_id,
                name,
                COUNT(list_items.id)
            FROM champ_lists
            LEFT JOIN list_items
            ON champ_lists.id = list_id
        """

        params = []
        if disc_id is not None:
            query += "WHERE owner_id=? "
            params.append(disc_id)

        query += "GROUP BY champ_lists.id"

        with self:
            return self.execute_query(query, *params).fetchall()

    def get_list_by_name(self, name):
        query = "SELECT id FROM champ_lists WHERE LOWER(name)=?"

        with self:
            result = self.execute_query(query, name.lower()).fetchone()

            if result is None:
                return None, None

            list_id = result[0]

            return list_id, self.get_list_items(list_id)

    def get_list_data(self, list_id):
        query = "SELECT name, owner_id FROM champ_lists WHERE id=?"

        with self:
            return self.execute_query(query, list_id).fetchone()

    def get_list_from_item_id(self, item_id):
        query = "SELECT list_id FROM list_items WHERE id=?"

        with self:
            list_id = self.execute_query(query, item_id).fetchone()
            if list_id is None:
                return None

            list_data = self.get_list_data(list_id[0])
            if list_data is None:
                return None

            return list_id + list_data

    def add_item_to_list(self, champ_id, list_id):
        query = "INSERT INTO list_items(champ_id, list_id) VALUES (?, ?)"

        with self:
            try:
                self.execute_query(query, champ_id, list_id)
                return True
            except IntegrityError: # Duplicate champion inserted.
                return False

    def add_items_to_list(self, items):
        query = "INSERT INTO list_items(champ_id, list_id) VALUES (?, ?)"

        with self:
            try:
                self.execute_query(query, *items)
                return True
            except IntegrityError: # Duplicate champion inserted.
                return False

    def get_list_items(self, list_id):
        query = "SELECT id, champ_id FROM list_items WHERE list_id=?"

        with self:
            return self.execute_query(query, list_id).fetchall()

    def delete_item_from_list(self, item_id):
        query = "DELETE FROM list_items WHERE id=?"

        with self:
            self.execute_query(query, item_id)

    def delete_items_from_list(self, item_ids):
        query = "DELETE FROM list_items WHERE id=?"

        with self:
            self.execute_query(query, *item_ids)
