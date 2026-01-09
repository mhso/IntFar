from abc import abstractmethod
from datetime import datetime
from sqlite3 import Cursor
from typing import Any, Dict

from mhooge_flask.database import SQLiteDatabase, DBException, Query
from mhooge_flask.logging import logger

from intfar.api.util import SUPPORTED_GAMES
from intfar.api.game_data import get_stat_quantity_descriptions
from intfar.api.game_stats import GameStats, get_outlier_stat
from intfar.api.config import Config
from intfar.api.user import User

class GameDatabase(SQLiteDatabase):
    def __init__(self, game: str, config: Config):
        database = f"{config.database_folder}/{game}.db"
        schema = f"{config.schema_folder}/{game}.sql"
        super().__init__(database, schema, False)

        self.game = game
        self.config = config
        self.game_users = self.get_all_registered_users()

    @property
    def game_user_params(self):
        return []

    def get_all_registered_users(self) -> dict[int, User]:
        with self:
            all_params = ["disc_id", "player_name", "player_id"] + list(self.game_user_params) + ["main", "active"]
            params_str = ", ".join(all_params)
            query = f"SELECT {params_str} FROM users ORDER BY main DESC"
            values = self.execute_query(query).fetchall()

            games_user_info = {}

            for row in values:
                disc_id = row[0]
                active = row[-1]
                if not active:
                    continue

                if disc_id not in games_user_info:
                    games_user_info[disc_id] = {}

                for index, param_name in enumerate(all_params):
                    if param_name not in ("disc_id", "main", "active"):
                        if param_name not in games_user_info[disc_id]:
                            games_user_info[disc_id][param_name] = []

                        games_user_info[disc_id][param_name].append(row[index])
                    else:
                        games_user_info[disc_id][param_name] = row[index]

        return {disc_id: User(**games_user_info[disc_id]) for disc_id in games_user_info if "player_name" in games_user_info[disc_id]}

    def user_exists(self, discord_id):
        return discord_id in self.game_users

    def add_user(self, discord_id, **game_params):
        status = ""
        status_code = 0
        game_name = SUPPORTED_GAMES[self.game]

        try:
            with self:
                query = f"SELECT * FROM users WHERE disc_id=? AND active=0"
                inactive_accounts = self.execute_query(query, discord_id).fetchall()

                if inactive_accounts != []:
                    # Check if user has been registered before, and is now re-registering.
                    query = f"UPDATE users SET active=1 WHERE disc_id=?"
                    self.execute_query(query, discord_id)
                    status = f"Welcome back to the Int-Far:tm: Tracker:tm: for {game_name}:tm:, my lost son :hearts:"

                    self.game_users[discord_id] = self.get_all_registered_users()[discord_id]
                    status_code = 3 # User reactivated

                else:
                    main = 1

                    user_info = self.game_users.get(discord_id)

                    game_user_name = game_params["player_name"]
                    game_user_id = game_params["player_id"]

                    parameter_list = ["disc_id"] + list(game_params.keys()) + ["main", "active"]
                    questionmarks = ", ".join("?" for _ in range(len(parameter_list) - 1))
                    parameter_names = ",\n".join(parameter_list)
                    query = f"""
                        INSERT INTO users (
                            {parameter_names}
                        ) VALUES ({questionmarks}, 1)
                    """

                    if user_info is not None:
                        if len(user_info.get("player_id", [])) >= 3:
                            return (
                                False,
                                "Error: A maximum of three accounts can be registered for one person."
                            )

                        for param_name in game_params:
                            user_info[param_name].append(game_params[param_name])

                        main = 0

                        status = f"Added smurf '{game_user_name}' with ID '{game_user_id}' for {game_name}."
                        status_code = 2 # Smurf added
                    else:
                        user_params = {param_name: [game_params[param_name]] for param_name in game_params}
                        user_params["disc_id"] = discord_id
                        self.game_users[discord_id] = User(**user_params)
                        status = f"User '{game_user_name}' with ID '{game_user_id}' succesfully added for {game_name}!"
                        status_code = 1 # New user added

                    values_list = [discord_id] + list(game_params.values()) + [main]
                    self.execute_query(query, *values_list)

        except DBException as exc:
            logger.bind(event="add_user_error").exception(exc)
            return (0, "A user with that summoner name is probably already registered!")

        return (status_code, status)

    def remove_user(self, disc_id):
        with self:
            query = f"UPDATE users SET active=0 WHERE disc_id=?"
            self.execute_query(query, disc_id)

        del self.game_users[disc_id]

    def set_user_name(self, disc_id, player_id, player_name):
        with self:
            query = "UPDATE users SET player_name=? WHERE disc_id=? AND player_id=?"
            self.execute_query(query, player_name, disc_id, player_id)

    def game_user_data_from_discord_id(self, disc_id):
        return self.game_users.get(disc_id)

    def discord_id_from_ingame_info(self, exact_match=True, **search_params):
        matches = []
        for disc_id in self.game_users.keys():
            for search_param in search_params:
                for ingame_info in self.game_users[disc_id].get(search_param, []):
                    info_str = str(ingame_info)
                    value = str(search_params[search_param])
                    if exact_match and info_str.lower() == value.lower():
                        return disc_id
                    elif not exact_match and value in info_str.lower():
                        matches.append(disc_id)

        return matches[0] if len(matches) == 1 else None

    def game_exists(self, game_id):
        with self:
            query = f"SELECT game_id FROM games WHERE game_id=?"
            return self.execute_query(query, game_id).fetchone() is not None

    def delete_game(self, game_id):
        with self:
            query_1 = f"DELETE FROM games WHERE game_id=?"
            query_2 = f"DELETE FROM participants WHERE game_id=?"
            self.execute_query(query_1, game_id, commit=False)
            self.execute_query(query_2, game_id)

    def get_delim_clause(self, params: Dict[str, Any]):
        clauses = ""
        param_values = []
        for param_name in params:
            param_val = params[param_name]
            if param_val is None:
                continue

            if param_values == []:
                clauses += "WHERE "
            else:
                clauses += " AND "

            clauses += f"{param_name} ?"
            param_values.append(param_val)

        return clauses, param_values

    def get_delimeter(self, time_after, time_before=None, guild_id=None, other_key=None, other_param=None, prefix=None):
        prefix = prefix if prefix is not None else "WHERE"
        delimiter = "" if other_param is None else f" {prefix} {other_key} = ?"
        params = [] if other_param is None else [other_param]

        if time_after is not None:
            params.append(time_after)
            if other_param is None:
                delimiter += f" {prefix} timestamp > ?"
            else:
                delimiter += " AND timestamp > ?"

        if time_before is not None:
            params.append(time_before)
            if time_after is None:
                delimiter += f" {prefix} timestamp < ?"
            else:
                delimiter += " AND timestamp < ?"

        if guild_id is not None:
            params.append(guild_id)
            if time_before is None:
                delimiter += f" {prefix} guild_id = ?"
            else:
                delimiter += " AND guild_id = ?"

        return delimiter, params

    def get_latest_game(self, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id)

        query_games = f"""
            SELECT
                game_id,
                MAX(timestamp),
                duration,
                win,
                intfar_id,
                intfar_reason
            FROM games{delim_str}
        """
        query_doinks = f"""
            SELECT
                g.timestamp,
                u.disc_id,
                p.doinks
            FROM (
               SELECT
                    game_id,
                    MAX(timestamp) AS t
               FROM games{delim_str}
            ) latest
            INNER JOIN games AS g
                ON g.game_id = latest.game_id
            INNER JOIN participants AS p
                ON p.game_id = g.game_id
            INNER JOIN users AS u
                ON u.player_id = p.player_id
            WHERE p.doinks IS NOT NULL
        """
        with self:
            game_data = self.execute_query(query_games, *params).fetchone()
            doinks_data = self.execute_query(query_doinks, *params).fetchall()
            return game_data, doinks_data

    def get_most_extreme_stat(self, stat, maximize=True):
        with self:
            aggregator = "MAX" if maximize else "MIN"

            if stat == "first_blood":
                query = f"""
                    SELECT
                        sub.first_blood,
                        {aggregator}(sub.c)
                    FROM  (
                        SELECT
                            first_blood,
                            Count(DISTINCT game_id) AS c
                        FROM
                            games AS g
                        INNER JOIN users AS u
                        ON u.disc_id = g.first_blood
                        WHERE u.active = 1
                        GROUP BY first_blood
                            HAVING first_blood IS NOT NULL
                    ) sub
                """

                result = self.execute_query(query).fetchone()
                return result + (None,)

            query = f"""
                SELECT
                    u.disc_id,
                    {aggregator}({stat}),
                    game_id
                FROM participants AS p
                INNER JOIN users AS u
                ON u.player_id = p.player_id
                WHERE u.active = 1
            """

            return self.execute_query(query).fetchone()

    def get_best_or_worst_stat(self, stat, disc_id=None, maximize=True, time_after: int = None, time_before: int = None):
        delim_str, params = self.get_delimeter(time_after, time_before, prefix="AND")
        aggregator = "MAX" if maximize else "MIN"

        player_select = ""

        if stat == "first_blood":
            if disc_id is not None:
                player_condition = "AND u.disc_id = ?"
                params.append(disc_id)
            else:
                player_select = "u.disc_id,"
                player_condition = "GROUP BY u.disc_id"

            query = f"""
                SELECT
                    {player_select}
                    Count(DISTINCT g.game_id) AS best,
                    games.c AS games,
                    NULL AS extreme,
                    NULL AS game_id
                FROM games AS g
                INNER JOIN participants AS p
                ON p.game_id = g.game_id
                INNER JOIN users AS u
                ON u.player_id = p.player_id
                AND u.disc_id = g.first_blood
                INNER JOIN (
                    SELECT
                        COUNT(*) AS c,
                        p.player_id
                    FROM games AS g
                    INNER JOIN participants AS p
                    ON p.game_id = g.game_id
                    GROUP BY p.player_id
                ) AS games
                ON games.player_id = p.player_id
                WHERE
                    u.active = 1
                    {delim_str}
                    {player_condition}
            """
        else:
            params = params * 2
            if disc_id is not None:
                player_condition = "WHERE best.disc_id = ?"
                params.append(disc_id)
            else:
                player_select = "best.disc_id,"
                player_condition = "GROUP BY best.disc_id"

            query = f"""
                SELECT
                    {player_select}
                    best.c AS best,
                    games.c AS games,
                    best.extreme,
                    best.game_id
                FROM (
                    SELECT
                        sub.disc_id,
                        COUNT(*) AS c,
                        {aggregator}(sub.c) AS extreme,
                        sub.game_id
                    FROM (
                        SELECT
                            sub_sub.agg AS c,
                            p.game_id,
                            sub_sub.disc_id
                        FROM participants AS p
                        INNER JOIN (
                            SELECT
                                {aggregator}({stat}) AS agg,
                                p.game_id,
                                u.disc_id
                            FROM participants AS p
                            INNER JOIN games AS g
                                ON g.game_id = p.game_id
                            INNER JOIN users AS u
                                ON u.player_id = p.player_id
                            WHERE
                                u.active = 1
                                AND {stat} IS NOT NULL
                                {delim_str}
                            GROUP BY p.game_id
                        ) sub_sub
                            ON sub_sub.game_id = p.game_id
                        WHERE {stat} = sub_sub.agg
                    ) sub
                    GROUP BY sub.disc_id
                ) best
                INNER JOIN (
                    SELECT
                        COUNT(DISTINCT p.game_id) AS c,
                        p.game_id,
                        u.disc_id
                    FROM participants AS p
                    INNER JOIN games AS g
                        ON g.game_id = p.game_id
                    JOIN users AS u
                        ON u.player_id = p.player_id
                    WHERE
                        u.active = 1
                        AND {stat} IS NOT NULL
                        {delim_str}
                    GROUP BY u.disc_id
                ) AS games
                ON games.disc_id = best.disc_id
                {player_condition}
            """

        def format_result(cursor: Cursor):
            return cursor.fetchall() if disc_id is None else cursor.fetchone()

        return self.query(query, *params, format_func=format_result)

    @abstractmethod
    def get_played_count(self, disc_id, playable_id):
        ...

    @abstractmethod
    def get_played_count_for_stat(self, stat, maximize, disc_id):
        ...

    @abstractmethod
    def get_average_stat(self, stat: str, disc_id=None, played_id=None, min_games=10) -> Query:
        ...

    @abstractmethod
    def get_played_doinks_count(self, disc_id, playable_id):
        ...

    @abstractmethod
    def get_played_intfar_count(self, disc_id, playable_id):
        ...

    @abstractmethod
    def get_played_with_most_doinks(self, disc_id):
        ...

    @abstractmethod
    def get_played_with_most_intfars(self, disc_id):
        ...

    @abstractmethod
    def get_played_ids(self, disc_id=None, time_after=None, time_before=None, guild_id=None):
        ...

    @abstractmethod
    def get_played_winrate(self, disc_id, played_id):
        ...

    @abstractmethod
    def get_min_or_max_winrate_played(self, disc_id, best, included_ids=None, return_top_n=1, min_games=10):
        ...

    @abstractmethod
    def get_current_rank(self, disc_id):
        ...

    def get_game_ids(self):
        query = f"SELECT game_id, guild_id FROM games"
        with self:
            return self.execute_query(query).fetchall()

    def get_doinks_count(
        self,
        disc_id: int=  None,
        time_after: int = None,
        time_before: int = None,
        guild_id: int = None
    ) -> tuple[int, int]:
        """
        Query the database for the total games where doinks were earned
        as well doinks earned in total over all games.

        ### Parameters

        `:param game:`          Supported game to look for doinks for (fx. 'lol' for League of Legends)
        `:param disc_id:`       Optional Discord ID to only include counts for a single person
        `:param time_after:`    Optional UNIX timestamp to only include results after this point
        `:param time_before:`   Optional UNIX timestamp to only include results before this point
        `:param guild_id:`      Optional Discord guild ID to only include results of games played in that server

        ### Returns
        `tuple[int, int]`: Amount of games where doinks was played and amount of doinks earned in total
        """
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "u.disc_id", disc_id, "AND")

        query_doinks = f"""
            SELECT SUM(sub.doinks_games), SUM(sub.doinks_total) FROM (
                SELECT
                    COUNT(*) AS doinks_games,
                    SUM(LENGTH(REPLACE(sub_2.doinks, '0', ''))) AS doinks_total
                FROM (
                    SELECT DISTINCT
                        p.game_id,
                        u.disc_id,
                        doinks,
                        timestamp
                    FROM participants AS p
                    LEFT JOIN users AS u
                    ON u.player_id = p.player_id
                    LEFT JOIN games AS g
                    ON g.game_id = p.game_id
                    WHERE
                        doinks IS NOT NULL
                        AND u.active=1{delim_str}
                ) sub_2
                GROUP BY sub_2.disc_id
            ) sub
        """

        with self:
            doinks_games, doinks_total = self.execute_query(query_doinks, *params).fetchone()
            return doinks_games or 0, doinks_total or 0

    def get_max_doinks_details(self):
        with self:
            query = """
                SELECT 
                    MAX(counts.c),
                    counts.disc_id
                FROM (
                    SELECT
                        u.disc_id,
                        COUNT(*) AS c
                    FROM
                        participants AS p
                    INNER JOIN users AS u
                    ON u.player_id = p.player_id
                    WHERE
                        doinks IS NOT NULL
                        AND u.active = 1
                    GROUP BY u.disc_id
                ) counts
            """
            return self.execute_query(query).fetchone()

    def get_doinks_reason_counts(self):
        query_doinks_multis = """
            SELECT doinks
            FROM participants AS p
            INNER JOIN users AS u
            ON u.player_id = p.player_id
            WHERE
                doinks IS NOT NULL
                AND u.active = 1
        """

        with self:
            doinks_reasons_data = self.execute_query(query_doinks_multis).fetchall()
            if doinks_reasons_data == []:
                return None

            doinks_counts = [0 for _ in range(len(doinks_reasons_data[0][0]))]
            for reason in doinks_reasons_data:
                for index, c in enumerate(reason[0]):
                    if c == "1":
                        doinks_counts[index] += 1

            return doinks_counts

    def get_recent_intfars_and_doinks(self):
        query = """
            SELECT
                g.game_id,
                timestamp,
                u.disc_id,
                doinks,
                intfar_id,
                intfar_reason
            FROM participants AS p
            LEFT JOIN games AS g
                ON p.game_id = g.game_id
            LEFT JOIN users AS u
                ON p.player_id = u.player_id
            WHERE u.active = 1
            GROUP BY
                p.game_id,
                u.disc_id
            ORDER BY timestamp ASC
        """

        with self:
            return self.execute_query(query).fetchall()

    def get_games_results(self, ascending=True, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id)

        sort_order = "ASC" if ascending else "DESC"

        query = f"""
            SELECT
                win,
                timestamp
            FROM games
            {delim_str}
            ORDER BY timestamp {sort_order}
        """

        with self:
            return self.execute_query(query, *params).fetchall()

    def get_games_count(self, disc_id=None, time_after=None, time_before=None, guild_id=None):
        delim_str_1, params_1 = self.get_delimeter(time_after, time_before, guild_id, prefix="AND")
        delim_str_2, params_2 = self.get_delimeter(time_after, time_before, guild_id, "u.disc_id", disc_id, prefix="AND")

        query = f"""
            WITH game_cte AS (
                SELECT
                    p.game_id,
                    u.disc_id,
                    g.guild_id,
                    g.win,
                    g.timestamp,
                    g.duration
                FROM games AS g
                INNER JOIN participants AS p
                ON p.game_id = g.game_id
                INNER JOIN users AS u
                ON u.player_id = p.player_id
                WHERE
                    u.active = 1
                    {delim_str_1}
                    {delim_str_2}
            )
            SELECT
                games.c,
                games.t_min,
                games.t_max,
                games.d,
                wins.c,
                guilds.c
            FROM (
                SELECT
                    COUNT(DISTINCT game_id) AS c,
                    SUM(duration) AS d,
                    MIN(timestamp) AS t_min,
                    MAX(timestamp) AS t_max
                FROM game_cte
            ) games,
            (
                SELECT COUNT(DISTINCT game_id) AS c
                FROM game_cte
                WHERE win = 1
            ) wins,
            (
                SELECT COUNT(DISTINCT guild_id) AS c
                FROM game_cte
            ) guilds
        """

        params = params_2 if params_1 is None else params_1 + params_2

        with self:
            return self.execute_query(query, *params).fetchone()

    def get_longest_game(self, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id)

        query = f"""
            SELECT
                MAX(duration),
                timestamp
            FROM games
            {delim_str}
        """

        with self:
            return self.execute_query(query, *params).fetchone()

    def get_intfar_count(self, disc_id=None, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "u.disc_id", disc_id, "AND")

        query_intfars = f"""
            SELECT SUM(sub.intfars)
            FROM (
                SELECT COUNT(*) AS intfars
                FROM (
                    SELECT DISTINCT
                        g.game_id,
                        intfar_id
                FROM games AS g
                LEFT JOIN users AS u
                ON u.disc_id=intfar_id
                WHERE
                    intfar_id IS NOT NULL
                    AND u.active = 1
                    {delim_str}
                ) sub_2
                GROUP BY sub_2.intfar_id
            ) sub
        """

        with self:
            intfars = self.execute_query(query_intfars, *params).fetchone()
            return (intfars[0] if intfars is not None else 0) or 0

    def get_intfar_reason_counts(self):
        query_intfar_multis = """
            SELECT intfar_reason
            FROM games AS g
            LEFT JOIN users AS u
                ON u.disc_id = g.intfar_id
            WHERE
                g.intfar_id IS NOT NULL
                AND u.active=1
            GROUP BY game_id
        """

        with self:
            intfar_multis_data = self.execute_query(query_intfar_multis).fetchall()
            if intfar_multis_data == []:
                return [], []

            amount_intfars = len(intfar_multis_data[0][0])

            intfar_counts = [0] * amount_intfars
            intfar_multi_counts = {
                i: 0 for i in range(1, amount_intfars + 1)
            }
            for reason in intfar_multis_data:
                amount = 0
                for index, c in enumerate(reason[0]):
                    if c == "1":
                        intfar_counts[index] += 1
                        amount += 1
                if amount > 0:
                    intfar_multi_counts[amount] += 1

            intfar_multis = [intfar_multi_counts[x] for x in intfar_multi_counts]

            return intfar_counts, intfar_multis

    def get_total_winrate(self, disc_id):
        query = f"""
            SELECT (wins.c / played.c) * 100 FROM (
                SELECT CAST(COUNT(DISTINCT g.game_id) as real) AS c
                FROM games AS g
                LEFT JOIN participants AS p
                    ON g.game_id = p.game_id
                INNER JOIN users AS u
                    ON u.player_id = p.player_id
                WHERE
                    u.disc_id = ?
                    AND win = 1
            ) wins,
            (
                SELECT CAST(COUNT(DISTINCT g.game_id) as real) AS c
                FROM games AS g
                LEFT JOIN participants AS p
                    ON g.game_id = p.game_id
                INNER JOIN users AS u
                    ON u.player_id = p.player_id
                WHERE u.disc_id = ?
            ) played
        """
    
        with self:
            return self.execute_query(query, disc_id, disc_id).fetchone()[0]

    def get_winrate_relation(self, disc_id, best, min_games=10):
        query_games = f"""
            SELECT
                u2.disc_id,
                Count(*) as c
            FROM participants AS p1
            INNER JOIN users AS u1
                ON u1.player_id = p1.player_id
            INNER JOIN participants AS p2
                ON p1.player_id != p2.player_id
                AND p1.game_id = p2.game_id
            INNER JOIN users AS u2
                ON p2.player_id = u2.player_id
            WHERE u1.disc_id = ?
            GROUP BY
                u1.disc_id,
                u2.disc_id
            ORDER BY c DESC
        """
        query_wins = f"""
            SELECT
                u2.disc_id,
                Count(*) as c
            FROM games AS g
            INNER JOIN participants AS p1
                ON p1.game_id = g.game_id
            INNER JOIN users AS u1
                ON u1.player_id = p1.player_id
            INNER JOIN participants AS p2
                ON p1.player_id != p2.player_id
                AND p1.game_id = p2.game_id
            INNER JOIN users AS u2
                ON p2.player_id = u2.player_id
            WHERE u1.disc_id = ?
                AND win = 1
            GROUP BY
                u1.disc_id,
                u2.disc_id
            ORDER BY c DESC
        """

        with self:
            games_with_person = {}
            wins_with_person = {}
            for part_id, wins in self.execute_query(query_wins, disc_id):
                if disc_id == part_id or not self.user_exists(part_id):
                    continue

                wins_with_person[part_id] = wins

            for part_id, games in self.execute_query(query_games, disc_id):
                if self.user_exists(part_id):
                    games_with_person[part_id] = games

            winrate_with_person = [
                (x, games_with_person[x], (wins_with_person[x] / games_with_person[x]) * 100)
                for x in games_with_person if games_with_person[x] > min_games
            ]

            if winrate_with_person == []:
                if min_games == 10:
                    return self.get_winrate_relation(disc_id, best, min_games=5)

                return None, None, None

            func = max if best else min

            return func(winrate_with_person, key=lambda x: x[2])

    def get_meta_stats(self):
        query_persons = f"SELECT COUNT(*) FROM participants AS p GROUP BY game_id"

        users = (len(self.game_users),)
        with self:
            game_data = self.get_games_count()
            longest_game = self.get_longest_game()
            intfar_data = self.get_intfar_count()
            doinks_data = self.get_doinks_count()
            persons_counts = self.execute_query(query_persons)
            persons_count = {2: 0, 3: 0, 4: 0, 5: 0}
            for persons in persons_counts:
                persons_count[persons[0]] += 1

            twos_ratio = int((persons_count[2] / game_data[0]) * 100)
            threes_ratio = int((persons_count[3] / game_data[0]) * 100)
            fours_ratio = int((persons_count[4] / game_data[0]) * 100)
            fives_ratio = int((persons_count[5] / game_data[0]) * 100)
            games_ratios = [twos_ratio, threes_ratio, fours_ratio, fives_ratio]

            intfar_counts, intfar_multis_counts = self.get_intfar_reason_counts()
            intfar_ratios = [(count / intfar_data) * 100 for count in intfar_counts]
            intfar_multis_ratios = [(count / intfar_data) * 100 for count in intfar_multis_counts]

            return (
                game_data + longest_game + users + doinks_data +
                (intfar_data, games_ratios, intfar_ratios, intfar_multis_ratios)
            )

    def get_monthly_delimiter(self):
        curr_time = datetime.now()

        current_month = curr_time.month

        if curr_time.day > 1 or curr_time.hour > self.config.hour_of_ifotm_announce + 1:
            # Get Int-Far stats for current month.
            start_of_month = curr_time.replace(day=1, hour=0, minute=0, second=0)
            min_timestamp = int(start_of_month.timestamp())
        else:
            # Get Int-Far stats for previous month.
            prev_month = 12 if current_month == 1 else current_month - 1
            prev_year = curr_time.year if prev_month != 12 else curr_time.year - 1
            prev_time = curr_time.replace(
                prev_year,
                prev_month,
                1,
                0,
                0,
                0,
                0,
            )
            min_timestamp = int(prev_time.timestamp())

        max_timestamp = int(curr_time.timestamp())
        return f"timestamp > {min_timestamp} AND timestamp < {max_timestamp}"

    def get_intfars_of_the_month(self):
        delim_str = self.get_monthly_delimiter()

        query_intfars = f"""
            SELECT intfar_id
            FROM games AS g
            LEFT JOIN users AS u
                ON u.disc_id = intfar_id
            WHERE
                intfar_id IS NOT NULL
                AND {delim_str}
                AND u.active = 1
            GROUP BY g.game_id
        """
        query_games = f"""
            SELECT u.disc_id
            FROM
                games AS g
            LEFT JOIN participants AS p
                ON g.game_id = p.game_id
            LEFT JOIN users AS u
                ON u.player_id = p.player_id
            WHERE
                {delim_str}
                AND u.active = 1
            GROUP BY
                g.game_id,
                u.disc_id
        """

        with self:
            games_per_person = self.execute_query(query_games).fetchall()
            intfars_per_person = self.execute_query(query_intfars).fetchall()
            pct_intfars = []
            intfar_dict = {}
            games_dict = {}
            for intfar_id in intfars_per_person:
                intfars = intfar_dict.get(intfar_id[0], 0)
                intfar_dict[intfar_id[0]] = intfars + 1

            for disc_id in games_per_person:
                games = games_dict.get(disc_id[0], 0)
                games_dict[disc_id[0]] = games + 1

            for disc_id in games_dict:
                total_games = games_dict[disc_id]

                if total_games < self.config.ifotm_min_games:
                    # Disqualify people with less than 10 games played this month.
                    continue

                intfars = intfar_dict.get(disc_id, 0)

                if intfars == 0:
                    # Disqualify people with no intfars this month.
                    continue

                pct_intfars.append(
                    (disc_id, total_games, intfars, (intfars / total_games) * 100)
                )

            return sorted(pct_intfars, key=lambda x: (x[3], x[2]), reverse=True)

    def get_longest_intfar_streak(self, disc_id):
        query = """
            SELECT
                intfar_id,
                timestamp
            FROM games
            GROUP BY game_id
            ORDER BY game_id
        """

        with self:
            int_fars = self.execute_query(query).fetchall()
            max_count = 0
            timestamp_ended = None
            count = 0
            for int_far, timestamp in int_fars:
                if int_far is None or disc_id != int_far:
                    count = 0
                else:
                    count += 1

                if count > max_count:
                    max_count = count
                    timestamp_ended = timestamp

            if timestamp_ended is not None:
                timestamp_ended = datetime.fromtimestamp(timestamp_ended).strftime("%Y-%m-%d")

            return max_count, timestamp_ended

    def get_longest_no_intfar_streak(self, disc_id):
        if not self.user_exists(disc_id):
            return 0

        query = """
            SELECT
                intfar_id,
                timestamp
            FROM participants AS p
            INNER JOIN games AS g
                ON g.game_id = p.game_id
            INNER JOIN users AS u
                ON u.player_id = p.player_id
            WHERE u.disc_id = ?
            ORDER BY g.game_id ASC
        """

        with self:
            int_fars = self.execute_query(query, disc_id).fetchall()
            max_count = 0
            timestamp_ended = None
            count = 0
            for int_far, timestamp in int_fars:
                if disc_id == int_far:
                    count = 0
                else:
                    count += 1

                if count > max_count:
                    max_count = count
                    timestamp_ended = timestamp

            if timestamp_ended is not None:
                if timestamp_ended == timestamp:
                    # Streak is ongoing
                    timestamp_ended = None
                else:
                    timestamp_ended = datetime.fromtimestamp(timestamp_ended).strftime("%Y-%m-%d")

            return max_count, timestamp_ended

    def get_current_intfar_streak(self):
        query = f"""
            SELECT g.intfar_id
            FROM games AS g
            LEFT JOIN users AS u
                ON g.intfar_id = u.disc_id
            WHERE u.active = 1
            GROUP BY game_id
            ORDER BY game_id DESC
        """

        with self:
            int_fars = self.execute_query(query).fetchall()
            if int_fars == []:
                return 0, None

            prev_intfar = int_fars[0][0]
            for count, int_far in enumerate(int_fars[1:], start=1):
                if int_far[0] is None or prev_intfar != int_far[0]:
                    return count, prev_intfar

            return len(int_fars), prev_intfar # All the Int-Fars is the current int-far!

    def get_longest_win_or_loss_streak(self, disc_id: int, win: int):
        query = f"""
            SELECT g.win
            FROM games AS g
            INNER JOIN participants AS p
                ON p.game_id = g.game_id
            INNER JOIN users AS u
                ON p.player_id = u.player_id
            WHERE
                u.disc_id = ?
                AND u.active
            GROUP BY g.game_id
            ORDER BY g.game_id DESC
        """

        with self:
            games = self.execute_query(query, disc_id).fetchall()

            max_count = 0
            count = 0
            for row in games:
                if win != row[0]:
                    count = 0
                else:
                    count += 1

                if count > max_count:
                    max_count = count

            return max_count

    def get_current_win_or_loss_streak(self, disc_id: int, win: int, offset=0):
        query = f"""
            SELECT g.win
            FROM games AS g
            INNER JOIN participants AS p
                ON p.game_id = g.game_id
            INNER JOIN users AS u
                ON p.player_id = u.player_id
            WHERE
                u.disc_id = ?
                AND u.active = 1
            GROUP BY g.game_id
            ORDER BY timestamp DESC
        """

        with self:
            games = self.execute_query(query, disc_id).fetchall()

            count_offset = 1 if offset == 0 else 0

            for count, row in enumerate(games[offset:], start=count_offset):
                if row[0] != win:
                    return count

            total_offset = -offset if offset > 0 else 1

            return len(games) + total_offset

    def get_max_intfar_details(self):
        query = f"""
            SELECT
                MAX(pcts.pct),
                pcts.intboi
            FROM (
                SELECT
                    (intfar_counts.c / games_counts.c) * 100 AS pct,
                    intfar_counts.intfar_id AS intboi
                FROM (
                    SELECT
                        intfar_id,
                        CAST(Count(*) as real) as c
                    FROM games
                    WHERE intfar_id IS NOT NULL
                    GROUP BY intfar_id
                ) AS intfar_counts
                INNER JOIN (
                    SELECT
                        u.disc_id,
                        CAST(Count(*) as real) as c
                    FROM participants AS p
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    GROUP BY u.disc_id
                ) AS games_counts
                ON games_counts.disc_id = intfar_counts.intfar_id
                WHERE games_counts.c > 10
            ) AS pcts
            INNER JOIN users AS u
                ON u.disc_id = pcts.intboi
            WHERE u.active = 1
        """

        with self:
            return self.execute_query(query).fetchone()

    def get_intfar_stats(self, disc_id, monthly=False, time_after=None, time_before=None, guild_id=None):
        params_1 = []
        params_2 = []

        if monthly:
            monthly_delim = self.get_monthly_delimiter()
            if disc_id is not None:
                delim_str_1 = f" WHERE u.disc_id = ? AND {monthly_delim}"
                delim_str_2 = f" WHERE intfar_id = ? AND {monthly_delim}"
                params_1 = [disc_id]
                params_2 = [disc_id]
            else:
                delim_str_1 = f" WHERE {monthly_delim}"
                delim_str_2 = f" WHERE {monthly_delim}"
        else:
            delim_str_1, params_1 = self.get_delimeter(time_after, time_before, guild_id, "u.disc_id", disc_id)
            delim_str_2, params_2 = self.get_delimeter(time_after, time_before, guild_id, "intfar_id", disc_id)

        query_total = f"""
            SELECT Count(*)
            FROM games AS g
            INNER JOIN participants AS p
                ON g.game_id = p.game_id
            INNER JOIN users AS u
                ON u.player_id = p.player_id
            {delim_str_1}
        """
        query_intfar = f"""
            SELECT intfar_reason
            FROM games AS g
            {delim_str_2}
            GROUP BY g.game_id
        """

        with self:
            total_games = self.execute_query(query_total, *params_1).fetchone()[0]
            intfar_games = self.execute_query(query_intfar, *params_2).fetchall()
            return total_games, intfar_games

    def get_intfar_relations(self, disc_id):
        query_games = f"""
            SELECT
                u2.disc_id,
                COUNT(*) AS c
            FROM participants AS p1
            INNER JOIN users AS u1
                ON u1.player_id = p1.player_id
            INNER JOIN participants AS p2
                ON p2.player_id != p1.player_id
                AND p2.game_id = p1.game_id
            INNER JOIN users AS u2
                ON u2.player_id = p2.player_id
            WHERE u1.disc_id = ?
            GROUP BY
                u1.disc_id,
                u2.disc_id
            ORDER BY c DESC
        """
        query_intfars = f"""
            SELECT
                u.disc_id,
                COUNT(*) AS c
            FROM games AS g
            INNER JOIN participants AS p
                ON p.game_id = g.game_id
            INNER JOIN users AS u
                ON u.player_id = p.player_id
            WHERE intfar_id IS NOT NULL
                AND intfar_id = ?
            GROUP BY u.disc_id
            ORDER BY c DESC
        """

        with self:
            games_with_person = {}
            intfars_with_person = {}

            for part_id, intfars in self.execute_query(query_intfars, disc_id):
                if disc_id == part_id or not self.user_exists(part_id):
                    continue
                intfars_with_person[part_id] = intfars

            for part_id, games in self.execute_query(query_games, disc_id):
                if self.user_exists(part_id):
                    games_with_person[part_id] = games

            return games_with_person, intfars_with_person

    def get_doinks_stats(self, disc_id=None, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "u.disc_id", disc_id, "AND")

        query = f"""
            SELECT doinks
            FROM participants AS p
            LEFT JOIN users AS u
                ON u.player_id = p.player_id
            LEFT JOIN games AS g
                ON p.game_id = g.game_id
            WHERE
                doinks IS NOT NULL
                AND u.active = 1
                {delim_str}
            GROUP BY g.game_id
        """

        with self:
            return self.execute_query(query, *params).fetchall()

    def get_doinks_relations(self, disc_id):
        query_games = f"""
            SELECT
                u2.disc_id,
                COUNT(*) as c
            FROM participants AS p1
            INNER JOIN users AS u1
                ON u1.player_id = p1.player_id
            INNER JOIN participants AS p2
                ON p1.player_id != p2.player_id
                AND p1.game_id = p2.game_id
            INNER JOIN users AS u2
                ON u2.player_id = p2.player_id
            WHERE u1.disc_id = ?
            GROUP BY
                u1.disc_id,
                u2.disc_id
            ORDER BY c DESC
        """
        query_doinks = f"""
            SELECT
                u2.disc_id,
                Count(*) as c
            FROM participants AS p1
            INNER JOIN users AS u1
                ON u1.player_id = p1.player_id
            INNER JOIN participants AS p2
                ON p1.player_id != p2.player_id
                AND p1.game_id = p2.game_id
            INNER JOIN users AS u2
                ON u2.player_id = p2.player_id
            WHERE p1.doinks IS NOT NULL
                AND u1.disc_id = ?
            GROUP BY
                u1.disc_id,
                u2.disc_id
            ORDER BY c DESC
        """

        with self:
            games_with_person = {}
            doinks_with_person = {}

            for part_id, doinks in self.execute_query(query_doinks, disc_id):
                if disc_id == part_id or not self.user_exists(part_id):
                    continue
                doinks_with_person[part_id] = doinks

            for part_id, games in self.execute_query(query_games, disc_id):
                if self.user_exists(part_id):
                    games_with_person[part_id] = games

            return games_with_person, doinks_with_person

    def get_max_games_count(self, time_after: int = None, time_before: int = None):
        delim_str, params = self.get_delimeter(time_after, time_before, prefix="AND")

        query = f"""
            SELECT MAX(counts.c)
            FROM (
                SELECT COUNT(games.disc_id) AS c
                FROM (
                    SELECT u.disc_id
                    FROM participants AS p
                    INNER JOIN games AS g
                        ON g.game_id = p.game_id
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    WHERE u.active = 1
                    {delim_str}
                ) games
                GROUP BY games.disc_id
            ) counts
        """
        with self:
            return self.execute_query(query, *params).fetchone()[0]

    def get_performance_score(self, disc_id: int | None = None, time_after: int = None, time_before: int = None, minimum_games: int = None):
        intfar_weight = 1
        doinks_weight = 1
        winrate_weight = 2
        stats_weight = 0.25

        stat_keys = get_stat_quantity_descriptions(self.game)
        stat_joins = []

        time_clause = ""
        params = []
        if time_after is not None:
            time_clause = "AND g.timestamp > ?"
            params.append(time_after)
        if time_before is not None:
            time_clause += " AND g.timestamp < ?"
            params.append(time_before)

        if params != []:
            params = params * 4

        prev_join = "doinks.disc_id"
        for stat in stat_keys:
            query_best = self.get_best_or_worst_stat(stat, maximize=stat != "deaths", time_after=time_after, time_before=time_before).query

            stat_joins.append(f"LEFT JOIN ({query_best}) {stat}_best\nON {stat}_best.disc_id = {prev_join}")
            prev_join = f"{stat}_best.disc_id"

        if time_after is not None and time_before is not None:
            params.extend([time_after, time_before] * ((len(stat_keys) * 2) - 1))

        stat_join_queries = "\n".join(stat_joins)

        stat_equations = [
            f"COALESCE({stat}_best.best / {stat}_best.games, 0) * {stats_weight}" for stat in stat_keys
        ]

        stat_equations_str = " + ".join(stat_equations)

        most_games = self.get_max_games_count(time_after, time_before) or 1
        games_weight = 0.25

        total = (intfar_weight + doinks_weight + winrate_weight + games_weight + (len(stat_keys) * stats_weight)) / 2
        performance_range = 10

        equation = (
            f"(((1 - COALESCE(intfars.c / played.c, 0)) * {intfar_weight} + " +
            f"COALESCE(doinks.c / played.c, 0) * {doinks_weight} + " +
            f"COALESCE(wins.c / played.c, 0) * {winrate_weight} + " +
            f"(played.c / {most_games}) * {games_weight} + "
            f"{stat_equations_str}) / {total}) * {performance_range}"
        )
        min_games = self.config.performance_mimimum_games if minimum_games is None else minimum_games

        query = f"""
            SELECT
                sub.user,
                MIN(sub.score, {performance_range})
            FROM (
                SELECT
                    played.disc_id AS user,
                    {equation} AS score
                FROM
                (
                    SELECT
                        CAST(COUNT(DISTINCT g.game_id) AS real) AS c,
                        u.disc_id
                    FROM games AS g
                    INNER JOIN participants AS p
                        ON g.game_id = p.game_id
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    WHERE 1=1
                    {time_clause}
                    GROUP BY u.disc_id
                ) played
                LEFT JOIN (
                    SELECT
                        CAST(COUNT(DISTINCT g.game_id) AS real) AS c,
                        u.disc_id
                    FROM games AS g
                    INNER JOIN participants AS p
                        ON g.game_id = p.game_id
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    WHERE win = 1
                    {time_clause}
                    GROUP BY u.disc_id
                ) wins
                ON wins.disc_id = played.disc_id
                LEFT JOIN (
                    SELECT
                        COALESCE(c, 0.0) AS c,
                        u.disc_id AS intfar_id
                    FROM participants AS p
                    LEFT JOIN participants AS g
                    ON g.game_id = p.game_id
                    INNER JOIN users AS u
                        ON u.player_id = p.player_id
                    LEFT JOIN (
                        SELECT
                            CAST(COUNT(*) AS real) AS c,
                            intfar_id
                        FROM games AS g
                        WHERE
                            intfar_id IS NOT NULL
                            {time_clause}
                        GROUP BY intfar_id
                    ) sub
                    ON u.disc_id = sub.intfar_id
                    GROUP BY u.disc_id
                ) intfars
                ON intfars.intfar_id = wins.disc_id
                LEFT JOIN (
                    SELECT
                        CAST(SUM(LENGTH(REPLACE(COALESCE(doinks_sub.doinks, ''), '0', ''))) AS real) AS c,
                        doinks_sub.disc_id
                    FROM (
                        SELECT
                            DISTINCT p.game_id,
                            p.doinks,
                            u.disc_id
                        FROM participants AS p
                        INNER JOIN games AS g
                            ON g.game_id = p.game_id
                        INNER JOIN users AS u
                            ON u.player_id = p.player_id
                        WHERE
                            doinks IS NOT NULL
                            {time_clause}
                    ) doinks_sub
                    GROUP BY doinks_sub.disc_id
                ) doinks
                ON doinks.disc_id = intfars.intfar_id
                {stat_join_queries}
                WHERE played.c > {min_games}
            ) sub
            LEFT JOIN users AS u
                ON sub.user = u.disc_id
            WHERE u.active = 1
            GROUP BY sub.user
            ORDER BY sub.score DESC
        """

        def format_result(cursor: Cursor):
            performance_scores = cursor.fetchall()
            if disc_id is None:
                return performance_scores

            rank = len(self.game_users) - 1
            score = 0
            for index, (score_id, score_value) in enumerate(performance_scores):
                if score_id == disc_id:
                    rank = index
                    score = score_value
                    break

            return score, rank + 1, len(performance_scores)

        return self.query(query, *params, format_func=format_result)

    def _was_stat_beaten(self, prev_val, curr_val, best, reverse):
        if None in (prev_val, curr_val):
            return False

        if reverse: # Stat is 'deaths'
            if best and curr_val < prev_val: # Fewest deaths has been reached
                return True
            elif not best and curr_val > prev_val: # Most deaths has been reached
                return True
        else: # Stat is any other stat
            if best and curr_val > prev_val: # A new best has been set for a stat
                return True
            elif not best and curr_val < prev_val: # A new worst has been set for a stat
                return True

        return False

    def get_beaten_stat_records(self, parsed_game_stats: GameStats):
        global_records_best = []
        global_records_worst = []
        player_records_best = []
        player_records_worst = []

        players_in_game = {stats.disc_id for stats in parsed_game_stats.filtered_player_stats}

        relevant_stats = parsed_game_stats.filtered_player_stats[0].stat_quantity_desc()
        for stat in relevant_stats:
            if stat == "first_blood":
                continue

            reverse_order = stat == "deaths"

            (
                best_id,
                best_value,
                worst_id,
                worst_value
            ) = get_outlier_stat(
                parsed_game_stats.filtered_player_stats,
                stat,
                reverse_order=reverse_order
            )

            # Check whether player has beaten their own record in a stat
            for disc_id, _, _, players_best, _ in self.get_best_or_worst_stat(stat, maximize=not reverse_order)():
                if disc_id in players_in_game and self._was_stat_beaten(players_best, best_value, True, reverse_order):
                    # Player has set a new personal best for a stat
                    player_records_best.append(
                        (stat, best_value, best_id, players_best, None)
                    )

            for disc_id, _, _, players_worst, _ in self.get_best_or_worst_stat(stat, maximize=reverse_order)():
                if disc_id in players_in_game and self._was_stat_beaten(players_worst, worst_value, False, reverse_order):
                    # Player has set a new personal worst for a stat
                    player_records_worst.append(
                        (stat, worst_value, worst_id, players_worst, None)
                    )

            # Check once whether anyone has beaten the global record in a stat
            prev_best_id,  prev_best, _ = self.get_most_extreme_stat(stat, not reverse_order)
            prev_worst_id, prev_worst, _ = self.get_most_extreme_stat(stat, reverse_order)

            if self._was_stat_beaten(prev_best, best_value, True, reverse_order):
                # A new best has been set for a stat
                global_records_best.append(
                    (stat, best_value, best_id, prev_best, prev_best_id)
                )
            elif self._was_stat_beaten(prev_worst, worst_value, False, reverse_order):
                # A new worst has been set for a stat
                global_records_worst.append(
                    (stat, worst_value, worst_id, prev_worst, prev_worst_id)
                )

        return global_records_best, global_records_worst, player_records_best, player_records_worst

    def save_stats(self, parsed_game_stats: GameStats) -> tuple[list[tuple], list[tuple], list[tuple], list[tuple]]:
        """
        Save all the stats in the given GameStats object to the database.
        Also determines whether any stat "records" have been beaten (i.e. whether
        someone has gotten a new lowest or highest value for a stat) and returns
        those stats along with who beat set the new record.
        """
        (
            global_records_best, 
            global_records_worst,
            player_records_best,
            player_records_worst,
        ) = self.get_beaten_stat_records(parsed_game_stats)

        game_insert_str = ",\n".join(parsed_game_stats.stats_to_save())
        game_insert_qms = ",".join(["?"] * len(parsed_game_stats.stats_to_save()))

        stats_insert_str = ",\n".join(parsed_game_stats.filtered_player_stats[0].stats_to_save())
        stats_insert_qms = ",".join(["?"] * len(parsed_game_stats.filtered_player_stats[0].stats_to_save()))

        game_insert_values = [getattr(parsed_game_stats, stat) for stat in parsed_game_stats.stats_to_save()]

        with self:
            query_game = f"""
                INSERT INTO games(
                    {game_insert_str}
                )
                VALUES ({game_insert_qms})
            """

            self.execute_query(
                query_game, *game_insert_values
            )

            query = f"""
                INSERT INTO participants(
                    {stats_insert_str}
                )
                VALUES ({stats_insert_qms})
            """

            for player_stats in parsed_game_stats.filtered_player_stats:
                stat_insert_values = [getattr(player_stats, stat) for stat in player_stats.stats_to_save()]
                logger.debug(f"Saving participant data:\n", stat_insert_values)

                self.execute_query(query, *stat_insert_values)

        return global_records_best, global_records_worst, player_records_best, player_records_worst

    def save_missed_game(self, game_id, guild_id, timestamp):
        query = "INSERT INTO missed_games VALUES (?, ?, ?)"
        with self:
            try:
                self.execute_query(query, game_id, guild_id, timestamp)
            except DBException:
                pass # Missed game has already been saved, just ignore error

    def get_missed_games(self):
        query = "SELECT game_id, guild_id FROM missed_games"
        with self:
            return self.execute_query(query).fetchall()

    def inspect_missed_games(self):
        query = "SELECT game_id, guild_id, timestamp FROM missed_games"

        def format_result(cursor):
            results = []
            for game_id, guild_id, timestamp in cursor.fetchall():
                fmt_time = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                results.append(f"{game_id} in {guild_id} on {fmt_time}")

            return results

        return self.query(query, format_func=format_result)

    def remove_missed_game(self, game_id):
        query = "DELETE FROM missed_games WHERE game_id=?"
        with self:
            self.execute_query(query, game_id)

    def get_game_stats(self, stats, game_id=None, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "g.game_id", game_id)

        stats_to_select = ", ".join(stats)

        query = f"""
            SELECT
                {stats_to_select}
            FROM games AS g
            {delim_str}
            ORDER BY timestamp DESC
        """

        with self:
            return self.execute_query(query, *params).fetchall()

    def get_player_stats(self, stats, game_id=None, disc_id=None, time_after=None, time_before=None, guild_id=None):
        prefix = "AND"
        game_id_delimeter = ""
        params = []
        if game_id is not None:
            game_id_delimeter = "AND g.game_id=?"
            params = [game_id]
 
        delim_str, delim_params = self.get_delimeter(time_after, time_before, guild_id, "u.disc_id", disc_id, prefix)
        params = params + delim_params

        stats_copy = list(stats)

        if disc_id is None and "disc_id" not in stats:
            if stats_copy[0] == "game_id":
                stats.insert(1, "disc_id")
                stats_copy.insert(1, "disc_id")
            else:
                stats.insert(0, "disc_id")
                stats_copy.insert(0, "disc_id")
        if "player_id" not in stats:
            if stats_copy[0] == "disc_id":
                stats.insert(1, "player_id")
                stats_copy.insert(1, "player_id")
            else:
                stats.insert(2, "player_id")
                stats_copy.insert(2, "player_id")

        if stats_copy[0] == "disc_id":
            stats_copy[0] = "u.disc_id"
        elif stats_copy[1] == "disc_id":
            stats_copy[1] = "u.disc_id"

        if stats_copy[1] == "player_id":
            stats_copy[1] = "p.player_id"
        elif stats_copy[2] == "player_id":
            stats_copy[2] = "p.player_id"

        try:
            # game_id will be ambigious, so we need to specify table alias
            index = stats_copy.index("game_id")
            stats_copy[index] = "g.game_id"
        except ValueError:
            pass

        stats_to_select = ", ".join(stats_copy)

        query = f"""
            SELECT
                {stats_to_select}
            FROM participants AS p
            INNER JOIN games AS g
                ON g.game_id = p.game_id
            INNER JOIN users AS u
                ON u.player_id = p.player_id
            WHERE u.active = 1
            {game_id_delimeter}
            {delim_str}
            ORDER BY timestamp DESC
        """

        with self:
            return self.execute_query(query, *params).fetchall()

    def get_event_sound(self, disc_id, event):
        query = "SELECT sound FROM event_sounds WHERE disc_id=? AND event=?"

        with self:
            result = self.execute_query(query, disc_id, event).fetchone()

            return result[0] if result is not None else None

    def set_event_sound(self, disc_id, sound, event):
        query = "REPLACE INTO event_sounds(disc_id, sound, event) VALUES (?, ?, ?)"

        with self:
            self.execute_query(query, disc_id, sound, event)

    def remove_event_sound(self, disc_id, event):
        query = "DELETE FROM event_sounds WHERE disc_id=? AND event=?"

        with self:
            self.execute_query( query, disc_id, event)

    def get_bets(self, only_active, disc_id=None, guild_id=None):
        with self:
            query = """
                SELECT
                    better_id,
                    id,
                    guild_id,
                    bets.timestamp,
                    amount,
                    event_id,
                    game_duration,
                    target,
                    ticket
            """

            if not only_active:
                query += ", result, payout"

            query += f"""
                FROM bets
                WHERE
            """

            if not only_active:
                query += "result != 0"
            else:
                query += "result = 0"

            params = []
            if disc_id is not None:
                query += " AND better_id = ?"
                params.append(disc_id)
            if guild_id is not None:
                query += " AND guild_id = ?"
                params.append(guild_id)

            query += f"""
                GROUP BY id
                ORDER by id
            """

            data = self.execute_query(query, *params).fetchall()

            data_for_person = {}
            bet_ids = []
            amounts = []
            events = []
            targets = []

            for index, row in enumerate(data):
                discord_id = row[0]
                if discord_id not in data_for_person:
                    data_for_person[discord_id] = []

                next_ticket = None if index == len(data) - 1 else data[index+1][8]
                next_better = None if index == len(data) - 1 else data[index+1][0]
                bet_ids.append(row[1])
                amounts.append(row[4])
                events.append(row[5])
                targets.append(row[7])

                ticket = row[8]

                if ticket is None or ticket != next_ticket or discord_id != next_better:
                    data_tuple = (bet_ids, row[2], row[3], amounts, events, targets, row[6])
                    if only_active: # Include ticket in tuple, if only active bets.
                        data_tuple = data_tuple + (row[-1], None)
                    else: # Include both result and payout if resolved bets.
                        data_tuple = data_tuple + (row[-2], row[-1])

                    data_for_person[discord_id].append(data_tuple)
                    bet_ids = []
                    amounts = []
                    events = []
                    targets = []

            return data_for_person if disc_id is None else data_for_person.get(disc_id)

    def generate_ticket_id(self, disc_id):
        with self:
            query = "SELECT MAX(ticket) FROM bets WHERE better_id=?"
            curr_id = self.execute_query(query, disc_id).fetchone()
            if curr_id is None or curr_id[0] is None:
                return 0
            return curr_id[0] + 1

    def get_bet_id(self, disc_id, guild_id, event_id, target=None, ticket=None):
        with self:
            if ticket is None:
                query = """
                    SELECT id
                    FROM bets
                    WHERE
                        better_id = ?
                        AND guild_id = ?
                        AND event_id = ?
                        AND (target=? OR target IS NULL)
                        AND result = 0
                """
                params = [disc_id, guild_id, event_id, target]
            else:
                query = """
                    SELECT id
                    FROM bets
                    WHERE
                        better_id = ?
                        AND guild_id = ?
                        AND ticket = ?
                        AND result = 0
                """
                params = [disc_id, guild_id, ticket]

            result = self.execute_query(query, *params).fetchone()

            return None if result is None else result[0]

    def get_better_id(self, bet_id):
        if bet_id is not None:
            bet_id = int(bet_id)

        with self:
            query = "SELECT better_id FROM bets WHERE id=?"
            result = self.execute_query(query, bet_id).fetchone()

            return None if result is None else result[0]

    def make_bet(self, disc_id, guild_id, event_id, amount, game_duration, target_person=None, ticket=None):
        query_bet = """
            INSERT INTO bets(
                better_id,
                guild_id,
                timestamp,
                event_id,
                amount,
                game_duration,
                target,
                ticket,
                result
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with self:
            self.execute_query(
                query_bet,
                disc_id,
                guild_id,
                0,
                event_id,
                amount,
                game_duration,
                target_person,
                ticket,
                0
            )

            return self.execute_query("SELECT last_insert_rowid()").fetchone()[0]

    def cancel_bet(self, bet_id, disc_id):
        query_del = "DELETE FROM bets WHERE id = ? AND better_id = ? AND result = 0"
        query_amount = "SELECT amount FROM bets WHERE id = ? AND better_id = ? AND result = 0"
    
        with self:
            amount = self.execute_query(query_amount, bet_id, disc_id).fetchone()[0]
            self.execute_query(query_del, bet_id, disc_id)

            return amount

    def cancel_multi_bet(self, ticket, disc_id):
        query_del = "DELETE FROM bets WHERE better_id=? AND ticket=?"
        query_amount = "SELECT amount FROM bets WHERE better_id=? AND ticket=?"

        with self:
            amounts = self.execute_query(query_amount, disc_id, ticket).fetchall()
            amount_total = sum(x[0] for x in amounts)
            self.execute_query(query_del, disc_id, ticket)

            return amount_total

    def mark_bet_as_resolved(self, bet_id, game_id, timestamp, success, value):
        result_val = 1 if success else -1
        query_bet = "UPDATE bets SET game_id=?, timestamp=?, result=?, payout=? WHERE id=?"
        payout = value if success else None

        with self:
            self.execute_query(query_bet, game_id, timestamp, result_val, payout, bet_id)

    def reset_bets(self):
        query_bets = "DELETE FROM bets WHERE result=0"
        query_balance = "UPDATE betting_balance SET tokens=100"

        with self:
            self.execute_query(query_bets)
            self.execute_query(query_balance)

    def get_lifetime_activity(self):
        query = """
            SELECT SUBSTR(
                DATE(
                    DATETIME(g.timestamp, 'unixepoch', 'localtime')
                ),
            1, 7) AS month, COUNT(g.game_id), COUNT(w.game_id)
            FROM (
                SELECT game_id, timestamp
                FROM games
            ) g
            LEFT JOIN
            (
                SELECT game_id
                FROM games
                WHERE win = 1
            ) w
            ON g.game_id = w.game_id
            GROUP BY month
        """

        with self:
            return self.execute_query(query).fetchall()

    def get_weekday_activity(self):
        query = """
            SELECT STRFTIME(
                "%w",
                DATE(DATETIME(g.timestamp, 'unixepoch', 'localtime'))
            ) AS day, COUNT(g.game_id), COUNT(w.game_id)
            FROM (
                SELECT game_id, timestamp
                FROM games
            ) g
            LEFT JOIN
            (
                SELECT game_id
                FROM games
                WHERE win = 1
            ) w
            ON g.game_id = w.game_id
            GROUP BY day
        """

        with self:
            return self.execute_query(query).fetchall()

    def get_hourly_activity(self):
        query = """
            SELECT STRFTIME(
                "%H",
                DATETIME(timestamp, 'unixepoch', 'localtime')
            ) AS hour, COUNT(g.game_id), COUNT(w.game_id)
            FROM (
                SELECT game_id, timestamp
                FROM games
            ) g
            LEFT JOIN
            (
                SELECT game_id
                FROM games
                WHERE win = 1
            ) w
            ON g.game_id = w.game_id
            GROUP BY hour
        """

        with self:
            return self.execute_query(query).fetchall()

    def get_most_games_in_a_day(self):
        query = """
            SELECT timestamp
            FROM games AS g
            ORDER BY timestamp ASC
        """

        with self:
            grouped_by_day = {}
            for timestamp in self.execute_query(query):
                dt = datetime.fromtimestamp(timestamp[0])
                day = dt.strftime("%Y-%m-%d")
                grouped_by_day[day] = grouped_by_day.get(day, 0) + 1

            data_as_list = sorted(grouped_by_day.items(), key=lambda x: x[1], reverse=True)
            return data_as_list[0:10]

    def clear_tables(self):
        with self:
            query_tables = "SELECT name FROM sqlite_master WHERE type='table'"
            tables = self.execute_query(query_tables).fetchall()

            for table in tables:
                query = f"DELETE FROM {table[0]}"
                self.execute_query(query, commit=False)

            self.connection.commit()
