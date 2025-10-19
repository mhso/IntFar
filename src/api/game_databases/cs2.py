from sqlite3 import Cursor
from api.game_database import GameDatabase
from api.config import Config

class CS2GameDatabase(GameDatabase):
    def __init__(self, game: str, config: Config):
        super().__init__(game, config)

    @property
    def game_user_params(self):
        return ["match_auth_code", "latest_match_token"]

    def set_new_cs2_sharecode(self, disc_id, steam_id, sharecode):
        query = f"UPDATE users SET latest_match_token=? WHERE disc_id=? AND player_id=?"

        with self:
            self.execute_query(query, sharecode, disc_id, steam_id)
            for index, player_id in enumerate(self.game_users[disc_id].player_id):
                if player_id == steam_id:
                    self.game_users[disc_id].latest_match_token[index] = sharecode
                    break

    def get_latest_sharecode(self, player_id):
        with self:
            return self.execute_query("SELECT latest_match_token FROM users WHERE player_id=?", player_id).fetchone()[0]

    def get_played_count(self, disc_id, playable_id):
        query = """
            SELECT COUNT(*)
            FROM games AS g
            INNER JOIN participants AS p
                ON p.game_id = g.game_id
            INNER JOIN users AS u
                ON u.player_id = p.player_id
            WHERE u.disc_id = ?
            AND g.map_id = ?
        """

        with self:
            result = self.execute_query(query, disc_id, playable_id).fetchone()
            return result[0]

    def get_played_count_for_stat(self, stat, maximize, disc_id):
        aggregator = "MAX" if maximize else "MIN"

        query = f"""
            SELECT sub2.map_id, {aggregator}(c) FROM (
                SELECT
                    sub.map_id,
                    COUNT(*) AS c
                FROM (
                    SELECT
                        {aggregator}({stat}) AS c,
                        g.map_id,
                        u.disc_id
                    FROM participants AS p
                    INNER JOIN games AS g
                        ON g.game_id = p.game_id
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    WHERE
                        u.active = 1
                        AND {stat} IS NOT NULL
                    GROUP BY g.game_id
                ) sub
                WHERE sub.disc_id = ?
                GROUP BY sub.map_id
            ) sub2
        """

        with self:
            return self.execute_query(query, disc_id).fetchone()

    def get_average_stat(self, stat, disc_id=None, played_id=None, min_games=10):
        params = []
        player_condition = ""
        map_condition = ""

        if played_id is not None:
            params = [played_id] * 2
            map_condition = "AND g.map_id=?"

        if disc_id is not None:
            params.append(disc_id)
            player_condition = "AND played.disc_id=?"

        query = f"""
            SELECT played.disc_id, stat_values.s / played.c AS avg_val, CAST(played.c AS int)
            FROM
            (
                SELECT
                    u.disc_id,
                    SUM({stat}) AS s
                FROM participants AS p
                INNER JOIN games AS g
                    ON g.game_id = p.game_id
                INNER JOIN users AS u
                    ON u.player_id = p.player_id
                WHERE {stat} IS NOT NULL
                {map_condition}
                GROUP BY u.disc_id
            ) stat_values
            INNER JOIN
            (
                SELECT
                    u.disc_id,
                    CAST(COUNT(DISTINCT g.game_id) as real) AS c
                FROM games AS g
                LEFT JOIN participants AS p
                    ON g.game_id = p.game_id
                INNER JOIN users AS u
                    ON u.player_id = p.player_id
                WHERE {stat} IS NOT NULL
                {map_condition}
                GROUP BY u.disc_id
            ) played
                ON played.disc_id = stat_values.disc_id
            INNER JOIN users AS u
                ON u.disc_id = played.disc_id
            WHERE u.active = 1
                AND played.c > {min_games}
                {player_condition}
            GROUP BY played.disc_id
            ORDER BY avg_val DESC
        """

        def format_result(cursor: Cursor):
            result = cursor.fetchall()
            return result or [(disc_id, None, None)]

        return self.query(query, *params, format_func=format_result)

    def get_played_doinks_count(self, disc_id, map_id=None):
        champ_condition = ""
        parameters = [disc_id]
        if map_id is not None:
            champ_condition = "AND g.map_id=?"
            parameters.append(map_id)
        else:
            champ_condition = "GROUP BY g.map_id"

        query = f"""
            SELECT
                g.map_id,
                COUNT(DISTINCT p.game_id) AS c
            FROM participants AS p
            INNER JOIN games AS g
                ON g.game_id = p.game_id
            INNER JOIN users AS u
                ON u.player_id = p.player_id
            WHERE
                u.disc_id=?
                AND p.doinks IS NOT NULL
                {champ_condition}
        """

        def format_result(cursor):
            return cursor.fetchone()[1] if map_id is not None else cursor.fetchall()

        return self.query(query, *parameters, format_func=format_result)

    def get_played_intfar_count(self, disc_id, map_id=None):
        champ_condition = ""
        parameters = [disc_id]
        if map_id is not None:
            champ_condition = "AND g.map_id=?"
            parameters.append(map_id)
        else:
            champ_condition = "GROUP BY g.map_id"

        query = f"""
            SELECT
                COUNT(DISTINCT g.game_id) AS c,
                map_id
            FROM games AS g
            WHERE
                g.intfar_id IS NOT NULL
                AND g.intfar_id = ?
                {champ_condition}
        """

        def format_result(cursor):
            return cursor.fetchone()[1] if map_id is not None else cursor.fetchall()

        return self.query(query, disc_id, map_id, format_func=format_result)

    def get_played_with_most_doinks(self, disc_id):
        doinks_query = self.get_played_doinks_count(disc_id).query
        query = f"""
            SELECT sub.map_id, MAX(sub.c) FROM (
                {doinks_query}
            ) sub
        """

        with self:
            return self.query(query, disc_id, format_func="one")

    def get_played_with_most_intfars(self, disc_id):
        doinks_query = self.get_played_intfar_count(disc_id).query
        query = f"""
            SELECT sub.map_id, MAX(sub.c) FROM (
                {doinks_query}
            ) sub
        """

        with self:
            return self.query(query, disc_id, format_func="one")

    def get_played_ids(self, disc_id=None, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "u.disc_id", disc_id)

        query = f"""
            SELECT DISTINCT g.map_id
            FROM participants AS p
            INNER JOIN games AS g
                ON p.game_id = g.game_id
            INNER JOIN users AS u
                ON u.player_id = p.player_id
                {delim_str}
        """

        with self:
            return self.execute_query(query, *params).fetchall()

    def get_played_winrate(self, disc_id, map_id):
        query = f"""
            SELECT
                (wins.c / played.c) * 100 AS wr,
                played.c AS gs
            FROM (
                SELECT
                    CAST(COALESCE(COUNT(DISTINCT g.game_id), 0) as real) AS c,
                    g.map_id
                FROM games AS g
                LEFT JOIN participants AS p
                    ON g.game_id = p.game_id
                INNER JOIN users AS u
                    ON u.player_id = p.player_id
                WHERE
                    u.disc_id = ?
                    AND g.map_id = ?
                    AND g.win = 1
            ) wins,
            (
                SELECT
                    CAST(COUNT(DISTINCT g.game_id) as real) AS c,
                    g.map_id
                FROM games AS g
                LEFT JOIN participants AS p
                    ON g.game_id = p.game_id
                INNER JOIN users AS u
                    ON u.player_id = p.player_id
                WHERE
                    u.disc_id = ?
                    AND g.map_id = ?
            ) played
            WHERE wins.map_id = played.map_id OR wins.map_id IS NULL
        """

        with self:
            params = [disc_id, map_id] * 2
            return self.execute_query(query, *params).fetchone()

    def get_min_or_max_winrate_played(self, disc_id, best, included_maps=None, return_top_n=1, min_games=10):
        sort_order = "DESC" if best else "ASC"
        if included_maps is not None:
            maps_condition = (
                "AND played.map_id IN (" +
                ",\n".join(f"'{map_id}'" for map_id in included_maps) +
                ")"
            )
        else:
            maps_condition = ""

        query = f"""
            SELECT
                sub.wr,
                CAST(sub.gs as integer),
                sub.map
            FROM (
                SELECT
                    (wins.c / played.c) * 100 AS wr,
                    played.c AS gs,
                    played.map_id as map
                FROM (
                    SELECT
                        CAST(COUNT(DISTINCT g.game_id) as real) AS c,
                        g.map_id
                    FROM games AS g
                    LEFT JOIN participants AS p
                        ON g.game_id = p.game_id
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    WHERE
                        u.disc_id = ?
                        AND g.win = 1
                    GROUP BY g.map_id
                    ORDER BY g.map_id
               ) wins,
               (
                SELECT
                    CAST(COUNT(DISTINCT g.game_id) as real) AS c,
                    g.map_id
                FROM games AS g
                LEFT JOIN participants AS p
                    ON g.game_id = p.game_id
                INNER JOIN users AS u
                    ON u.player_id = p.player_id
                WHERE u.disc_id = ?
                GROUP BY g.map_id
                ORDER BY g.map_id
               ) played
               WHERE
                    wins.map_id = played.map_id
                    AND played.c > {min_games}
                    {maps_condition}
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
                result = None if result == [] else result[0]

            if result is None and min_games == 10:
                # If no champs are found with min 10 games, try again with 5.
                return self.get_min_or_max_winrate_played(disc_id, best, included_maps, return_top_n, min_games=5)

            return result

    def get_current_rank(self, disc_id) -> str:
        query = """
            SELECT p.rank
            FROM participants AS p
            INNER JOIN users AS u
                ON u.player_id = p.player_id
            WHERE u.disc_id = ?
            ORDER BY p.game_id DESC
            LIMIT 1
        """

        with self:
            return self.execute_query(query, disc_id).fetchone()

    def get_overtime_winrate(self, disc_id):
        query = """
            SELECT
                CAST(games.c AS integer),
                CAST((wins.c / games.c * 100) AS integer)
            FROM (
                SELECT CAST(COUNT(*) AS real) AS c
                FROM games AS g
                INNER JOIN participants AS p
                    ON p.game_id = g.game_id
                INNER JOIN users AS u
                    ON u.player_id = p.player_id
                WHERE u.disc_id = ?
                    AND g.rounds_us + g.rounds_them > 24
            ) games,
            (
                SELECT CAST(COUNT(*) AS real) AS c
                FROM games AS g
                INNER JOIN participants AS p
                    ON p.game_id = g.game_id
                INNER JOIN users AS u
                    ON u.player_id = p.player_id
                WHERE u.disc_id = ?
                    AND g.rounds_us + g.rounds_them > 24
                    AND g.win = 1
            ) wins
        """

        with self:
            return self.execute_query(query, disc_id, disc_id).fetchone()
