import os
from shutil import copyfile
from datetime import datetime
from sqlite3 import DatabaseError, OperationalError, ProgrammingError

from mhooge_flask.logging import logger

from mhooge_flask.database import SQLiteDatabase

from api.game_stats import GameStats, get_outlier_stat
from api.user import User
from api.util import TimeZone, generate_user_secret, SUPPORTED_GAMES

class DBException(OperationalError, ProgrammingError):
    def __init__(self, *args):
        super().__init__(args)

class Database(SQLiteDatabase):
    def __init__(self, config):
        self.config = config
        super().__init__(self.config.database, "resources/schema.sql", False)

        # Populate summoner names and ids lists with currently registered summoners.
        params = {
            "lol": [],
            "csgo": ["match_auth_code", "latest_match_token"]
        }
        with self:
            self.all_users: dict[int, User] = self.get_base_users()
            self.users_by_game: dict[str, dict[int, User]] = {game: self.get_all_registered_users(game, *params[game]) for game in SUPPORTED_GAMES}

    def _group_users(self, user_data, *params):
        user_entries = {}
        for user in user_data:
            disc_id = user[0]

            if disc_id not in user_entries:
                user_entries[disc_id] = {}

            for index, param_name in enumerate(params):
                if param_name not in user_entries[disc_id]:
                    user_entries[disc_id][param_name] = []

                user_entries[disc_id][param_name].append(user[index + 1])

        return {disc_id: User(**user_entries[disc_id]) for disc_id in user_entries}

    def _get_games_table(self, game):
        return f"games_{game}"

    def _get_participants_table(self, game):
        return f"participants_{game}"

    def _get_users_table(self, game):
        return f"users_{game}"

    def user_exists(self, game, discord_id):
        if game is None:
            return any(discord_id in self.users_by_game[game] for game in self.users_by_game)

        return discord_id in self.users_by_game[game]

    def get_base_users(self):
        query = "SELECT disc_id, secret FROM users"
        with self:
            return {x[0]: User(x[0], x[1]) for x in self.execute_query(query).fetchall()}

    def get_all_registered_users(self, game, *extra_params):
        users_table = self._get_users_table(game)
        with self:
            query = "SELECT disc_id, secret FROM users"
            values = self.execute_query(query).fetchall()
            games_user_info = {x[0]: {"disc_id": x[0], "secret": x[1]} for x in values}

            all_params = ["disc_id", "ingame_name", "ingame_id"] + list(extra_params) + ["active"]
            params_str = ", ".join(all_params)
            query = f"SELECT {params_str} FROM {users_table} ORDER BY main DESC"
            values = self.execute_query(query).fetchall()

            for row in values:
                disc_id = row[0]
                active = row[-1]
                if not active:
                    continue

                for index, param_name in enumerate(all_params[1:], start=1):
                    if param_name not in games_user_info[disc_id]:
                        games_user_info[disc_id][param_name] = []

                    games_user_info[disc_id][param_name].append(row[index])

        return {disc_id: User(**games_user_info[disc_id]) for disc_id in games_user_info if "ingame_name" in games_user_info[disc_id]}

    def get_client_secret(self, disc_id):
        query = "SELECT secret FROM users WHERE disc_id=?"

        with self:
            return self.execute_query(query, disc_id).fetchone()[0]

    def get_user_from_secret(self, secret):
        query = "SELECT disc_id FROM users WHERE secret=?"

        with self:
            return self.execute_query(query, secret).fetchone()[0]

    def add_user(self, game, discord_id, **game_params):
        status = ""
        status_code = 0
        users_table = self._get_users_table(game)
        try:
            with self:
                query = f"SELECT * FROM {users_table} WHERE disc_id=? AND active=0"
                inactive_accounts = self.execute_query(query, discord_id).fetchall()

                if inactive_accounts != []:
                    # Check if user has been registered before, and is now re-registering.
                    query = f"UPDATE {users_table} SET active=1 WHERE disc_id=?"
                    self.execute_query(query, discord_id)
                    status = "Welcome back to the Int-Far:tm: Tracker:tm:, my lost son :hearts:"

                    reduced_params = dict(game_params)
                    del reduced_params["ingame_name"]
                    del reduced_params["ingame_id"]

                    self.all_users = self.get_base_users()
                    self.users_by_game[game][discord_id] = self.get_all_registered_users(game, **reduced_params)
                    status_code = 2 # User reactivated

                else:
                    new_user = not any(self.user_exists(game_name, discord_id) for game_name in self.users_by_game)
                    main = 1
                    if new_user:
                        # User has never signed up for any game before
                        query = "INSERT INTO users(disc_id, secret, reports) VALUES (?, ?, ?)"
                        main = 1
                        secret = generate_user_secret()
                        self.execute_query(query, discord_id, secret, 0)
                    else:
                        secret = self.all_users[discord_id].secret

                    user_info = self.users_by_game[game].get(discord_id)

                    game_user_name = game_params["ingame_name"]
                    game_user_id = game_params["ingame_id"]

                    parameter_list = ["disc_id"] + list(game_params.keys()) + ["main", "active"]
                    questionmarks = ", ".join("?" for _ in range(len(parameter_list) - 1))
                    parameter_names = ",\n".join(parameter_list)
                    query = f"""
                        INSERT INTO {users_table} (
                            {parameter_names}
                        ) VALUES ({questionmarks}, 1)
                    """

                    if user_info is not None:
                        if sum(len(user_info.get(param_name, [])) for param_name in game_params) >= 3:
                            return (
                                False,
                                "Error: A maximum of three accounts can be registered for one person."
                            )

                        for param_name in game_params:
                            user_info[param_name].append(game_params[param_name])

                        main = 0

                        status = f"Added smurf '{game_user_name}' with ID '{game_user_id}' for {SUPPORTED_GAMES[game]}."
                    else:
                        user_params = {param_name: [game_params[param_name]] for param_name in game_params}
                        user_params["disc_id"] = discord_id
                        user_params["secret"] = secret
                        self.all_users[discord_id] = User(discord_id, secret)
                        self.users_by_game[game][discord_id] = User(**user_params)
                        status = f"User '{game_user_name}' with ID '{game_user_id}' succesfully added for {SUPPORTED_GAMES[game]}!"

                    values_list = [discord_id] + list(game_params.values()) + [main]
                    self.execute_query(query, *values_list)

                    if new_user:
                        # Only create betting balance table if user is new.
                        query = "INSERT INTO betting_balance VALUES (?, ?)"

                        self.execute_query(query, discord_id, 100)

                    status_code = 1 # User added
    
        except DBException:
            return (0, "A user with that summoner name is already registered!")

        return (status_code, status)

    def remove_user(self, game, disc_id):
        game_table = self._get_users_table(game)
        with self:
            query = f"UPDATE {game_table} SET active=0 WHERE disc_id=?"
            self.execute_query(query, disc_id)

        del self.users_by_game[game][disc_id]

    def discord_id_from_ingame_info(self, game, exact_match=True, **search_params):
        matches = []
        for disc_id in self.users_by_game[game]:
            for search_param in search_params:
                for ingame_info in self.users_by_game[game][disc_id].get(search_param, []):
                    info_str = str(ingame_info)
                    value = str(search_params[search_param])
                    if exact_match and info_str.lower() == value.lower():
                        return disc_id
                    elif not exact_match and value in info_str.lower():
                        matches.append(disc_id)

        return matches[0] if len(matches) == 1 else None

    def game_user_data_from_discord_id(self, game, disc_id):
        return self.users_by_game[game].get(disc_id, None)

    def game_exists(self, game, game_id):
        games_table = self._get_games_table(game)

        with self:
            query = f"SELECT game_id FROM {games_table} WHERE game_id=?"
            return self.execute_query(query, game_id).fetchone() is not None

    def delete_game(self, game, game_id):
        games_table = self._get_games_table(game)

        with self:
            query_1 = f"DELETE FROM {games_table} WHERE game_id=?"
            query_2 = f"DELETE FROM participants_{game} WHERE game_id=?"
            self.execute_query(query_1, game_id, commit=False)
            self.execute_query(query_2, game_id)

    def set_new_csgo_sharecode(self, disc_id, sharecode):
        game = "csgo"
        users_table = self._get_users_table(game)

        query = f"UPDATE {users_table} SET latest_match_token=? WHERE disc_id=?"

        with self:
            self.execute_query(query, sharecode, disc_id)
            self.users_by_game[game][disc_id].latest_match_token = sharecode

    def get_latest_game(self, game, time_after=None, time_before=None, guild_id=None):
        stats_table = self._get_participants_table(game)
        games_table = self._get_games_table(game)
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id)

        query_games = f"SELECT MAX(timestamp), win, intfar_id, intfar_reason FROM {games_table}{delim_str}"
        query_doinks = f"""
            SELECT
                timestamp,
                disc_id,
                doinks
            FROM (
               SELECT MAX(timestamp) AS t
               FROM {games_table}{delim_str}
            ) sub_1, {stats_table} AS p
            JOIN {games_table} AS g
            ON p.game_id = g.game_id
            WHERE doinks IS NOT NULL AND timestamp = sub_1.t
        """
        with self:
            game_data = self.execute_query(query_games, *params).fetchone()
            doinks_data = self.execute_query(query_doinks, *params).fetchall()
            return game_data, doinks_data

    def get_most_extreme_stat(self, game, stat, maximize=True):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)

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
                            {games_table} AS g
                        INNER JOIN {users_table} AS u
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
                    p.disc_id,
                    {aggregator}({stat}),
                    game_id
                FROM {stats_table} AS p
                JOIN {users_table} AS u
                ON u.disc_id = p.disc_id
                WHERE u.active = 1
            """

            return self.execute_query(query).fetchone()

    def get_best_or_worst_stat(self, game, stat, disc_id, maximize=True):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)

        with self:
            aggregator = "MAX" if maximize else "MIN"

            if stat == "first_blood":
                query = f"""
                    SELECT Count(DISTINCT g.game_id)
                    FROM {games_table} AS g
                    JOIN {stats_table} AS p
                    ON p.game_id = g.game_id
                    INNER JOIN {users_table} AS u
                    ON u.disc_id = p.disc_id
                    WHERE
                        g.first_blood = ?
                        AND u.active = 1
                """

                result = self.execute_query(query, disc_id).fetchone()
                return result[0], None, None

            query = f"""
                SELECT
                    COUNT(*),
                    {aggregator}(c),
                    game_id
                FROM (
                    SELECT
                        {aggregator}({stat}) AS c,
                        p.game_id,
                        p.disc_id
                    FROM {stats_table} AS p
                    JOIN {users_table} AS u
                    ON u.disc_id = p.disc_id
                    WHERE u.active = 1
                    GROUP BY game_id
                ) sub
                WHERE disc_id = ?
            """

            return self.execute_query(query, disc_id).fetchone()

    def get_league_champ_count_for_stat(self, stat, maximize, disc_id):
        game = "lol"
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)
        aggregator = "MAX" if maximize else "MIN"

        query = f"""
            SELECT sub2.champ_id, {aggregator}(c) FROM (
                SELECT
                    sub.champ_id,
                    COUNT(*) AS c
                FROM (
                    SELECT
                        {aggregator}({stat}) AS c,
                        p.champ_id,
                        p.disc_id
                    FROM {stats_table} AS p
                    JOIN {games_table} AS g
                    ON g.game_id = p.game_id
                    JOIN {users_table} AS u
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

    def get_average_stat_league(self, stat, disc_id=None, champ_id=None, min_games=10):
        game = "lol"
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)
        params = []
        player_condition = ""
        champ_condition = ""

        if champ_id is not None:
            params = [champ_id, champ_id]
            champ_condition = "WHERE p.champ_id=?"

        if disc_id is not None:
            params.append(disc_id)
            player_condition = "AND played.disc_id=?"

        if stat == "first_blood":
            query = f"""
                SELECT played.disc_id, first_bloods.c / played.c AS avg_val, CAST(played.c AS int)
                FROM (
                    SELECT g.first_blood, CAST(COUNT(DISTINCT g.game_id) as REAL) AS c
                    FROM {games_table} AS g
                    INNER JOIN {stats_table} AS p
                        ON p.game_id = g.game_id
                        AND p.disc_id = g.first_blood
                    {champ_condition}
                    GROUP BY g.first_blood
                ) first_bloods
                INNER JOIN
                (
                    SELECT p.disc_id, CAST(COUNT(DISTINCT g.game_id) as REAL) AS c
                    FROM {games_table} AS g
                    LEFT JOIN {stats_table} AS p
                        ON g.game_id = p.game_id
                    {champ_condition}
                    GROUP BY p.disc_id
                ) played
                    ON played.disc_id = first_bloods.first_blood
                INNER JOIN {users_table} AS u
                    ON u.disc_id = played.disc_id
                WHERE u.active = 1
                    AND played.c > {min_games}
                    {player_condition}
                GROUP BY played.disc_id
                ORDER BY avg_val DESC
            """

        else:
            query = f"""
                SELECT played.disc_id, stat_values.s / played.c AS avg_val, CAST(played.c AS int)
                FROM
                (
                    SELECT disc_id, SUM({stat}) AS s
                    FROM {stats_table} AS p
                    {champ_condition.replace('AND', 'WHERE')}
                    GROUP BY p.disc_id
                ) stat_values
                INNER JOIN
                (
                    SELECT disc_id, CAST(COUNT(DISTINCT g.game_id) as real) AS c
                    FROM {games_table} AS g
                    LEFT JOIN {stats_table} AS p
                        ON g.game_id = p.game_id
                    {champ_condition}
                    GROUP BY p.disc_id
                ) played
                    ON played.disc_id = stat_values.disc_id
                INNER JOIN {users_table} AS u
                    ON u.disc_id = played.disc_id
                WHERE u.active = 1
                    AND played.c > {min_games}
                {player_condition}
                GROUP BY played.disc_id
                ORDER BY avg_val DESC
            """

        with self:
            result = self.execute_query(query, *params).fetchall()
            return result or [(disc_id, None, None)]

    def get_csgo_map_count_for_stat(self, stat, maximize, disc_id):
        pass

    def get_doinks_count(
        self,
        game: str,
        disc_id: int=None,
        time_after: int=None,
        time_before: int=None,
        guild_id: int=None
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
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "p.disc_id", disc_id, "AND")

        query_doinks = f"""
            SELECT SUM(sub.doinks_games), SUM(sub.doinks_total) FROM (
                SELECT COUNT(*) AS doinks_games, SUM(LENGTH(REPLACE(sub_2.doinks, '0', ''))) AS doinks_total FROM (
                    SELECT DISTINCT
                        p.game_id,
                        p.disc_id,
                        doinks,
                        timestamp
                    FROM {stats_table} AS p
                    LEFT JOIN {users_table} AS u
                    ON u.disc_id = p.disc_id
                    LEFT JOIN {games_table} AS g
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

    def get_league_champ_with_most_doinks(self, disc_id):
        stats_table = self._get_participants_table("lol")
        with self:
            query = f"""
                SELECT sub.champ_id, MAX(sub.c) FROM (
                    SELECT
                        COUNT(DISTINCT p.game_id) AS c,
                        champ_id
                    FROM {stats_table} p
                    WHERE
                        p.disc_id=?
                        AND p.doinks IS NOT NULL
                    GROUP BY champ_id
                ) sub
            """
            return self.execute_query(query, disc_id).fetchone()

    def get_max_doinks_details(self, game):
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)

        with self:
            query = f"""
                SELECT 
                    MAX(counts.c),
                    counts.disc_id
                FROM (
                    SELECT
                        p.disc_id,
                        COUNT(*) AS c
                    FROM
                        {stats_table} AS p, 
                        {users_table} AS u
                    WHERE
                        doinks IS NOT NULL
                        AND u.disc_id = p.disc_id
                        AND u.active = 1
                    GROUP BY p.disc_id
                ) counts
            """
            return self.execute_query(query).fetchone()

    def get_doinks_reason_counts(self, game):
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)

        with self:
            query_doinks_multis = f"""
                SELECT doinks
                FROM
                    {stats_table} AS p,
                    {users_table} AS u
                WHERE
                    doinks IS NOT NULL
                    AND u.disc_id = p.disc_id
                    AND u.active = 1
            """
            doinks_reasons_data = self.execute_query(query_doinks_multis).fetchall()
            if doinks_reasons_data == []:
                return None

            doinks_counts = [0 for _ in range(len(doinks_reasons_data[0][0]))]
            for reason in doinks_reasons_data:
                for index, c in enumerate(reason[0]):
                    if c == "1":
                        doinks_counts[index] += 1

            return doinks_counts

    def get_game_ids(self, game):
        games_table = self._get_games_table(game)
        query = f"SELECT game_id FROM {games_table}"
        with self:
            return self.execute_query(query).fetchall()

    def get_recent_intfars_and_doinks(self, game):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)

        with self:
            query = f"""
                SELECT
                    g.game_id,
                    timestamp,
                    p.disc_id,
                    doinks,
                    intfar_id,
                    intfar_reason
                FROM {stats_table} AS p
                LEFT JOIN {games_table} AS g
                    ON p.game_id = g.game_id
                LEFT JOIN {users_table} AS u
                    ON p.disc_id = u.disc_id
                WHERE u.active = 1
                GROUP BY p.game_id, p.disc_id
                ORDER BY timestamp ASC
            """
            return self.execute_query(query).fetchall()

    def get_delimeter(self, time_after, time_before, guild_id, other_key=None, other_param=None, prefix=None):
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

    def get_recent_game_results(self, game, time_after=None, time_before=None, guild_id=None):
        games_table = self._get_games_table(game)
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id)

        query = f"""
            SELECT win
            FROM {games_table}
            {delim_str}
            ORDER BY timestamp DESC
        """
        with self:
            return [x[0] for x in self.execute_query(query, *params).fetchall()]

    def get_games_results(self, game, time_after=None, time_before=None, guild_id=None):
        games_table = self._get_games_table(game)
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id)

        query = f"""
            SELECT
                win,
                timestamp
            FROM {games_table}
            {delim_str}
            ORDER BY timestamp
        """

        with self:
            return self.execute_query(query, *params).fetchall()

    def get_games_count(self, game, disc_id=None, time_after=None, time_before=None, guild_id=None):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)
        delim_str_1, params_1 = self.get_delimeter(time_after, time_before, guild_id, prefix="AND")
        delim_str_2, params_2 = self.get_delimeter(time_after, time_before, guild_id, "p.disc_id", disc_id, prefix="AND")

        query = f"""
            WITH game_cte AS (
                SELECT
                    p.game_id,
                    p.disc_id,
                    g.guild_id,
                    g.win,
                    g.timestamp
                FROM {games_table} AS g
                INNER JOIN {stats_table} AS p
                ON p.game_id = g.game_id
                INNER JOIN {users_table} AS u
                ON u.disc_id = p.disc_id
                WHERE
                    u.active = 1
                    {delim_str_1}
                    {delim_str_2}
            )
            SELECT
                games.c,
                games.t,
                wins.c,
                guilds.c
            FROM (
                SELECT
                    COUNT(DISTINCT game_id) AS c,
                    MIN(timestamp) AS t
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

    def get_longest_game(self, game, time_after=None, time_before=None, guild_id=None):
        games_table = self._get_games_table(game)
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id)

        query = f"""
            SELECT
                MAX(duration),
                timestamp
            FROM {games_table}
            {delim_str}
        """

        with self:
            return self.execute_query(query, *params).fetchone()

    def get_league_champs_played(self, disc_id=None, time_after=None, time_before=None, guild_id=None):
        game = "lol"
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "disc_id", disc_id)

        query = f"""
            SELECT COUNT(DISTINCT champ_id)
            FROM {stats_table} AS p
            JOIN {games_table} g
                ON p.game_id = g.game_id
                {delim_str}
        """

        with self:
            return self.execute_query(query, *params).fetchone()[0]

    def get_champ_with_most_intfars(self, disc_id):
        game = "lol"
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)

        query = f"""
            SELECT sub.champ_id, MAX(sub.c) FROM (
                SELECT
                    COUNT(DISTINCT p.game_id) AS c,
                    champ_id FROM {games_table} AS g
                JOIN {stats_table} AS p
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

    def get_intfar_count(self, game, disc_id=None, time_after=None, time_before=None, guild_id=None):
        games_table = self._get_games_table(game)
        users_table = self._get_users_table(game)
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "disc_id", disc_id, "AND")

        query_intfars = f"""
            SELECT SUM(sub.intfars)
            FROM (
                SELECT COUNT(*) AS intfars
                FROM (
                    SELECT DISTINCT
                        g.game_id,
                        intfar_id
                    FROM {games_table} AS g
                    LEFT JOIN {users_table} u
                    ON u.disc_id=intfar_id
                  WHERE
                    intfar_id IS NOT NULL
                    AND u.active = 1{delim_str}
                ) sub_2
                GROUP BY sub_2.intfar_id
            ) sub
        """

        with self:
            intfars = self.execute_query(query_intfars, *params).fetchone()
            return (intfars[0] if intfars is not None else 0) or 0

    def get_intfar_reason_counts(self, game):
        games_table = self._get_games_table(game)
        users_table = self._get_users_table(game)

        query_intfar_multis = f"""
            SELECT intfar_reason
            FROM {games_table}
            LEFT JOIN {users_table} u
                ON u.disc_id=intfar_id
            WHERE
                intfar_id IS NOT NULL
                AND u.active=1
            GROUP BY game_id
        """

        with self:
            intfar_multis_data = self.execute_query(query_intfar_multis).fetchall()
            if intfar_multis_data == []:
                return None, None

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

    def get_total_winrate(self, game, disc_id):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)

        query = f"""
            SELECT (wins.c / played.c) * 100 FROM (
                SELECT CAST(COUNT(DISTINCT g.game_id) as real) AS c
                FROM {games_table} AS g
                LEFT JOIN {stats_table} AS p
                    ON g.game_id = p.game_id
                WHERE
                    disc_id = ?
                    AND win=1
            ) wins,
            (
                SELECT CAST(COUNT(DISTINCT g.game_id) as real) AS c
                FROM {games_table} AS g
                LEFT JOIN {stats_table} AS p
                    ON g.game_id = p.game_id
                WHERE disc_id = ?
            ) played
        """
    
        with self:
            return self.execute_query(query, disc_id, disc_id).fetchone()[0]

    def get_league_champ_winrate(self, disc_id, champ_id):
        game = "lol"
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)

        query = f"""
            SELECT
                (wins.c / played.c) * 100 AS wr,
                played.c AS gs
            FROM (
                SELECT
                    CAST(COALESCE(COUNT(DISTINCT g.game_id), 0) as real) AS c,
                    champ_id
                FROM {games_table} AS g
                LEFT JOIN {stats_table} AS p
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
                FROM {games_table} AS g
                LEFT JOIN {stats_table} AS p
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

    def get_min_or_max_league_winrate_champ(self, disc_id, best, included_champs=None, return_top_n=1, min_games=10):
        game = "lol"
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)

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
                    FROM {games_table} AS g
                    LEFT JOIN {stats_table} AS p 
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
                FROM {games_table} AS g
                LEFT JOIN {stats_table} AS p
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
                result = result[0]

            if result is None and min_games == 10:
                # If no champs are found with min 10 games, try again with 5.
                return self.get_min_or_max_league_winrate_champ(disc_id, best, included_champs, return_top_n, min_games=5)

            return result

    def get_csgo_map_winrate(self, disc_id, map_id):
        pass # TODO: Implement

    def get_winrate_relation(self, game, disc_id, best, min_games=10):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)

        query_games = f"""
            SELECT
                p2.disc_id,
                Count(*) as c
            FROM
                {stats_table} p1,
                {stats_table} p2
            WHERE
                p1.disc_id != p2.disc_id
                AND p1.game_id = p2.game_id
                AND p1.disc_id = ?
            GROUP BY
                p1.disc_id,
                p2.disc_id
            ORDER BY c DESC
        """
        query_wins = f"""
            SELECT
                p2.disc_id,
                Count(*) as c
            FROM
                {games_table} AS g,
                {stats_table} p1,
                {stats_table} p2
            WHERE
                p1.disc_id != p2.disc_id
                AND g.game_id = p1.game_id
                AND g.game_id = p2.game_id
                AND p1.game_id = p2.game_id
                AND p1.disc_id = ?
                AND win = 1
            GROUP BY
                p1.disc_id,
                p2.disc_id
            ORDER BY c DESC
        """

        with self:
            games_with_person = {}
            wins_with_person = {}
            for part_id, wins in self.execute_query(query_wins, disc_id):
                if disc_id == part_id or not self.user_exists(game, part_id):
                    continue
                wins_with_person[part_id] = wins

            for part_id, games in self.execute_query(query_games, disc_id):
                if self.user_exists(game, part_id):
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

    def get_played_league_champs(self, disc_id):
        game = "lol"
        stats_table = self._get_participants_table(game)

        with self:
            query = f"SELECT DISTINCT champ_id FROM {stats_table} WHERE disc_id=?"
            return self.execute_query(query, disc_id).fetchall()

    def get_meta_stats(self, game):
        stats_table = self._get_participants_table(game)
        query_persons = f"SELECT Count(*) FROM {stats_table} as p GROUP BY game_id"

        users = (len(self.users_by_game[game]),)
        with self:
            game_data = self.get_games_count(game)
            longest_game = self.get_longest_game(game)
            intfar_data = self.get_intfar_count(game)
            doinks_data = self.get_doinks_count(game)
            persons_counts = self.execute_query(query_persons)
            persons_count = {2: 0, 3: 0, 4: 0, 5: 0}
            for persons in persons_counts:
                persons_count[persons[0]] += 1
            twos_ratio = int((persons_count[2] / game_data[0]) * 100)
            threes_ratio = int((persons_count[3] / game_data[0]) * 100)
            fours_ratio = int((persons_count[4] / game_data[0]) * 100)
            fives_ratio = int((persons_count[5] / game_data[0]) * 100)
            games_ratios = [twos_ratio, threes_ratio, fours_ratio, fives_ratio]

            intfar_counts, intfar_multis_counts = self.get_intfar_reason_counts(game)
            intfar_ratios = [(count / intfar_data) * 100 for count in intfar_counts]
            intfar_multis_ratios = [(count / intfar_data) * 100 for count in intfar_multis_counts]

            return (
                game_data + longest_game + users + doinks_data +
                (intfar_data, games_ratios, intfar_ratios, intfar_multis_ratios)
            )

    def get_monthly_delimiter(self):
        tz_cph = TimeZone()
        curr_time = datetime.now(tz_cph)
        current_month = curr_time.month
        if curr_time.day > 1 or curr_time.hour > self.config.hour_of_ifotm_announce:
            # Get Int-Far stats for current month.
            start_of_month = curr_time.replace(day=1, hour=0, minute=0, second=0)
            min_timestamp = int(start_of_month.timestamp())
        else:
            # Get Int-Far stats for previous month.
            prev_month = 12 if current_month == 1 else current_month - 1
            prev_year = curr_time.year if prev_month != 12 else curr_time.year - 1
            prev_time = curr_time.replace(prev_year, prev_month, 1,
                                          0, 0, 0, 0, tz_cph)
            min_timestamp = int(prev_time.timestamp())

        max_timestamp = int(curr_time.timestamp())
        return f"timestamp > {min_timestamp} AND timestamp < {max_timestamp}"

    def get_intfars_of_the_month(self, game):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)
        delim_str = self.get_monthly_delimiter()

        query_intfars = f"""
            SELECT intfar_id
            FROM {games_table} AS g
            LEFT JOIN {users_table} AS u
                ON u.disc_id = intfar_id
            WHERE
                intfar_id IS NOT NULL
                AND {delim_str}
                AND u.active = 1
            GROUP BY g.game_id
        """
        query_games = f"""
            SELECT p.disc_id
            FROM
                {games_table} AS g
            LEFT JOIN {stats_table} AS p
                ON g.game_id = p.game_id
            LEFT JOIN {users_table} AS u
                ON u.disc_id=p.disc_id
            WHERE
                {delim_str}
                AND u.active = 1
            GROUP BY
                g.game_id,
                p.disc_id
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

    def get_longest_intfar_streak(self, game, disc_id):
        games_table = self._get_games_table(game)

        query = f"""
            SELECT
                intfar_id,
                timestamp
            FROM {games_table}
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

    def get_longest_no_intfar_streak(self, game, disc_id):
        if not self.user_exists(game, disc_id):
            return 0

        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)

        query = f"""
            SELECT
                intfar_id,
                timestamp
            FROM {stats_table} AS p
            LEFT JOIN {games_table} AS g
                ON g.game_id = p.game_id
            WHERE p.disc_id = ?
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

    def get_current_intfar_streak(self, game):
        games_table = self._get_games_table(game)
        users_table = self._get_users_table(game)

        query = f"""
            SELECT intfar_id
            FROM {games_table}
            LEFT JOIN {users_table} AS u
                ON intfar_id=u.disc_id
            WHERE u.active = 1
            GROUP BY game_id
            ORDER BY game_id DESC
        """

        with self:
            int_fars = self.execute_query(query).fetchall()
            prev_intfar = int_fars[0][0]
            for count, int_far in enumerate(int_fars[1:], start=1):
                if int_far[0] is None or prev_intfar != int_far[0]:
                    return count, prev_intfar

            return len(int_fars), prev_intfar # All the Int-Fars is the current int-far!

    def get_longest_win_or_loss_streak(self, game, disc_id, win):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)

        query = f"""
            SELECT g.win
            FROM {games_table} AS g
            INNER JOIN {stats_table} AS p
                ON p.game_id = g.game_id
            INNER JOIN {users_table} AS u
                ON p.disc_id = u.disc_id
            WHERE
                p.disc_id = ?
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

    def get_current_win_or_loss_streak(self, game, disc_id, win, offset=0):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)

        query = f"""
            SELECT g.win
            FROM {games_table} AS g
            INNER JOIN {stats_table} AS p
                ON p.game_id = g.game_id
            INNER JOIN {users_table} AS u
                ON p.disc_id = u.disc_id
            WHERE
                p.disc_id = ?
                AND u.active
            GROUP BY g.game_id
            ORDER BY g.game_id DESC
        """

        with self:
            games = self.execute_query(query, disc_id).fetchall()

            count_offset = 1 if offset == 0 else 0

            for count, row in enumerate(games[offset:], start=count_offset):
                if row[0] != win:
                    return count

            total_offset = -offset if offset > 0 else 1

            return len(games) + total_offset

    def get_max_intfar_details(self, game):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)

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
                    FROM {games_table}
                    WHERE intfar_id IS NOT NULL
                    GROUP BY intfar_id
                ) AS intfar_counts,
                (
                    SELECT
                        disc_id,
                        CAST(Count(*) as real) as c
                    FROM {stats_table}
                    GROUP BY disc_id
                ) AS games_counts
                WHERE
                    intfar_id = disc_id
                    AND games_counts.c > 10
            ) AS pcts
            INNER JOIN {users_table} AS u
                ON u.disc_id = pcts.intboi
            WHERE u.active = 1
        """

        with self:
            return self.execute_query(query).fetchone()

    def get_intfar_stats(self, game, disc_id, monthly=False, time_after=None, time_before=None, guild_id=None):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        params_1 = []
        params_2 = []

        if monthly:
            monthly_delim = self.get_monthly_delimiter()
            if disc_id is not None:
                delim_str_1 = f" WHERE disc_id = ? AND {monthly_delim}"
                delim_str_2 = f" WHERE intfar_id = ? AND {monthly_delim}"
                params_1 = [disc_id]
                params_2 = [disc_id]
            else:
                delim_str_1 = f" WHERE {monthly_delim}"
                delim_str_2 = f" WHERE {monthly_delim}"
        else:
            delim_str_1, params_1 = self.get_delimeter(time_after, time_before, guild_id, "disc_id", disc_id)
            delim_str_2, params_2 = self.get_delimeter(time_after, time_before, guild_id, "intfar_id", disc_id)

        query_total = f"""
            SELECT Count(*)
            FROM {games_table} AS g
            JOIN {stats_table} AS p
                ON g.game_id = p.game_id
            {delim_str_1}
        """
        query_intfar = f"""
            SELECT intfar_reason
            FROM {games_table} AS g
            JOIN {stats_table} AS p 
                ON g.game_id = p.game_id
            {delim_str_2}
            GROUP BY g.game_id
        """

        with self:
            total_games = self.execute_query(query_total, *params_1).fetchone()[0]
            intfar_games = self.execute_query(query_intfar, *params_2).fetchall()
            return total_games, intfar_games

    def get_intfar_relations(self, game, disc_id):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)

        query_games = f"""
            SELECT
                p2.disc_id,
                COUNT(*) AS c
            FROM
                {stats_table} AS p1,
                {stats_table} AS p2
            WHERE
                p1.disc_id != p2.disc_id
                AND p1.game_id = p2.game_id
                AND p1.disc_id = ?
            GROUP BY
                p1.disc_id,
                p2.disc_id
            ORDER BY c DESC
        """
        query_intfars = f"""
            SELECT
                disc_id,
                COUNT(*) AS c
            FROM
                {games_table} AS g,
                {stats_table} AS p
            WHERE
                intfar_id IS NOT NULL
                AND g.game_id = p.game_id
                AND intfar_id = ?
            GROUP BY disc_id
            ORDER BY c DESC
        """

        with self:
            games_with_person = {}
            intfars_with_person = {}

            for part_id, intfars in self.execute_query(query_intfars, disc_id):
                if disc_id == part_id or not self.user_exists(game, part_id):
                    continue
                intfars_with_person[part_id] = intfars

            for part_id, games in self.execute_query(query_games, disc_id):
                if self.user_exists(game, part_id):
                    games_with_person[part_id] = games

            return games_with_person, intfars_with_person

    def get_doinks_stats(self, game, disc_id=None, time_after=None, time_before=None, guild_id=None):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "p.disc_id", disc_id, "AND")

        query = f"""
            SELECT doinks
            FROM {stats_table} AS p
            LEFT JOIN {users_table} AS u
                ON u.disc_id = p.disc_id
            LEFT JOIN {games_table} AS g
                ON p.game_id = g.game_id
            WHERE
                doinks IS NOT NULL
                AND u.active = 1
                {delim_str}
            GROUP BY g.game_id
        """

        with self:
            return self.execute_query(query, *params).fetchall()

    def get_doinks_relations(self, game, disc_id):
        stats_table = self._get_participants_table(game)
        query_games = f"""
            SELECT
                p2.disc_id,
                Count(*) as c
            FROM
                {stats_table} p1,
                {stats_table} p2
            WHERE
                p1.disc_id != p2.disc_id
                AND p1.game_id = p2.game_id
                AND p1.disc_id = ?
            GROUP BY
                p1.disc_id,
                p2.disc_id
            ORDER BY c DESC
        """
        query_doinks = f"""
            SELECT
                p2.disc_id,
                Count(*) as c
            FROM
                {stats_table} p1,
                {stats_table} p2
            WHERE
                p1.disc_id != p2.disc_id
                AND p1.game_id = p2.game_id
                AND p1.doinks IS NOT NULL
                AND p1.disc_id = ?
            GROUP BY
                p1.disc_id,
                p2.disc_id
            ORDER BY c DESC
        """

        with self:
            games_with_person = {}
            doinks_with_person = {}

            for part_id, doinks in self.execute_query(query_doinks, disc_id):
                if disc_id == part_id or not self.user_exists(game, part_id):
                    continue
                doinks_with_person[part_id] = doinks

            for part_id, games in self.execute_query(query_games, disc_id):
                if self.user_exists(game, part_id):
                    games_with_person[part_id] = games

            return games_with_person, doinks_with_person

    def get_performance_score(self, game, disc_id=None):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)
        users_table = self._get_users_table(game)
        intfar_weight = 1
        doinks_weight = 1
        winrate_weight = 2
        total = 4
        performance_range = 10
        equation = (
            f"(((1 - intfars.c / played.c) * {intfar_weight} + " +
            f"(doinks.c / played.c) * {doinks_weight} + " +
            f"(wins.c / played.c) * {winrate_weight}) / {total}) * {performance_range}"
        )

        query_outer = "SELECT sub.user, sub.score FROM\n("

        query_select = f"   SELECT played.disc_id AS user, {equation} AS score FROM "

        query_subs = f"""
                (
                    SELECT
                        CAST(COUNT(DISTINCT g.game_id) AS real) AS c,
                        disc_id
                    FROM {games_table} AS g
                    JOIN {stats_table} AS p
                        ON g.game_id = p.game_id
                    GROUP BY disc_id
                ) played,
                (
                    SELECT
                        CAST(COUNT(DISTINCT g.game_id) AS real) AS c,
                        disc_id
                    FROM {games_table} AS g
                    JOIN {stats_table} AS p
                        ON g.game_id = p.game_id
                    WHERE win=1
                    GROUP BY disc_id
                ) wins,
                (
                    SELECT
                        CAST(COUNT(*) AS real) AS c,
                        intfar_id
                    FROM {games_table} AS g
                    GROUP BY intfar_id
                ) intfars,
                (
                    SELECT
                        CAST(SUM(LENGTH(REPLACE(doinks_sub.doinks, '0', ''))) AS real) AS c,
                        doinks_sub.disc_id
                    FROM (
                        SELECT
                            DISTINCT game_id,
                            doinks,
                            disc_id
                        FROM {stats_table}
                        WHERE doinks IS NOT NULL
                    ) doinks_sub
                    GROUP BY doinks_sub.disc_id
                ) doinks
                WHERE
                    played.disc_id = wins.disc_id
                    AND played.disc_id = intfars.intfar_id
                    AND played.disc_id = doinks.disc_id
                    AND wins.disc_id = intfars.intfar_id
                    AND wins.disc_id = doinks.disc_id
                    AND intfars.intfar_id = doinks.disc_id
            ) sub
            LEFT JOIN {users_table} AS u
                ON sub.user = u.disc_id
            WHERE u.active = 1
            GROUP BY sub.user
            ORDER BY sub.score DESC
        """

        query_full = query_outer + query_select + query_subs

        with self:
            performance_scores = self.execute_query(query_full).fetchall()
            if disc_id is None:
                return performance_scores
            
            rank = 0
            score = 0
            for index, (score_id, score_value) in enumerate(performance_scores):
                if score_id == disc_id:
                    rank = index
                    score = score_value
                    break

            return score, rank+1, len(performance_scores)

    def get_stat_data(self, parsed_game_stats: GameStats, stat: str, reverse_order=False):
        (
            min_stat_id, min_stat,
            max_stat_id, max_stat
        ) = get_outlier_stat(
            parsed_game_stats.filtered_player_stats,
            stat,
            reverse_order=reverse_order
        )

        (
            best_ever_id,
            best_ever,
            _
        ) = self.get_most_extreme_stat(parsed_game_stats.game, stat, stat != "deaths")

        (
            worst_ever_id,
            worst_ever,
            _
        ) = self.get_most_extreme_stat(parsed_game_stats.game, stat, stat == "deaths")

        return min_stat_id, min_stat, max_stat_id, max_stat, best_ever, best_ever_id, worst_ever, worst_ever_id

    def record_stats(self, parsed_game_stats: GameStats):
        beaten_records_best = []
        beaten_records_worst = []

        for stat in parsed_game_stats.filtered_player_stats[0].STAT_QUANTITY_DESC():
            reverse_order = stat == "deaths"
            (
                min_id, min_value, max_id, max_value,
                prev_best, prev_best_id, prev_worst, prev_worst_id
            ) = self.get_stat_data(parsed_game_stats, stat, reverse_order)

            if reverse_order: # Stat is 'deaths'.
                if None not in (prev_best, min_value) and min_value < prev_best: # Fewest deaths ever has been reached.
                    beaten_records_best.append((stat, min_value, min_id, prev_best, prev_best_id))
                elif None not in(prev_worst, max_value) and max_value > prev_worst: # Most deaths ever has been reached.
                    beaten_records_worst.append((stat, max_value, max_id, prev_worst, prev_worst_id))
            else: # Stat is any other stat.
                if None not in (prev_best, max_value) and max_value > prev_best: # A new best has been set for a stat.
                    beaten_records_best.append((stat, max_value, max_id, prev_best, prev_best_id))
                elif None not in (prev_worst, min_value) and min_value < prev_worst: # A new worst has been set for a stat.
                    beaten_records_worst.append((stat, min_value, min_id, prev_worst, prev_worst_id))

        game_insert_str = ",\n".join(parsed_game_stats.STATS_TO_SAVE())
        game_insert_qms = ",".join(["?"] * len(parsed_game_stats.STATS_TO_SAVE()))

        stats_insert_str = ",\n".join(parsed_game_stats.filtered_player_stats[0].STATS_TO_SAVE())
        stats_insert_qms = ",".join(["?"] * len(parsed_game_stats.filtered_player_stats[0].STATS_TO_SAVE()))

        game_insert_values = [getattr(parsed_game_stats, stat) for stat in parsed_game_stats.STATS_TO_SAVE()]

        games_table = self._get_games_table(parsed_game_stats.game)
        stats_table = self._get_participants_table(parsed_game_stats.game)

        with self:
            query_game = f"""
                INSERT INTO {games_table}(
                    {game_insert_str}
                )
                VALUES ({game_insert_qms})
            """

            self.execute_query(
                query_game, *game_insert_values
            )

            query = f"""
                INSERT INTO {stats_table}(
                    {stats_insert_str}
                )
                VALUES ({stats_insert_qms})
            """

            for player_stats in parsed_game_stats.filtered_player_stats:
                stat_insert_values = [getattr(player_stats, stat) for stat in player_stats.STATS_TO_SAVE()]
                logger.debug(f"Saving participant data:\n", stat_insert_values)

                self.execute_query(query, *stat_insert_values)

        return beaten_records_best, beaten_records_worst

    def save_missed_game(self, game, game_id, guild_id, timestamp):
        query = "INSERT INTO missed_games VALUES (?, ?, ?, ?)"
        with self:
            self.execute_query(query, game_id, game, guild_id, timestamp)

    def get_missed_games(self, game):
        query = "SELECT game_id, guild_id FROM missed_games WHERE game = ?"
        with self:
            return self.execute_query(query, game).fetchall()

    def remove_missed_game(self, game, game_id):
        query = "DELETE FROM missed_games WHERE game_id=? AND game=?"
        with self:
            self.execute_query(query, game_id, game)

    def get_game_stats(self, game, stats, game_id=None, time_after=None, time_before=None, guild_id=None):
        games_table = self._get_games_table(game)

        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "g.game_id", game_id)

        stats_to_select = ", ".join(stats)

        query = f"""
            SELECT
                {stats_to_select}
            FROM {games_table} AS g
            {delim_str}
        """

        with self:
            return self.execute_query(query, *params).fetchall()

    def get_player_stats(self, game, stats, game_id=None, disc_id=None, time_after=None, time_before=None, guild_id=None):
        games_table = self._get_games_table(game)
        stats_table = self._get_participants_table(game)

        prefix = "WHERE"
        game_id_delimeter = ""
        params = []
        if game_id is not None:
            game_id_delimeter = "WHERE game_id=?"
            params = [game_id]
            prefix = "AND"
 
        delim_str, delim_params = self.get_delimeter(time_after, time_before, guild_id, "disc_id", disc_id, prefix)
        params = params + delim_params

        stats_to_select = ", ".join(stats)
        if disc_id is None:
            stats_to_select = f"disc_id, {stats_to_select}"

        query = f"""
            SELECT
                {stats_to_select}
            FROM {stats_table} AS p
            INNER JOIN {games_table} AS g
            ON g.game_id = p.game_id
            {game_id_delimeter}
            {delim_str}
        """

        with self:
            return self.execute_query(query, *params).fetchall()

    def create_backup(self):
        backup_name = "resources/database_backup.db"
        try:
            # Remove old backup if it exists.
            if os.path.exists(backup_name):
                os.remove(backup_name)

            copyfile(self.config.database, backup_name)
        except (OSError, IOError) as exc:
            raise DBException(exc.args[0])

    def generate_ticket_id(self, disc_id):
        with self:
            query = "SELECT MAX(ticket) FROM bets WHERE better_id=?"
            curr_id = self.execute_query(query, disc_id).fetchone()
            if curr_id is None or curr_id[0] is None:
                return 0
            return curr_id[0] + 1

    def get_bets(self, game, only_active, disc_id=None, guild_id=None):
        users_table = self._get_users_table(game)

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
                LEFT JOIN {users_table} AS u
                    ON u.disc_id = better_id
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
                AND u.active=1
                AND game = '{game}'
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

    def get_bet_id(self, game, disc_id, guild_id, event_id, target=None, ticket=None):
        with self:
            if ticket is None:
                query = """
                    SELECT id
                    FROM bets
                    WHERE
                        better_id = ?
                        AND guild_id = ?
                        AND event_id = ?
                        AND game = ?
                        AND (target=? OR target IS NULL)
                        AND result = 0
                """
                params = [disc_id, guild_id, event_id, game, target]
            else:
                query = """
                    SELECT id
                    FROM bets
                    WHERE
                        better_id = ?
                        AND guild_id = ?
                        AND game = ?
                        AND ticket = ?
                        AND result = 0
                """
                params = [disc_id, guild_id, game, ticket]

            result = self.execute_query(query, *params).fetchone()

            return None if result is None else result[0]

    def get_better_id(self, bet_id):
        if bet_id is not None:
            bet_id = int(bet_id)

        with self:
            query = "SELECT better_id FROM bets WHERE id=?"
            result = self.execute_query(query, bet_id).fetchone()

            return None if result is None else result[0]

    def make_bet(self, game, disc_id, guild_id, event_id, amount, game_duration, target_person=None, ticket=None):
        query_bet = """
            INSERT INTO bets(
                better_id,
                guild_id,
                game,
                timestamp,
                event_id,
                amount,
                game_duration,
                target,
                ticket,
                result
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with self:
            self.update_token_balance(disc_id, amount, False)
            self.execute_query(
                query_bet,
                disc_id,
                guild_id,
                game,
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
            self.update_token_balance(disc_id, amount, True)

            return amount

    def cancel_multi_bet(self, ticket, disc_id):
        query_del = "DELETE FROM bets WHERE better_id=? AND ticket=?"
        query_amount = "SELECT amount FROM bets WHERE better_id=? AND ticket=?"

        with self:
            amounts = self.execute_query(query_amount, disc_id, ticket).fetchall()
            amount_total = sum(x[0] for x in amounts)
            self.execute_query(query_del, disc_id, ticket)
            self.update_token_balance(disc_id, amount_total, True)

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

    def get_event_sound(self, game, disc_id, event):
        query = "SELECT sound FROM event_sounds WHERE disc_id=? AND game=? AND event=?"

        with self:
            result = self.execute_query(query, disc_id, game, event).fetchone()

            return result[0] if result is not None else None

    def set_event_sound(self, game, disc_id, sound, event):
        query = "REPLACE INTO event_sounds(disc_id, game, sound, event) VALUES (?, ?, ?, ?)"

        with self:
            self.execute_query(query, disc_id, game, sound, event)

    def remove_event_sound(self, game, disc_id, event):
        query = "DELETE FROM event_sounds WHERE disc_id=? AND game=? AND event=?"

        with self:
            self.execute_query( query, disc_id, game, event)

    def create_list(self, disc_id, name):
        query = "INSERT INTO champ_lists(name, owner_id) VALUES (?, ?)"

        with self:
            try:
                self.execute_query( query, name, disc_id)
                return True, self.execute_query("SELECT last_insert_rowid()").fetchone()[0]
            except DatabaseError: # Duplicate champion inserted.
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
            except DatabaseError: # Duplicate champion inserted.
                return False

    def add_items_to_list(self, items):
        query = "INSERT INTO list_items(champ_id, list_id) VALUES (?, ?)"

        with self:
            try:
                self.execute_query(query, *items)
                return True
            except DatabaseError: # Duplicate champion inserted.
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

    def clear_tables(self):
        with self:
            query_tables = "SELECT name FROM sqlite_master WHERE type='table'"
            tables = self.execute_query(query_tables).fetchall()

            for table in tables:
                query = f"DELETE FROM {table[0]}"
                self.execute_query(query, commit=False)

            self.connection.commit()
