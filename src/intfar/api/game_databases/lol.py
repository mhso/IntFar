from datetime import datetime
from intfar.api.game_database import GameDatabase
from intfar.api.config import Config
from sqlite3 import IntegrityError
from intfar.api.game_data.lol import get_rank_value

class LoLGameDatabase(GameDatabase):
    def __init__(self, game: str, config: Config):
        super().__init__(game, config)

    def get_played_count(self, disc_id, playable_id):
        query = """
            SELECT COUNT(*)
            FROM participants AS p
            INNER JOIN users AS u
                ON u.player_id = p.player_id
            WHERE u.disc_id = ?
            AND p.champ_id = ?
        """

        with self:
            result = self.execute_query(query, disc_id, playable_id).fetchone()
            return result[0]

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
                        u.disc_id
                    FROM participants AS p
                    INNER JOIN games AS g
                    ON g.game_id = p.game_id
                    INNER JOIN users AS u
                    ON u.player_id = p.player_id
                    WHERE u.active = 1
                    GROUP BY p.game_id
                ) sub
                WHERE sub.disc_id = ?
                GROUP BY champ_id
            ) sub2
        """

        with self:
            return self.execute_query(query, disc_id).fetchone()

    def get_average_stat_rank(self, stat, disc_id, champ_id, comparison, role=None, min_games=10):
        parameters = []

        where_clause = ""
        group_clause = ""
        if comparison == 1: # Compare to other champs played by person
            where_clause = "WHERE u.disc_id=?"
            group_clause = "GROUP BY p.champ_id"
            parameters = [disc_id]
        elif comparison == 2: # Compare to other people playing the same champ
            where_clause = "WHERE p.champ_id=?"
            group_clause = "GROUP BY u.disc_id"
            parameters = [champ_id]
        elif comparison == 3: # Compare to all people across all champs
            group_clause = "GROUP BY u.disc_id, p.champ_id"

        if role is not None:
            where_clause = where_clause + f" AND p.role = ?" if where_clause else "WHERE p.role = ?"
            parameters.append(role)

        parameters = parameters * 2

        parameters.extend([disc_id, champ_id])
        ordering = "ASC" if stat == "deaths" else "DESC"

        query = f"""
            WITH ranking AS (
                SELECT
                    played.disc_id,
                    played.champ_id,
                    CAST(played.c AS int) AS games,
                    ROW_NUMBER() OVER (ORDER BY stat_values.s / played.c {ordering}) AS rank
                FROM (
                    SELECT
                        u.disc_id,
                        p.champ_id,
                        p.game_id,
                        SUM({stat}) AS s
                    FROM participants AS p
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    {where_clause}
                    {group_clause}
                ) stat_values
                INNER JOIN (
                    SELECT
                        u.disc_id,
                        p.champ_id,
                        CAST(COUNT(g.game_id) as real) AS c
                    FROM games AS g
                    LEFT JOIN participants AS p
                        ON g.game_id = p.game_id
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    {where_clause}
                    {group_clause}
                ) played
                ON played.champ_id = stat_values.champ_id
                    AND played.disc_id = stat_values.disc_id
                INNER JOIN users AS u
                ON u.disc_id = played.disc_id
                WHERE u.active = 1
                    AND played.c >= {min_games}
                GROUP BY
                    played.champ_id,
                    played.disc_id
            )
            SELECT rank, best_id, max_rank
            FROM (
                SELECT rank
                FROM ranking
                WHERE disc_id = ?
                    AND champ_id = ?
            ) sub_1,
            (
                SELECT MAX(rank) AS max_rank
                FROM ranking
            ) sub_2,
            (
                SELECT
                    disc_id AS best_id,
                    MIN(rank)
                FROM ranking
            )
            """

        return self.query(query, *parameters, format_func="one")

    def get_average_stat(self, stat, disc_id=None, played_id=None, role=None, min_games=10, time_after=None, time_before=None):
        champ_condition = ""
        role_condition = ""
        player_condition, params = self.get_delimeter(time_after, time_before, None, "played.disc_id", disc_id, "AND")

        extra_params = []
        if played_id is not None:
            extra_params.append(played_id)
            champ_condition = "WHERE p.champ_id = ?"

        if role is not None:
            extra_params.append(role)
            role_condition = f"{'AND' if played_id else 'WHERE'} p.role = ?"

        params = (extra_params * 2) + params

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
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                        AND u.disc_id = g.first_blood
                    {champ_condition}
                    {role_condition}
                    GROUP BY g.first_blood
                ) first_bloods
                INNER JOIN
                (
                    SELECT
                        u.disc_id,
                        CAST(COUNT(DISTINCT g.game_id) as REAL) AS c,
                        g.timestamp
                    FROM games AS g
                    LEFT JOIN participants AS p
                        ON g.game_id = p.game_id
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    {champ_condition}
                    {role_condition}
                    GROUP BY u.disc_id
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
                        u.disc_id,
                        SUM({stat}) AS s
                    FROM participants AS p
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    {champ_condition}
                    {role_condition}
                    GROUP BY u.disc_id
                ) stat_values
                INNER JOIN (
                    SELECT
                        u.disc_id,
                        CAST(COUNT(DISTINCT g.game_id) as real) AS c,
                        g.timestamp
                    FROM games AS g
                    LEFT JOIN participants AS p
                        ON g.game_id = p.game_id
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    {champ_condition}
                    {role_condition}
                    GROUP BY u.disc_id
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

        return self.query(query, *params, format_func="all", default=[(disc_id, None, None)])

    def get_most_played_id(self, disc_id):
        query = f"""
            SELECT
                champ_id,
                COUNT(*) AS c
            FROM participants AS p
            INNER JOIN users AS u
                ON u.player_id = p.player_id
            WHERE u.disc_id = ?
            GROUP BY p.champ_id
            ORDER BY COUNT(*) DESC
            LIMIT 5
        """

        return self.query(query, disc_id, format_func="all")

    def get_played_doinks_count(self, disc_id, champ_id=None, role=None):
        parameters = [disc_id]

        if role is not None:
            role_condition = "AND p.role = ?"
            parameters.append(role)
        else:
            role_condition = ""

        if champ_id is not None:
            champ_condition = "AND p.champ_id=?"
            parameters.append(champ_id)
        else:
            champ_condition = "GROUP BY p.champ_id"

        query = f"""
            SELECT
                p.champ_id,
                COUNT(DISTINCT p.game_id) AS c
            FROM participants AS p
            INNER JOIN users AS u
                ON u.player_id = p.player_id
            WHERE p.doinks IS NOT NULL
                AND u.disc_id=?
                {role_condition}
                {champ_condition}
        """

        def format_result(cursor):
            return cursor.fetchone()[1] if champ_id is not None else cursor.fetchall()

        return self.query(query, *parameters, format_func=format_result)

    def get_played_intfar_count(self, disc_id, champ_id=None, role=None):
        parameters = [disc_id]

        if role is not None:
            role_condition = "AND p.role = ?"
            parameters.append(role)
        else:
            role_condition = ""

        if champ_id is not None:
            champ_condition = "AND p.champ_id=?"
            parameters.append(champ_id)
        else:
            champ_condition = "GROUP BY p.champ_id"

        query = f"""
            SELECT
                p.champ_id,
                COUNT(DISTINCT p.game_id) AS c
            FROM games AS g
            INNER JOIN participants AS p
            ON p.game_id = g.game_id
            INNER JOIN users AS u
                ON u.player_id = p.player_id
                AND g.intfar_id = u.disc_id
            WHERE
                g.intfar_id IS NOT NULL
                AND g.intfar_id = ?
                {role_condition}
                {champ_condition}
        """

        def format_result(cursor):
            return cursor.fetchone()[1] if champ_id is not None else cursor.fetchall()

        return self.query(query, *parameters, format_func=format_result)

    def get_played_with_most_doinks(self, disc_id):
        doinks_query = self.get_played_doinks_count(disc_id).query
        query = f"""
            SELECT sub.champ_id, MAX(sub.c) FROM (
                {doinks_query}
            ) sub
        """

        return self.query(query, disc_id, format_func="one")

    def get_played_with_most_intfars(self, disc_id):
        intfar_query = self.get_played_intfar_count(disc_id).query
        query = f"""
            SELECT sub.champ_id, MAX(sub.c) FROM (
                {intfar_query}
            ) sub
        """

        return self.query(query, disc_id, format_func="one")

    def get_played_ids(self, disc_id=None, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "u.disc_id", disc_id)

        query = f"""
            SELECT DISTINCT p.champ_id
            FROM participants AS p
            INNER JOIN users AS u
                ON u.player_id = p.player_id
            JOIN games AS g
                ON p.game_id = g.game_id
                {delim_str}
        """

        with self:
            return self.execute_query(query, *params).fetchall()

    def get_played_winrate(self, disc_id, champ_id, role: str=None):
        role_condition = "AND p.role = ?" if role is not None else ""

        query = f"""
            SELECT
                (wins.c / played.c) * 100 AS wr,
                played.c AS gs
            FROM (
                SELECT
                    CAST(COALESCE(COUNT(DISTINCT g.game_id), 0) as real) AS c,
                    p.champ_id
                FROM games AS g
                LEFT JOIN participants AS p
                    ON g.game_id = p.game_id
                INNER JOIN users AS u
                    ON u.player_id = p.player_id
                WHERE
                    u.disc_id = ?
                    AND p.champ_id = ?
                    AND g.win = 1
                    {role_condition}
            ) wins,
            (
                SELECT
                    CAST(COUNT(DISTINCT g.game_id) as real) AS c,
                    p.champ_id
                FROM games AS g
                LEFT JOIN participants AS p
                    ON g.game_id = p.game_id
                INNER JOIN users AS u
                    ON u.player_id = p.player_id
                WHERE
                    u.disc_id = ?
                    AND p.champ_id = ?
                    {role_condition}
            ) played
            WHERE wins.champ_id = played.champ_id OR wins.champ_id IS NULL
        """

        with self:
            params = [disc_id, champ_id]
            if role is not None:
                params.append(role)

            return self.execute_query(query, *(params * 2)).fetchone()

    def get_min_or_max_winrate_played(
        self,
        disc_id,
        best,
        included_champs=None,
        return_top_n=1,
        min_games=10,
        time_after=None,
        time_before=None
    ):
        sort_order = "DESC" if best else "ASC"
        if included_champs is not None:
            champs_condition = (
                f"AND played.champ_id IN (" +
                ",\n".join(map(str, included_champs)) +
                ")"
            )
        else:
            champs_condition = ""

        delim_str, params = self.get_delimeter(time_after, time_before, prefix="AND")

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
                        p.champ_id
                    FROM games AS g
                    LEFT JOIN participants AS p 
                        ON g.game_id = p.game_id
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    WHERE
                        u.disc_id = ?
                        AND g.win = 1
                    GROUP BY p.champ_id
                    ORDER BY p.champ_id
               ) wins,
               (
                SELECT
                    CAST(COUNT(DISTINCT g.game_id) as real) AS c,
                    p.champ_id,
                    g.timestamp
                FROM games AS g
                LEFT JOIN participants AS p
                    ON g.game_id = p.game_id
                INNER JOIN users AS u
                    ON u.player_id = p.player_id
                WHERE u.disc_id = ?
                GROUP BY p.champ_id
                ORDER BY p.champ_id
               ) played
               WHERE
                    wins.champ_id = played.champ_id
                    AND played.c > {min_games}
                    {champs_condition}
                    {delim_str}
            ) sub
            ORDER BY
                sub.wr {sort_order},
                sub.gs DESC
            LIMIT {return_top_n}
        """

        with self:
            params.extend([disc_id] * 2)
            result = self.execute_query(query, *params).fetchall()

            if return_top_n == 1:
                result = result[0] if result != [] else (None, None, None)

            if result is None and min_games == 10:
                # If no champs are found with min 10 games, try again with 5.
                return self.get_min_or_max_winrate_played(disc_id, best, included_champs, return_top_n, min_games=min_games // 2)

            return result if result[0] is not None else (None, None, None)

    def get_role_winrate(self, disc_id, time_after=None, time_before=None):
        delim_str, params = self.get_delimeter(time_after, time_before, prefix="AND")
        query = f"""
            SELECT
                sub.wr,
                CAST(sub.gs AS INTEGER),
                sub.role
            FROM (
                SELECT
                    (wins.c / played.c) * 100 AS wr,
                    played.c AS gs,
                    played.role as role
                FROM (
                    SELECT
                        CAST(COUNT(DISTINCT g.game_id) AS REAL) AS c,
                        role
                    FROM games AS g
                    LEFT JOIN participants AS p 
                        ON g.game_id = p.game_id
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    WHERE
                        u.disc_id = ?
                        AND g.win = 1
                    GROUP BY p.role
                    ORDER BY p.role
               ) wins
               INNER JOIN (
                    SELECT
                        CAST(COUNT(DISTINCT g.game_id) AS REAL) AS c,
                        p.role,
                        g.timestamp
                    FROM games AS g
                    LEFT JOIN participants AS p
                        ON g.game_id = p.game_id
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    WHERE u.disc_id = ?
                    GROUP BY p.role
                    ORDER BY p.role
                ) played
                ON wins.role = played.role
                {delim_str}
            ) sub
            ORDER BY sub.wr DESC
        """

        with self:
            params.extend([disc_id] * 2)
            result = self.execute_query(query, *params).fetchall()
            return result or (None, None, None)

    def get_player_ranks(self, disc_id, time_after=None, time_before=None, order="ASC"):
        main_player_id = self.game_users[disc_id].player_id[0]
        delim_str, params = self.get_delimeter(time_after, time_before, None, "p.player_id", main_player_id)

        query = f"""
            SELECT
                p.rank_solo,
                p.rank_flex
            FROM games AS g
            INNER JOIN participants AS p
                ON p.game_id = g.game_id
            {delim_str}
            ORDER BY g.timestamp {order}
        """

        return self.query(query, *params, format_func="all")

    def get_current_rank(self, disc_id, time_after=None, time_before=None) -> tuple[str, str]:
        main_player_id = self.game_users[disc_id].player_id[0]
        query = f"""
            {self.get_player_ranks(disc_id, time_after, time_before, "DESC").query}
            LIMIT 1
        """

        with self:
            return self.execute_query(query, main_player_id).fetchone() or (None, None)

    def get_highest_rank(self, disc_id, time_after=None, time_before=None) -> tuple[str, str]:
        with self:
            ranks = self.get_player_ranks(disc_id, time_after, time_before)()
        
            solo_highest_val = 0
            solo_highest = "Unranked"
            flex_highest_val = 0
            flex_highest = "Unranked"
            for rank_solo, rank_flex in ranks:
                solo_value = get_rank_value(rank_solo)
                if solo_value > solo_highest_val:
                    solo_highest_val = solo_value
                    solo_highest = rank_solo

                flex_value = get_rank_value(rank_flex)
                if flex_value > flex_highest_val:
                    flex_highest_val = flex_value
                    flex_highest = rank_flex

            return solo_highest, flex_highest


    def get_split_start(self, offset=0):
        timestamp_before = datetime.now().timestamp() - offset
        query = """
            SELECT MAX(g.timestamp)
            FROM games AS g
            INNER JOIN (
                SELECT
                    g.game_id,
                    p.rank_flex AS curr_rank,
                    LAG(p.rank_flex, 1) OVER (PARTITION BY p.player_id ORDER BY g.timestamp DESC) prev_rank
                FROM games AS g
                INNER JOIN participants AS p
                ON p.game_id = g.game_id
                ORDER BY g.timestamp DESC
            ) sub
            ON sub.game_id = g.game_id
            WHERE
                sub.prev_rank IS NULL
                AND sub.curr_rank IS NOT NULL
                AND g.timestamp < ?
        """

        with self:
            return self.execute_query(query, timestamp_before).fetchone()[0]

    def get_split_message_status(self, disc_id):
        main_player_id = self.game_users[disc_id].player_id[0]
        query = "SELECT timestamp FROM split_messages WHERE player_id = ?"

        with self:
            result = self.execute_query(query, main_player_id).fetchone()
            return result[0] if result is not None else None

    def set_split_message_sent(self, disc_id, timestamp):
        main_player_id = self.game_users[disc_id].player_id[0]
        query = "INSERT INTO split_messages VALUES (?, ?)"
    
        with self:
            self.execute_query(query, main_player_id, timestamp)

    def get_split_summary_data(self, disc_id, stats):
        """
        Summarizes the following stats:
        - Avg stats, compare each to prev split
        - Int-Fars, doinks, compare to prev split
        - Games played, compare to prev split
        - W/L, show best and worst champ
        - Most played role(?)
        - Highest rank
        - New champs played
        """
        offset_1 = 30 * 24 * 60 * 60
        offset_2 = 190 * 24 * 60 * 60

        curr_split_start = self.get_split_start(offset_1)
        prev_split_start = self.get_split_start(offset_2)
        no_previous = curr_split_start == prev_split_start

        # Get average stats for prev split and this split
        avg_stats_before = []
        avg_stats_now = []
        for stat in stats:
            avg_prev_split = None if no_previous else self.get_average_stat(stat, disc_id, time_after=prev_split_start, time_before=curr_split_start)()
            avg_curr_split = self.get_average_stat(stat, disc_id, time_after=curr_split_start)()

            avg_stats_before.append((stat, avg_prev_split))
            avg_stats_now.append((stat, avg_curr_split))

        # Get Int-Fars & doinks for prev split and this split
        intfars_before = None if no_previous else self.get_intfar_count(disc_id, prev_split_start, curr_split_start)
        intfars_after = self.get_intfar_count(disc_id, curr_split_start)

        doinks_before = None if no_previous else self.get_doinks_count(disc_id, prev_split_start, curr_split_start)
        doinks_after = self.get_doinks_count(disc_id, curr_split_start)

        # Get games played prev split and this split
        games_played_before = None if no_previous else self.get_games_count(disc_id, prev_split_start, curr_split_start)
        games_played_after = self.get_games_count(disc_id, curr_split_start)

        # Get best and worst performing champ this split
        best_wr_info = self.get_min_or_max_winrate_played(disc_id, True, min_games=5)
        worst_wr_info = self.get_min_or_max_winrate_played(disc_id, False, min_games=5)

        # Get role performance
        role_winrates = self.get_role_winrate(disc_id, curr_split_start)

        # Get highest rank
        solo_highest, flex_highest = self.get_highest_rank(disc_id, curr_split_start)

        # Get new champs played prev split and this split
        played_before = None if no_previous else len(self.get_played_ids(disc_id, prev_split_start, curr_split_start))
        played_after = len(self.get_played_ids(disc_id, curr_split_start))

        return {
            "avg_stats_before": avg_stats_before,
            "avg_stats_now": avg_stats_now,
            "intfars_before": intfars_before,
            "intfars_after": intfars_after,
            "doinks_before": doinks_before,
            "doinks_after": doinks_after,
            "games_before": games_played_before,
            "games_after": games_played_after,
            "best_wr_champ": best_wr_info,
            "worst_wr_champ": worst_wr_info,
            "role_winrates": role_winrates,
            "solo_highest": solo_highest,
            "flex_highest": flex_highest,
            "played_before": played_before,
            "played_after": played_after
        }

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

    def insert_bingo_challenge(self, challenge_id, date, challenge_name, total, commit=True):
        query = "INSERT INTO lan_bingo (id, lan_date, name, total) VALUES (?, ?, ?, ?)"

        with self:
            self.execute_query(query, challenge_id, date, challenge_name, total, commit=commit)

    def update_bingo_challenge(self, challenge_id, date, progress=0, new_progress=0, completed=0, completed_by=None):
        query = """
            UPDATE lan_bingo
            SET
                progress = ?,
                new_progress = ?,
                completed = ?,
                completed_by = ?
            WHERE
                id = ?
                AND lan_date = ?
        """

        with self:
            self.execute_query(
                query,
                progress,
                new_progress,
                completed,
                completed_by,
                challenge_id,
                date,
            )

    def reset_bingo_new_progress(self, challenge_id):
        query = "UPDATE lan_bingo SET new_progress = 0 WHERE id = ?"

        with self:
            self.execute_query(query, challenge_id)

    def set_bingo_challenge_seen(self, challenge_id):
        query = """
            UPDATE lan_bingo
            SET notification_sent = 1
            WHERE id = ?
        """

        with self:
            self.execute_query(query, challenge_id)

    def get_new_bingo_challenges(self, amount):
        query_select = f"""
            SELECT
                sub.*
            FROM (
                SELECT
                    id,
                    name,
                    progress,
                    total,
                    0,
                    NULL,
                    NULL
                FROM lan_bingo
                WHERE completed = 0
                ORDER BY random()
                LIMIT {amount}
            ) sub
            ORDER BY sub.id
        """

        with self:
            challenges = self.execute_query(query_select).fetchall()

            if challenges == []:
                return []

            challenge_ids = ",".join(challenge[0] for challenge in challenges)
            query_update = f"""
                UPDATE lan_bingo
                SET active = 1
                WHERE id IN ({challenge_ids})
            """

            self.execute_query(query_update)

    def get_active_bingo_challenges(self, lan_date):
        query_select = f"""
            SELECT
                id,
                name,
                progress,
                new_progress,
                total,
                completed,
                completed_by,
                notification_sent
            FROM lan_bingo
            WHERE
                lan_date = ?
                AND active = 1
            ORDER BY id
        """

        with self:
            return self.execute_query(query_select, lan_date).fetchall()
