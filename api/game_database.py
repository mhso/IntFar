from mhooge_flask.database import SQLiteDatabase, DBException
from api.util import SUPPORTED_GAMES
from api.config import Config
from api.user import User

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

    def get_all_registered_users(self):
        with self:
            query = "SELECT disc_id, secret FROM users"
            values = self.execute_query(query).fetchall()
            games_user_info = {x[0]: {"disc_id": x[0], "secret": x[1]} for x in values}

            all_params = ["disc_id", "ingame_name", "ingame_id"] + list(self.game_user_params) + ["main", "active"]
            params_str = ", ".join(all_params)
            query = f"SELECT {params_str} FROM users ORDER BY main DESC"
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

    def user_exists(self, discord_id):
        return discord_id in self.game_users

    def add_user(self, game, discord_id, **game_params):
        status = ""
        status_code = 0
        try:
            with self:
                query = f"SELECT * FROM users WHERE disc_id=? AND active=0"
                inactive_accounts = self.execute_query(query, discord_id).fetchall()

                if inactive_accounts != []:
                    # Check if user has been registered before, and is now re-registering.
                    query = f"UPDATE users SET active=1 WHERE disc_id=?"
                    self.execute_query(query, discord_id)
                    status = "Welcome back to the Int-Far:tm: Tracker:tm:, my lost son :hearts:"

                    reduced_params = dict(game_params)
                    del reduced_params["ingame_name"]
                    del reduced_params["ingame_id"]

                    self.game_users[game][discord_id] = self.get_all_registered_users(game, **reduced_params)
                    status_code = 3 # User reactivated

                else:
                    new_user = not any(self.user_exists(game_name, discord_id) for game_name in self.game_users.keys())
                    main = 1

                    user_info = self.game_users[game].get(discord_id)

                    game_user_name = game_params["ingame_name"]
                    game_user_id = game_params["ingame_id"]

                    parameter_list = ["disc_id"] + list(game_params.keys()) + ["main", "active"]
                    questionmarks = ", ".join("?" for _ in range(len(parameter_list) - 1))
                    parameter_names = ",\n".join(parameter_list)
                    query = f"""
                        INSERT INTO users (
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
                        self.game_users[game][discord_id] = User(**user_params)
                        status = f"User '{game_user_name}' with ID '{game_user_id}' succesfully added for {SUPPORTED_GAMES[game]}!"

                    values_list = [discord_id] + list(game_params.values()) + [main]
                    self.execute_query(query, *values_list)

                    if new_user:
                        # Only create betting balance table if user is new.
                        query = "INSERT INTO betting_balance VALUES (?, ?)"

                        self.execute_query(query, discord_id, 100)

                        status_code = 1 # New user added
                    else:
                        status_code = 2 # Smurf added

        except DBException:
            return (0, "A user with that summoner name is already registered!")

        return (status_code, status)

    def remove_user(self, disc_id):
        with self:
            query = f"UPDATE users SET active=0 WHERE disc_id=?"
            self.execute_query(query, disc_id)

        del self.game_users[disc_id]

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

    def get_latest_game(self, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id)

        query_games = f"SELECT MAX(timestamp), win, intfar_id, intfar_reason FROM games{delim_str}"
        query_doinks = f"""
            SELECT
                timestamp,
                disc_id,
                doinks
            FROM (
               SELECT MAX(timestamp) AS t
               FROM games{delim_str}
            ) sub_1, participants AS p
            JOIN games AS g
            ON p.game_id = g.game_id
            WHERE doinks IS NOT NULL AND timestamp = sub_1.t
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
                    p.disc_id,
                    {aggregator}({stat}),
                    game_id
                FROM participants AS p
                JOIN users AS u
                ON u.disc_id = p.disc_id
                WHERE u.active = 1
            """

            return self.execute_query(query).fetchone()
