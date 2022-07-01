import os
from shutil import copyfile
from datetime import datetime
import sqlite3
from sqlite3 import DatabaseError, OperationalError, ProgrammingError
from contextlib import closing

from api import game_stats
from api.util import TimeZone, generate_user_secret, DOINKS_REASONS, STAT_COMMANDS

class DBException(OperationalError, ProgrammingError):
    def __init__(self, *args):
        super().__init__(args)

class Database:
    def __init__(self, config):
        self.config = config
        self.summoners = []
        self.persistent_connection = None
        if not os.path.exists(self.config.database):
            self.create_database()

        # Populate summoner names and ids lists with currently registered summoners.
        users = self.get_all_registered_users()
        user_entries = {x[0]: ([], []) for x in users}
        for disc_id, summ_name, summ_id, _ in users:
            user_entries[disc_id][0].append(summ_name)
            user_entries[disc_id][1].append(summ_id)

        for k, v in user_entries.items():
            self.summoners.append((k, v[0], v[1]))

        self.summoners.sort(key=lambda x: x[0])

    def get_connection(self):
        if self.persistent_connection is not None:
            return self.persistent_connection
        return closing(sqlite3.connect(self.config.database))

    def start_persistent_connection(self):
        self.persistent_connection = sqlite3.connect(self.config.database)

    def close_persistent_connection(self):
        self.persistent_connection.close()
        self.persistent_connection = None

    def execute_query(self, db, query, query_params=None, commit=True):
        try:
            if query_params is None:
                cursor = db.cursor().execute(query)
            else:
                if isinstance(query_params, list):
                    cursor = db.cursor().executemany(query, query_params)
                else:
                    cursor = db.cursor().execute(query, query_params)
            if commit:
                db.commit()
            return cursor
        except (OperationalError, ProgrammingError, DatabaseError) as exc:
            raise DBException(exc.args)

    def create_database(self):
        with self.get_connection() as db:
            with open("resources/schema.sql", "r") as f:
                db.cursor().executescript(f.read())
            db.commit()

    def user_exists(self, discord_id):
        for disc_id, _, _ in self.summoners:
            if discord_id == disc_id:
                return True
        return False

    def get_registered_user(self, summ_name):
        with self.get_connection() as db:
            return self.execute_query(
                db, (
                    "SELECT disc_id, summ_name, summ_id FROM registered_summoners " +
                    "WHERE summ_name=?"
                ), (summ_name,)
            ).fetchone()

    def get_all_registered_users(self):
        with self.get_connection() as db:
            query = (
                "SELECT disc_id, summ_name, summ_id, secret " +
                "FROM registered_summoners WHERE active=1"
            )
            return self.execute_query(db, query).fetchall()

    def get_client_secret(self, disc_id):
        with self.get_connection() as db:
            return self.execute_query(
                db, ("SELECT secret FROM registered_summoners WHERE disc_id=?"),
                (disc_id,)
            ).fetchone()[0]

    def get_user_from_secret(self, secret):
        with self.get_connection() as db:
            return self.execute_query(
                db, ("SELECT disc_id FROM registered_summoners WHERE secret=?"),
                (secret,)
            ).fetchone()[0]

    def add_user(self, summ_name, summ_id, discord_id):
        status = ""
        try:
            with self.get_connection() as db:
                summ_info = self.summoner_from_discord_id(discord_id)

                is_inactive = self.execute_query(
                    db, "SELECT * FROM registered_summoners WHERE disc_id=? AND active=0",
                    (discord_id,)
                ).fetchone() is not None

                if is_inactive:
                    query = ("UPDATE registered_summoners SET active=1 WHERE disc_id=?")
                    status = "Welcome back to the Int-Far:tm: Tracker:tm:, my lost son :hearts:"
                    self.summoners.append((discord_id, [summ_name], [summ_id]))
                    self.execute_query(
                        db, query, (discord_id,)
                    )

                else:
                    query = (
                        "INSERT INTO registered_summoners(disc_id, summ_name, " +
                        "summ_id, secret, reports, active) VALUES (?, ?, ?, ?, ?, 1)"
                    )

                    if summ_info is not None:
                        _, summ_names, summ_ids = summ_info
                        if len(summ_names) == 3:
                            return (
                                False,
                                "Error: A maximum of three accounts can be registered for one person."
                            )
                        summ_names.append(summ_name)
                        summ_ids.append(summ_id)
                        secret = self.get_client_secret(discord_id)
                        status = f"Added smurf '{summ_name}' with  summoner ID '{summ_id}'."
                    else:
                        self.summoners.append((discord_id, [summ_name], [summ_id]))
                        secret = generate_user_secret()
                        status = f"User '{summ_name}' with summoner ID '{summ_id}' succesfully added!"
                        # Check if user has been registered before, and is now re-registering.

                    self.execute_query(
                        db, query, (discord_id, summ_name, summ_id, secret, 0)
                    )
                    if summ_info is None:
                        # Only create betting balance table if user is new.
                        self.execute_query(
                            db, "INSERT INTO betting_balance VALUES (?, ?)", (discord_id, 100)
                        )
        except DBException:
            return (False, "A user with that summoner name is already registered!")
        return (True, status)

    def remove_user(self, disc_id):
        with self.get_connection() as db:
            delete_query = "UPDATE registered_summoners SET active=0 WHERE disc_id=?"
            self.execute_query(db, delete_query, (disc_id,))

        new_summ_list = []
        for discord_id, summ_names, summ_ids in self.summoners:
            if discord_id != disc_id:
                new_summ_list.append((discord_id, summ_names, summ_ids))
        self.summoners = new_summ_list

    def discord_id_from_summoner(self, name, exact_match=True):
        matches = []
        for disc_id, summ_names, summ_ids in self.summoners:
            for (summ_name, summ_id) in zip(summ_names, summ_ids):
                if exact_match and summ_name.lower() == name:
                    return (disc_id, summ_name, summ_id)
                elif not exact_match and name in summ_name.lower():
                    matches.append((disc_id, summ_name, summ_id))
        return matches[0] if len(matches) == 1 else None

    def summoner_from_discord_id(self, discord_id):
        for disc_id, summ_names, summ_ids in self.summoners:
            if disc_id == discord_id:
                return (disc_id, summ_names, summ_ids)
        return None

    def game_exists(self, game_id):
        with self.get_connection() as db:
            query = "SELECT game_id FROM games WHERE game_id=?"
            return self.execute_query(db, query, (game_id,)).fetchone() is not None

    def delete_game(self, game_id):
        with self.get_connection() as db:
            query_1 = "DELETE FROM games WHERE game_id=?"
            query_2 = "DELETE FROM best_stats WHERE game_id=?"
            query_3 = "DELETE FROM worst_stats WHERE game_id=?"
            query_4 = "DELETE FROM participants WHERE game_id=?"
            self.execute_query(db, query_1, (game_id,), commit=False)
            self.execute_query(db, query_2, (game_id,), commit=False)
            self.execute_query(db, query_3, (game_id,), commit=False)
            self.execute_query(db, query_4, (game_id,))

    def get_latest_game(self, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id)

        query_games = f"SELECT MAX(timestamp), win, intfar_id, intfar_reason FROM games{delim_str}"
        query_doinks = f"""
            SELECT timestamp, disc_id, doinks FROM (
               SELECT MAX(timestamp) AS t
               FROM games{delim_str}
            ) sub_1, participants p
            JOIN games g
            ON p.game_id = g.game_id
            WHERE doinks IS NOT NULL AND timestamp = sub_1.t
        """
        with self.get_connection() as db:
            game_data = self.execute_query(db, query_games, params).fetchone()
            doinks_data = self.execute_query(db, query_doinks, params).fetchall()
            return game_data, doinks_data

    def get_most_extreme_stat(self, stat, best, maximize=True):
        with self.get_connection() as db:
            aggregator = "MAX" if maximize else "MIN"
            table = "best_stats" if best else "worst_stats"

            if stat == "first_blood":
                query = (
                    f"SELECT sub.first_blood, {aggregator}(sub.c) FROM " +
                    f"(SELECT first_blood, Count(DISTINCT game_id) AS c FROM {table}, " +
                    "registered_summoners as rs WHERE rs.disc_id=first_blood AND rs.active=1 " +
                    "GROUP BY first_blood HAVING first_blood IS NOT NULL) sub"
                    ""
                )
                result = self.execute_query(db, query).fetchone()
                return result + (None,)

            query = (
                f"SELECT {stat}_id, {aggregator}({stat}), game_id FROM {table}, " +
                f"registered_summoners as rs WHERE rs.disc_id={stat}_id AND rs.active=1"
            )
            return self.execute_query(db, query).fetchone()

    def get_stat(self, stat, best, disc_id, maximize=True):
        with self.get_connection() as db:
            aggregator = "MAX" if maximize else "MIN"
            table = "best_stats" if best else "worst_stats"

            if stat == "first_blood":
                query = (
                    f"SELECT Count(DISTINCT game_id) FROM {table} JOIN registered_summoners rs ON " +
                    "rs.disc_id=first_blood WHERE first_blood=? AND rs.active=1"
                )
                result = self.execute_query(db, query, (disc_id,)).fetchone()
                return result[0], None, None

            query = (
                f"SELECT Count(DISTINCT game_id), {aggregator}({stat}), game_id " +
                f"FROM {table} JOIN registered_summoners rs ON " +
                f"rs.disc_id={stat}_id WHERE {stat}_id=? AND rs.active=1"
            )

            return self.execute_query(db, query, (disc_id,)).fetchone()

    def get_champ_count_for_stat(self, stat, best, disc_id):
        table = "best_stats" if best else "worst_stats"
        query = (
            f"SELECT sub.champ_id, MAX(sub.c) FROM ( " +
            f"   SELECT COUNT(DISTINCT st.game_id) AS c, champ_id FROM {table} st" +
            f"   JOIN registered_summoners rs ON rs.disc_id=st.{stat}_id" +
            "   JOIN participants p ON p.game_id = st.game_id" +
            f"   WHERE st.{stat}_id=? AND p.disc_id=rs.disc_id AND rs.active=1" +
            "   GROUP BY champ_id" +
            ") sub"
        )
        with self.get_connection() as db:
            return self.execute_query(db, query, (disc_id,)).fetchone()

    def get_doinks_count(self, disc_id=None, context=None, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "p.disc_id", disc_id, "AND")

        query_doinks = (
            "SELECT SUM(sub.doinks_games), SUM(sub.doinks_total) FROM\n" +
            "(\n" +
            "   SELECT COUNT(*) AS doinks_games, SUM(LENGTH(REPLACE(sub_2.doinks, '0', ''))) AS doinks_total FROM"
            "   (\n" +
            "       SELECT DISTINCT p.game_id, p.disc_id, doinks, timestamp FROM participants AS p\n" +
            "       LEFT JOIN registered_summoners rs ON rs.disc_id=p.disc_id\n" +
            "       LEFT JOIN games g ON g.game_id = p.game_id\n" +
            f"      WHERE doinks IS NOT NULL AND rs.active=1{delim_str}\n" +
            "   ) sub_2\n" +
            "   GROUP BY sub_2.disc_id\n" +
            ") sub"
        )

        with (self.get_connection() if context is None else context) as db:
            doinks_games, doinks_total = self.execute_query(db, query_doinks, params).fetchone()
            return doinks_games or 0, doinks_total or 0

    def get_champ_with_most_doinks(self, disc_id):
        with self.get_connection() as db:
            query = (
                "SELECT sub.champ_id, MAX(sub.c) FROM ( " +
                f"   SELECT COUNT(DISTINCT p.game_id) AS c, champ_id FROM participants p" +
                f"   WHERE p.disc_id=? AND p.doinks IS NOT NULL" +
                "   GROUP BY champ_id" +
                ") sub"
            )
            return self.execute_query(db, query, (disc_id,)).fetchone()

    def get_max_doinks_details(self):
        with self.get_connection() as db:
            query = """
            SELECT MAX(counts.c), counts.disc_id FROM 
            (SELECT p.disc_id, Count(*) as c FROM participants as p, 
            registered_summoners as rs WHERE doinks IS NOT NULL 
            AND rs.disc_id=p.disc_id AND rs.active=1 GROUP BY p.disc_id) AS counts 
            """
            return self.execute_query(db, query).fetchone()

    def get_doinks_reason_counts(self, context=None):
        query_doinks_multis = (
            "SELECT doinks FROM participants as p, registered_summoners as rs " +
            "WHERE doinks IS NOT NULL AND rs.disc_id=p.disc_id AND rs.active=1"
        )

        with (self.get_connection() if context is None else context) as db:
            doinks_reasons_data = self.execute_query(db, query_doinks_multis).fetchall()

            doinks_counts = [0 for _ in DOINKS_REASONS]
            for reason in doinks_reasons_data:
                for index, c in enumerate(reason[0]):
                    if c == "1":
                        doinks_counts[index] += 1

            return doinks_counts

    def get_game_ids(self):
        query = "SELECT game_id FROM games"
        with self.get_connection() as db:
            return self.execute_query(db, query).fetchall()

    def get_recent_intfars_and_doinks(self):
        with self.get_connection() as db:
            query = (
                "SELECT g.game_id, timestamp, p.disc_id, doinks, intfar_id, "
                "intfar_reason FROM participants AS p LEFT JOIN games g ON "
                "p.game_id = g.game_id LEFT JOIN registered_summoners rs ON " +
                "p.disc_id=rs.disc_id WHERE rs.active=1 GROUP BY p.game_id, p.disc_id ORDER BY timestamp ASC"
            )
            return self.execute_query(db, query).fetchall()

    def get_delimeter(self, time_after, time_before, guild_id, other_key=None, other_param=None, prefix=None):
        prefix = prefix if prefix is not None else "WHERE"
        delimiter = "" if other_param is None else f" {prefix} {other_key} = ?"
        params = None if other_param is None else (other_param,)

        if time_after is not None:
            if params is None:
                params = (time_after,)
                delimiter += f" {prefix} timestamp > ?"
            else:
                params = (other_param, time_after)
                delimiter += " AND timestamp > ?"

        if time_before is not None:
            if params is None:
                params = (time_before,)
                delimiter += f" {prefix} timestamp < ?"
            else:
                delimiter += " AND timestamp < ?"
                params = params + (time_before,)

        if guild_id is not None:
            if params is None:
                params = (guild_id,)
                delimiter += f" {prefix} guild_id = ?"
            else:
                params = params + (guild_id,)
                delimiter += " AND guild_id = ?"

        return delimiter, params

    def get_recent_game_results(self, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id)

        query = f"SELECT win FROM games{delim_str} ORDER BY timestamp DESC"
        with self.get_connection() as db:
            return [x[0] for x in self.execute_query(db, query, params).fetchall()]

    def get_games_results(self, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id)

        query = f"""
            SELECT win, timestamp
            FROM games{delim_str}
            ORDER BY timestamp
        """

        with self.get_connection() as db:
            return self.execute_query(db, query, params).fetchall()

    def get_games_count(self, context=None, time_after=None, time_before=None, guild_id=None):
        delim_str_1, params_1 = self.get_delimeter(time_after, time_before, guild_id)
        delim_str_2, params_2 = self.get_delimeter(time_after, time_before, guild_id, "win", 1)

        query = f"""
            SELECT games.c, games.timestamp, wins.c FROM (
                SELECT COUNT(*) AS c, timestamp FROM games g{delim_str_1}
            ) games,
            (
                SELECT COUNT(*) AS c FROM games{delim_str_2}
            ) wins
        """
        params = params_2 if params_1 is None else params_1 + params_2

        with (self.get_connection() if context is None else context) as db:
            return self.execute_query(db, query, params).fetchone()

    def get_longest_game(self, context=None, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id)

        query = f"SELECT MAX(duration), timestamp FROM games{delim_str}"

        with (self.get_connection() if context is None else context) as db:
            return self.execute_query(db, query, params).fetchone()

    def get_champs_played(self, disc_id=None, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "disc_id", disc_id)

        with self.get_connection() as db:
            query = f"""
                SELECT COUNT(DISTINCT champ_id) FROM participants AS p
                JOIN games g ON p.game_id = g.game_id{delim_str}
            """
            return self.execute_query(db, query, params).fetchone()[0]

    def get_champ_with_most_intfars(self, disc_id):
        with self.get_connection() as db:
            query = """
                SELECT sub.champ_id, MAX(sub.c) FROM (
                    SELECT COUNT(DISTINCT p.game_id) AS c, champ_id FROM games g
                    JOIN participants p
                    ON p.game_id=g.game_id AND g.intfar_id=p.disc_id
                    WHERE g.intfar_id=? AND g.intfar_id IS NOT NULL
                    GROUP BY champ_id
                ) sub
            """
            return self.execute_query(db, query, (disc_id,)).fetchone()

    def get_intfar_count(self, disc_id=None, context=None, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "disc_id", disc_id, "AND")

        query_intfars = f"""
            SELECT SUM(sub.intfars) FROM (
                SELECT COUNT(*) AS intfars FROM (
                   SELECT DISTINCT g.game_id, intfar_id FROM games AS g
                   LEFT JOIN registered_summoners rs ON rs.disc_id=intfar_id
                  WHERE intfar_id IS NOT NULL AND rs.active = 1{delim_str}
                ) sub_2
                GROUP BY sub_2.intfar_id
            ) sub
        """

        with (self.get_connection() if context is None else context) as db:
            intfars = self.execute_query(db, query_intfars, params).fetchone()
            return (intfars[0] if intfars is not None else 0) or 0

    def get_intfar_reason_counts(self, context=None):
        query_intfar_multis = """
            SELECT intfar_reason FROM games LEFT JOIN registered_summoners rs
            ON rs.disc_id=intfar_id WHERE intfar_id IS NOT NULL AND
            rs.active=1 GROUP BY game_id
        """
        with (self.get_connection() if context is None else context) as db:
            intfar_multis_data = self.execute_query(db, query_intfar_multis).fetchall()

            intfar_counts = [0, 0, 0, 0]
            intfar_multi_counts = {
                1: 0, 2: 0, 3: 0, 4: 0
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
        query = (
            "SELECT (wins.c / played.c) * 100 FROM ( " +
            "   SELECT CAST(COUNT(DISTINCT g.game_id) as real) AS c FROM games AS g " +
            "   LEFT JOIN participants p on g.game_id=p.game_id " +
            "   WHERE disc_id=? AND win=1" +
            ") wins," +
            "(" +
            "   SELECT CAST(COUNT(DISTINCT g.game_id) as real) AS c FROM games AS g " +
            "   LEFT JOIN participants p on g.game_id=p.game_id " +
            "   WHERE disc_id=?" +
            ") played "
        )
        with self.get_connection() as db:
            return self.execute_query(db, query, (disc_id, disc_id)).fetchone()[0]

    def get_champ_winrate(self, disc_id, champ_id):
        query = (
            "SELECT (wins.c / played.c) * 100 AS wr, played.c AS gs FROM (" +
            "   SELECT CAST(COALESCE(COUNT(DISTINCT g.game_id), 0) as real) AS c, champ_id FROM games AS g " +
            "       LEFT JOIN participants p on g.game_id=p.game_id " +
            "       WHERE disc_id=? AND champ_id =? AND win=1" +
            "   ) wins," +
            "   (" +
            "       SELECT CAST(COUNT(DISTINCT g.game_id) as real) AS c, champ_id FROM games AS g " +
            "       LEFT JOIN participants p on g.game_id=p.game_id " +
            "       WHERE disc_id=? AND champ_id=?" +
            "   ) played " +
            f"WHERE wins.champ_id = played.champ_id OR wins.champ_id IS NULL"
        )

        with self.get_connection() as db:
            return self.execute_query(db, query, (disc_id, champ_id, disc_id, champ_id)).fetchone()

    def get_min_or_max_winrate_champ(self, disc_id, best, min_games=10):
        aggregate = "MAX" if best else "MIN"
        query = (
            f"SELECT {aggregate}(sub.wr), CAST(sub.gs as integer), sub.champ FROM ( " +
            "   SELECT (wins.c / played.c) * 100 AS wr, played.c AS gs, played.champ_id as champ FROM ( " +
            "       SELECT CAST(COUNT(DISTINCT g.game_id) as real) AS c, champ_id FROM games AS g " +
            "       LEFT JOIN participants p on g.game_id=p.game_id " +
            "       WHERE disc_id=? AND win=1 GROUP BY champ_id ORDER BY champ_id" +
            "   ) wins," +
            "   (" +
            "       SELECT CAST(COUNT(DISTINCT g.game_id) as real) AS c, champ_id FROM games AS g " +
            "       LEFT JOIN participants p on g.game_id=p.game_id " +
            "       WHERE disc_id=? GROUP BY champ_id ORDER BY champ_id" +
            "   ) played " +
            f"   WHERE wins.champ_id = played.champ_id AND played.c > {min_games}" +
            ") sub"
        )
        with self.get_connection() as db:
            result = self.execute_query(db, query, (disc_id, disc_id)).fetchone()
            if result is None and min_games == 10:
                return self.get_champ_winrate(disc_id, best, min_games=5)

            return result

    def get_winrate_relation(self, disc_id, best, min_games=10):
        query_games = """
        SELECT p2.disc_id, Count(*) as c FROM participants p1, participants p2
        WHERE p1.disc_id != p2.disc_id AND p1.game_id = p2.game_id AND p1.disc_id=?
        GROUP BY p1.disc_id, p2.disc_id ORDER BY c DESC;
        """
        query_wins = """
        SELECT p2.disc_id, Count(*) as c FROM games g, participants p1, participants p2
        WHERE p1.disc_id != p2.disc_id AND g.game_id = p1.game_id AND g.game_id = p2.game_id
        AND p1.game_id = p2.game_id AND p1.disc_id=? AND win=1
        GROUP BY p1.disc_id, p2.disc_id ORDER BY c DESC;
        """
        with self.get_connection() as db:
            games_with_person = {}
            wins_with_person = {}
            for part_id, wins in self.execute_query(db, query_wins, (disc_id,)):
                if disc_id == part_id or not self.user_exists(part_id):
                    continue
                wins_with_person[part_id] = wins
            for part_id, games in db.cursor().execute(query_games, (disc_id,)):
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

    def get_played_champs(self, disc_id):
        with self.get_connection() as db:
            query = "SELECT DISTINCT champ_id FROM participants WHERE disc_id=?"
            return self.execute_query(db, query, (disc_id,)).fetchall()

    def get_meta_stats(self):
        query_persons = "SELECT Count(*) FROM participants as p GROUP BY game_id"

        users = (len(self.summoners),)
        with self.get_connection() as db:
            game_data = self.get_games_count(context=db)
            longest_game = self.get_longest_game(context=db)
            intfar_data = self.get_intfar_count(context=db)
            doinks_data = self.get_doinks_count(context=db)
            persons_counts = self.execute_query(db, query_persons)
            persons_count = {2: 0, 3: 0, 4: 0, 5: 0}
            for persons in persons_counts:
                persons_count[persons[0]] += 1
            twos_ratio = int((persons_count[2] / game_data[0]) * 100)
            threes_ratio = int((persons_count[3] / game_data[0]) * 100)
            fours_ratio = int((persons_count[4] / game_data[0]) * 100)
            fives_ratio = int((persons_count[5] / game_data[0]) * 100)
            games_ratios = [twos_ratio, threes_ratio, fours_ratio, fives_ratio]

            intfar_counts, intfar_multis_counts = self.get_intfar_reason_counts(db)
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

    def get_intfars_of_the_month(self):
        delim_str = self.get_monthly_delimiter()

        query_intfars = (
            "SELECT intfar_id FROM games g " +
            "LEFT JOIN registered_summoners rs ON rs.disc_id=intfar_id WHERE " +
            "intfar_id IS NOT NULL AND " + delim_str + " AND rs.active=1 GROUP BY g.game_id"
        )
        query_games = (
            "SELECT p.disc_id FROM games g, participants p LEFT JOIN " +
            "registered_summoners rs ON rs.disc_id=p.disc_id WHERE " +
            "g.game_id=p.game_id AND " + delim_str + " AND rs.active=1 GROUP BY g.game_id, p.disc_id"
        )

        with self.get_connection() as db:
            games_per_person = self.execute_query(db, query_games).fetchall()
            intfars_per_person = self.execute_query(db, query_intfars).fetchall()
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
                    # Disqualify people with less than 5 games played this month.
                    continue

                intfars = intfar_dict.get(disc_id, 0)

                pct_intfars.append(
                    (disc_id, total_games, intfars, (intfars / total_games) * 100)
                )

            return sorted(pct_intfars, key=lambda x: (x[3], x[2]), reverse=True)

    def get_longest_intfar_streak(self, disc_id):
        query = (
            "SELECT intfar_id FROM games LEFT JOIN registered_summoners rs " +
            "ON intfar_id=rs.disc_id GROUP BY game_id ORDER BY game_id"
        )
        with self.get_connection() as db:
            int_fars = self.execute_query(db, query).fetchall()
            max_count = 0
            count = 0
            for int_far in int_fars:
                if int_far[0] is None or disc_id != int_far[0]:
                    count = 0
                else:
                    count += 1
                if count > max_count:
                    max_count = count
            return max_count

    def get_longest_no_intfar_streak(self, disc_id):
        if not self.user_exists(disc_id):
            return 0

        query = """
        SELECT intfar_id FROM participants p LEFT JOIN games g ON g.game_id=p.game_id
        WHERE p.disc_id=? ORDER BY g.game_id
        """
        with self.get_connection() as db:
            int_fars = self.execute_query(db, query, (disc_id,)).fetchall()
            max_count = 0
            count = 0
            for int_far in int_fars:
                if disc_id == int_far[0]:
                    count = 0
                else:
                    count += 1
                if count > max_count:
                    max_count = count
            return max_count

    def get_current_intfar_streak(self):
        query = (
            "SELECT intfar_id FROM games LEFT JOIN registered_summoners rs " +
            "ON intfar_id=rs.disc_id GROUP BY game_id ORDER BY game_id DESC"
        )
        with self.get_connection() as db:
            int_fars = self.execute_query(db, query).fetchall()
            prev_intfar = int_fars[0][0]
            for count, int_far in enumerate(int_fars[1:], start=1):
                if int_far[0] is None or prev_intfar != int_far[0]:
                    return count, prev_intfar
            return len(int_fars), prev_intfar # All the int-fars is the current int-far!

    def get_max_intfar_details(self):
        with self.get_connection() as db:
            query = """
            SELECT MAX(pcts.pct), pcts.intboi FROM 
            (
                SELECT (intfar_counts.c / games_counts.c) * 100 AS pct, intfar_counts.intfar_id AS intboi FROM
                (
                    SELECT intfar_id, CAST(Count(*) as real) as c FROM games
                    WHERE intfar_id IS NOT NULL GROUP BY intfar_id
                ) AS intfar_counts,
                (
                    SELECT disc_id, CAST(Count(*) as real) as c FROM participants
                    GROUP BY disc_id
                ) AS games_counts
                WHERE intfar_id=disc_id AND games_counts.c > 10
            ) AS pcts, registered_summoners as rs WHERE rs.disc_id=pcts.intboi AND rs.active=1;
            """
            return self.execute_query(db, query).fetchone()

    def get_intfar_stats(self, disc_id, monthly=False, time_after=None, time_before=None, guild_id=None):
        params_1 = None
        params_2 = None
        if monthly:
            monthly_delim = self.get_monthly_delimiter()
            if disc_id is not None:
                delim_str_1 = f" WHERE disc_id=? AND {monthly_delim}"
                delim_str_2 = f" WHERE intfar_id=? AND {monthly_delim}"
                params_1 = (disc_id,)
                params_2 = (disc_id,)
            else:
                delim_str_1 = f" WHERE {monthly_delim}"
                delim_str_2 = f" WHERE {monthly_delim}"
        else:
            delim_str_1, params_1 = self.get_delimeter(time_after, time_before, guild_id, "disc_id", disc_id)
            delim_str_2, params_2 = self.get_delimeter(time_after, time_before, guild_id, "intfar_id", disc_id)

        query_total = (
            f"SELECT Count(*) FROM games AS g JOIN participants p ON g.game_id = p.game_id{delim_str_1}"
        )
        query_intfar = (
            f"SELECT intfar_reason FROM games g JOIN participants p ON g.game_id=p.game_id{delim_str_2} GROUP BY g.game_id"
        )

        with self.get_connection() as db:
            total_games = self.execute_query(db, query_total, params_1).fetchone()[0]
            intfar_games = self.execute_query(db, query_intfar, params_2).fetchall()
            return total_games, intfar_games

    def get_intfar_relations(self, disc_id):
        query_games = """
        SELECT p2.disc_id, Count(*) as c FROM participants p1, participants p2
        WHERE p1.disc_id != p2.disc_id AND p1.game_id = p2.game_id AND p1.disc_id=?
        GROUP BY p1.disc_id, p2.disc_id ORDER BY c DESC;
        """
        query_intfars = """
        SELECT disc_id, Count(*) as c FROM games g, participants p
        WHERE intfar_id IS NOT NULL AND g.game_id=p.game_id AND intfar_id=?
        GROUP BY disc_id ORDER BY c DESC
        """
        with self.get_connection() as db:
            games_with_person = {}
            intfars_with_person = {}
            for part_id, intfars in self.execute_query(db, query_intfars, (disc_id,)):
                if disc_id == part_id or not self.user_exists(part_id):
                    continue
                intfars_with_person[part_id] = intfars
            for part_id, games in db.cursor().execute(query_games, (disc_id,)):
                if self.user_exists(part_id):
                    games_with_person[part_id] = games
            return games_with_person, intfars_with_person

    def get_doinks_stats(self, disc_id=None, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "p.disc_id", disc_id, "AND")

        query = (
            "SELECT doinks FROM participants AS p " +
            "LEFT JOIN registered_summoners rs ON rs.disc_id=p.disc_id " +
            "LEFT JOIN games g ON p.game_id = g.game_id " +
            f"WHERE doinks IS NOT NULL AND rs.active=1{delim_str} GROUP BY g.game_id"
        )

        with self.get_connection() as db:
            return self.execute_query(db, query, params).fetchall()

    def get_doinks_relations(self, disc_id):
        query_games = """
        SELECT p2.disc_id, Count(*) as c FROM participants p1, participants p2
        WHERE p1.disc_id != p2.disc_id AND p1.game_id = p2.game_id AND p1.disc_id=?
        GROUP BY p1.disc_id, p2.disc_id ORDER BY c DESC;
        """
        query_doinks = """
        SELECT p2.disc_id, Count(*) as c FROM participants p1, participants p2
        WHERE p1.disc_id != p2.disc_id AND p1.game_id = p2.game_id AND p1.doinks IS NOT NULL AND p1.disc_id=?
        GROUP BY p1.disc_id, p2.disc_id ORDER BY c DESC
        """
        with self.get_connection() as db:
            games_with_person = {}
            doinks_with_person = {}
            for part_id, doinks in self.execute_query(db, query_doinks, (disc_id,)):
                if disc_id == part_id or not self.user_exists(part_id):
                    continue
                doinks_with_person[part_id] = doinks
            for part_id, games in db.cursor().execute(query_games, (disc_id,)):
                if self.user_exists(part_id):
                    games_with_person[part_id] = games
            return games_with_person, doinks_with_person

    def get_performance_score(self, disc_id=None):
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

        query_subs = """
            (
                SELECT CAST(COUNT(DISTINCT g.game_id) AS real) AS c, disc_id FROM games g
                JOIN participants p ON g.game_id = p.game_id
                GROUP BY disc_id
            ) played,
            (
                SELECT CAST(COUNT(DISTINCT g.game_id) AS real) AS c, disc_id FROM games g
                JOIN participants p ON g.game_id = p.game_id
                WHERE win=1 GROUP BY disc_id
            ) wins,
            (
                SELECT CAST(COUNT(*) AS real) AS c, intfar_id FROM games
                GROUP BY intfar_id
            ) intfars,
            (
                SELECT CAST(SUM(LENGTH(REPLACE(doinks_sub.doinks, '0', ''))) AS real) AS c, doinks_sub.disc_id FROM
                (
                    SELECT DISTINCT game_id, doinks, disc_id FROM participants
                    WHERE doinks IS NOT NULL
                ) doinks_sub
                GROUP BY doinks_sub.disc_id
            ) doinks
            WHERE played.disc_id = wins.disc_id AND played.disc_id = intfars.intfar_id AND played.disc_id = doinks.disc_id
            AND wins.disc_id = intfars.intfar_id AND wins.disc_id = doinks.disc_id AND intfars.intfar_id = doinks.disc_id
        ) sub
        LEFT JOIN registered_summoners rs ON sub.user = rs.disc_id WHERE active=1
        GROUP BY sub.user ORDER BY sub.score DESC
        """

        query_full = query_outer + query_select + query_subs

        with self.get_connection() as db:
            performance_scores = self.execute_query(db, query_full).fetchall()
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

    def get_stat_data(self, stat_key, stat_name, data, reverse_order=False, total_kills=0):
        (min_stat_id, min_stat,
         max_stat_id, max_stat) = game_stats.get_outlier_stat(
             stat_key, data, reverse_order=reverse_order, total_kills=total_kills
        )

        (best_ever_id, best_ever, _) = self.get_most_extreme_stat(stat_name, True, stat_name != "deaths")
        (worst_ever_id, worst_ever, _) = self.get_most_extreme_stat(stat_name, False, stat_name == "deaths")

        return min_stat_id, min_stat, max_stat_id, max_stat, best_ever, best_ever_id, worst_ever, worst_ever_id

    def record_stats(self, intfar_id, intfar_reason, doinks, game_id, data, users_in_game, guild_id):
        kills_by_our_team = data[0][1]["kills_by_team"]
        timestamp = data[0][1]["timestamp"] // 1000
        duration = data[0][1]["gameDuration"]

        first_blood_id = None
        for disc_id, stats in data:
            if stats["firstBloodKill"]:
                first_blood_id = disc_id
                break

        keys = [
            "kills", "deaths", "kda", "totalDamageDealtToChampions",
            "totalCs", "csPerMin", "goldEarned", "kp",
            "visionWardsBoughtInGame", "visionScore"
        ]

        stats_query = "first_blood"
        for stat_name in STAT_COMMANDS[:-1]:
            stats_query += f", {stat_name}, {stat_name}_id"
        question_marks = ", ".join("?" * len(STAT_COMMANDS) * 2)
        query_cols = f"(game_id, {stats_query}) VALUES ({question_marks})"

        beaten_records_best = []
        beaten_records_worst = []

        best_values = [game_id, first_blood_id]
        worst_values = [game_id, first_blood_id]
        for key, stat in zip(keys, STAT_COMMANDS[:-1]):
            reverse_order = key == "deaths"
            (
                min_id, min_value, max_id, max_value,
                prev_best, prev_best_id, prev_worst, prev_worst_id
            ) = self.get_stat_data(key, stat, data, reverse_order, kills_by_our_team)

            best_values.extend([max_value, max_id])
            worst_values.extend([min_value, min_id])

            if reverse_order: # Stat is 'deaths'.
                if min_value < prev_best: # Fewest deaths ever has been reached.
                    beaten_records_best.append((stat, min_value, min_id, prev_best, prev_best_id))
                elif max_value > prev_worst: # Most deaths ever has been reached.
                    beaten_records_worst.append((stat, max_value, max_id, prev_worst, prev_worst_id))
            else: # Stat is any other stat.
                if max_value > prev_best: # A new best has been set for a stat.
                    beaten_records_best.append((stat, max_value, max_id, prev_best, prev_best_id))
                elif min_value < prev_worst: # A new worst has been set for a stat.
                    beaten_records_worst.append((stat, min_value, min_id, prev_worst, prev_worst_id))

        with self.get_connection() as db:
            query_game = (
                "INSERT INTO games(game_id, timestamp, duration, intfar_id, " +
                "intfar_reason, win, guild_id) VALUES (?, ?, ?, ?, ?, ?, ?)"
            )

            win = 1 if data[0][1]["gameWon"] else 0
            self.execute_query(
                db, query_game, (game_id, timestamp, duration, intfar_id, intfar_reason, win, guild_id)
            )

            for table in ("best", "worst"):
                value_list = best_values if table == "best" else worst_values
                print_str = (f"{x} - {y}" for (x, y) in zip(value_list[1::2], value_list[::2]))
                print_str = "), (".join(print_str)

                self.config.log(
                    f"Saving {table} stats:\n" +
                    f"{game_id}, {intfar_id}, {intfar_reason}, " +
                    f"{first_blood_id}, ({print_str})"
                )

                query = f"INSERT INTO {table}_stats {query_cols}"

                self.execute_query(db, query, tuple(value_list))

            self.config.log(
                "Saving participants:\n"+
                f"{game_id}, {users_in_game}, {timestamp}, {doinks}"
            )

            query = "INSERT INTO participants(game_id, disc_id, champ_id, doinks) VALUES (?, ?, ?, ?)"
            for user_data in users_in_game:
                print(user_data)
                disc_id = user_data[0]
                champ_id = user_data[-1]
                doink = doinks.get(disc_id, None)
                self.execute_query(db, query, (game_id, disc_id, champ_id, doink))
            db.commit()

        return beaten_records_best, beaten_records_worst

    def save_missed_game(self, game_id, guild_id, timestamp):
        query = "INSERT INTO missed_games VALUES (?, ?, ?)"
        with self.get_connection() as db:
            self.execute_query(db, query, (game_id, guild_id, timestamp))

    def get_missed_games(self):
        query = "SELECT game_id, guild_id FROM missed_games"
        with self.get_connection() as db:
            return self.execute_query(db, query).fetchall()

    def remove_missed_game(self, game_id):
        query = "DELETE FROM missed_games WHERE game_id=?"
        with self.get_connection() as db:
            self.execute_query(db, query, (game_id,))

    def save_lan_stats(self, game_id, data):
        query = (
            "INSERT INTO lan_stats(game_id, disc_id, kills, deaths, assists, " +
            "damage, cs, cs_per_min, gold, kp, vision_wards, vision_score) " +
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )

        keys = [
            "kills", "deaths", "assists", "totalDamageDealtToChampions", "totalCs",
            "csPerMin", "goldEarned", "kp", "visionWardsBoughtInGame", "visionScore"
        ]
        kills_by_our_team = data[0][1]["kills_by_team"]

        for disc_id, stats in data:
            params = [game_id, disc_id]
            for stat_key in keys:
                params.append(game_stats.get_stat_value(stats, stat_key, kills_by_our_team))

            with self.get_connection() as db:
                self.execute_query(db, query, tuple(params))

    def get_lan_stats(self, disc_id=None, time_after=None, time_before=None, guild_id=None):
        delim_str, params = self.get_delimeter(time_after, time_before, guild_id, "disc_id", disc_id)

        query = f"""
            SELECT
                disc_id,
                kills,
                deaths,
                assists,
                cs,
                cs_per_min,
                damage,
                gold,
                kp,
                vision_wards,
                vision_score
            FROM lan_stats
            INNER JOIN games g
            ON g.game_id = lan_stats.game_id
            {delim_str}
        """

        with self.get_connection() as db:
            results = self.execute_query(db, query, params).fetchall()
            if disc_id is None:
                result_dict = {}
                for result_tuple in results:
                    user_id = result_tuple[0]
                    if user_id not in result_dict:
                        result_dict[user_id] = []

                    result_dict[user_id].append(result_tuple[1:])
                return result_dict
            return results

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
        with self.get_connection() as db:
            query = "SELECT MAX(ticket) FROM bets WHERE better_id=?"
            curr_id = self.execute_query(db, query, (disc_id,)).fetchone()
            if curr_id is None or curr_id[0] is None:
                return 0
            return curr_id[0] + 1

    def get_bets(self, only_active, disc_id=None, guild_id=None):
        with self.get_connection() as db:
            query = (
                "SELECT better_id, id, guild_id, bets.timestamp, amount, " +
                "event_id, game_duration, target, ticket"
            )
            if not only_active:
                query += ", result, payout"
            query += (
                " FROM bets LEFT JOIN registered_summoners rs " +
                "ON rs.disc_id=better_id WHERE "
            )
            if not only_active:
                query += "result != 0"
            else:
                query += "result = 0"

            params = None
            if disc_id is not None:
                query += " AND better_id=?"
                params = (disc_id,)
            if guild_id is not None:
                query += " AND guild_id=?"
                params = params + (guild_id,) if params is not None else (guild_id,)

            query += " AND rs.active=1 GROUP BY id ORDER by id"

            data = self.execute_query(db, query, params).fetchall()
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

    def get_base_bet_return(self, event_id):
        with self.get_connection() as db:
            query = "SELECT max_return FROM betting_events WHERE id=?"
            return self.execute_query(db, query, (event_id,)).fetchone()[0]

    def get_token_balance(self, disc_id=None):
        with self.get_connection() as db:
            query = "SELECT bb.tokens"
            if disc_id is None:
                query += ", bb.disc_id"

            query += (
                " FROM betting_balance as bb, registered_summoners AS rs " +
                "WHERE rs.disc_id=bb.disc_id AND rs.active=1 "
            )

            params = None
            if disc_id is not None:
                query += "AND bb.disc_id=? "
                params = (disc_id,)
            query += "GROUP BY bb.disc_id ORDER BY bb.tokens DESC"
            data = self.execute_query(db, query, params).fetchall()
            return data if disc_id is None else data[0][0]

    def get_max_tokens_details(self):
        with self.get_connection() as db:
            query = (
                "SELECT MAX(tokens), bb.disc_id FROM betting_balance AS bb, " +
                "registered_summoners AS rs WHERE rs.disc_id=bb.disc_id AND rs.active=1"
            )
            return self.execute_query(db, query).fetchone()

    def update_token_balance(self, disc_id, amount, increment=True):
        with self.get_connection() as db:
            sign_str = "+" if increment else "-"
            query = f"UPDATE betting_balance SET tokens=tokens{sign_str}? WHERE disc_id=?"
            self.execute_query(db, query, (amount, disc_id))

    def get_bet_id(self, disc_id, guild_id, event_id, target=None, ticket=None):
        with self.get_connection() as db:
            query = ""
            if ticket is None:
                query = (
                    "SELECT id FROM bets WHERE better_id=? " +
                    "AND guild_id=? AND event_id=? "
                )
                query += "AND (target=? OR target IS NULL) "
                query += "AND result=0"
                args = (disc_id, guild_id, event_id, target)
            else:
                query = (
                    "SELECT id FROM bets WHERE better_id=? "
                    "AND guild_id=? AND ticket=? AND result=0"
                )
                args = (disc_id, guild_id, ticket)
            result = self.execute_query(db, query, args).fetchone()
            return None if result is None else result[0]

    def get_better_id(self, bet_id):
        if bet_id is not None:
            bet_id = int(bet_id)

        with self.get_connection() as db:
            query = "SELECT better_id FROM bets WHERE id=?"
            result = self.execute_query(db, query, (bet_id,)).fetchone()
            return None if result is None else result[0]

    def make_bet(self, disc_id, guild_id, event_id, amount, game_duration, target_person=None, ticket=None):
        with self.get_connection() as db:
            query_bet = "INSERT INTO bets(better_id, guild_id, timestamp, event_id, amount, "
            query_bet += "game_duration, target,  ticket, result) "
            query_bet += "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
            self.update_token_balance(disc_id, amount, False)
            self.execute_query(
                db, query_bet, (
                    disc_id, guild_id, 0, event_id, amount,
                    game_duration, target_person, ticket, 0
                )
            )
            return self.execute_query(db, "SELECT last_insert_rowid()").fetchone()[0]

    def cancel_bet(self, bet_id, disc_id):
        with self.get_connection() as db:
            query_del = "DELETE FROM bets WHERE id=? AND better_id=? AND result=0"
            query_amount = "SELECT amount FROM bets WHERE id=? AND better_id=? AND result=0"
            amount = self.execute_query(db, query_amount, (bet_id, disc_id)).fetchone()[0]
            self.execute_query(db, query_del, (bet_id, disc_id))
            self.update_token_balance(disc_id, amount, True)
            return amount

    def cancel_multi_bet(self, ticket, disc_id):
        with self.get_connection() as db:
            query_del = "DELETE FROM bets WHERE better_id=? AND ticket=?"
            query_amount = "SELECT amount FROM bets WHERE better_id=? AND ticket=?"
            amounts = self.execute_query(db, query_amount, (disc_id, ticket)).fetchall()
            amount_total = sum(x[0] for x in amounts)
            self.execute_query(db, query_del, (disc_id, ticket))
            self.update_token_balance(disc_id, amount_total, True)
            return amount_total

    def mark_bet_as_resolved(self, bet_id, game_id, timestamp, success, value):
        result_val = 1 if success else -1
        with self.get_connection() as db:
            query_bet = "UPDATE bets SET game_id=?, timestamp=?, result=?, payout=? WHERE id=?"
            payout = value if success else None
            self.execute_query(db, query_bet, (game_id, timestamp, result_val, payout, bet_id))

    def reset_bets(self):
        with self.get_connection() as db:
            query_bets = "DELETE FROM bets WHERE result=0"
            query_balance = "UPDATE betting_balance SET tokens=100"
            self.execute_query(db, query_bets)
            self.execute_query(db, query_balance)

    def give_tokens(self, sender, amount, receiver):
        self.update_token_balance(sender, amount, increment=False)
        self.update_token_balance(receiver, amount, increment=True)

    def get_reports(self, disc_id=None, context=None):
        with (self.get_connection() if context is None else context) as db:
            query_select = (
                "SELECT disc_id, reports FROM registered_summoners " +
                "WHERE active=1 "
            )

            params = None
            if disc_id is not None:
                query_select += "AND disc_id=? "
                params = (disc_id,)
            else:
                query_select += "GROUP BY disc_id "

            query_select += "ORDER BY reports DESC"
            return self.execute_query(db, query_select, params).fetchall()

    def get_max_reports_details(self):
        with self.get_connection() as db:
            query = "SELECT MAX(reports), disc_id FROM registered_summoners WHERE active=1"
            return self.execute_query(db, query).fetchone()

    def report_user(self, disc_id):
        with self.get_connection() as db:
            query_update = "UPDATE registered_summoners SET reports=reports+1 WHERE disc_id=?"
            self.execute_query(db, query_update, (disc_id,))
            return self.get_reports(disc_id, db)[0][1]

    def add_items_to_shop(self, item_tuples):
        with self.get_connection() as db:
            query = "INSERT INTO shop_items(name, price) VALUES (?, ?)"
            db.executemany(query, item_tuples)
            db.commit()

    def get_item_by_name(self, item_name, event):
        table = "shop_items" if event in ("buy", "cancel") else "owned_items"
        fmt_name = f"%{item_name.lower()}%"
        with self.get_connection() as db:
            query = f"SELECT DISTINCT(name) FROM {table} WHERE name LIKE ?"
            return self.execute_query(db, query, (fmt_name,)).fetchall()

    def get_items_for_user(self, disc_id):
        with self.get_connection() as db:
            query = "SELECT name, COUNT(*) FROM owned_items WHERE owner_id=? GROUP BY name"
            return self.execute_query(db, query, (disc_id,)).fetchall()

    def get_items_in_shop(self):
        with self.get_connection() as db:
            query = "SELECT name, price, COUNT(*) FROM shop_items GROUP BY name, price ORDER BY price DESC"
            return self.execute_query(db, query).fetchall()

    def get_items_matching_price(self, item_name, price, quantity, seller_id=None):
        with self.get_connection() as db:
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

            return self.execute_query(db, query_price, tuple(params)).fetchall()

    def buy_item(self, disc_id, item_copies, total_price, item_name):
        with self.get_connection() as db:
            for _, price, seller_id in item_copies: # Add items to user's inventory.
                query_insert = "INSERT INTO owned_items(name, owner_id) VALUES(?, ?)"
                self.execute_query(db, query_insert, (item_name, disc_id), commit=False)
                # Add payment of item to seller.
                query_update = "UPDATE betting_balance SET tokens=tokens+? WHERE disc_id=?"
                self.execute_query(db, query_update, (price, seller_id), commit=False)

            # Subtract the tokens spent from the user's balance.
            query_update = "UPDATE betting_balance SET tokens=tokens-? WHERE disc_id=?"
            self.execute_query(db, query_update, (total_price, disc_id), commit=False)

            for item in item_copies: # Delete from shop.
                query_delete = "DELETE FROM shop_items WHERE id=?"
                self.execute_query(db, query_delete, (item[0],), commit=False)

            db.commit()

    def get_matching_items_for_user(self, disc_id, item_name, quantity):
        with self.get_connection() as db:
            query_items = "SELECT id FROM owned_items WHERE owner_id=? AND name=? LIMIT ?"
            return self.execute_query(db, query_items, (disc_id, item_name, quantity)).fetchall()

    def sell_item(self, disc_id, item_copies, item_name, price):
        with self.get_connection() as db:
            query_insert = "INSERT INTO shop_items(name, price, seller_id) VALUES (?, ?, ?)"
            params_insert = [(item_name, price, disc_id) for _ in item_copies]
            self.execute_query(db, query_insert, params_insert)

            query_delete = "DELETE FROM owned_items WHERE id=?"
            params_delete = [(item_data[0],) for item_data in item_copies]
            self.execute_query(db, query_delete, params_delete)

            db.commit()

    def cancel_listings(self, item_ids, item_name, disc_id):
        with self.get_connection() as db:
            query_insert = "INSERT INTO owned_items(name, owner_id) VALUES (?, ?)"
            params_insert = [(item_name, disc_id) for _ in item_ids]
            self.execute_query(db, query_insert, params_insert)

            query_delete = "DELETE FROM shop_items WHERE id=?"
            params_delete = [(item_id,) for item_id in item_ids]
            self.execute_query(db, query_delete, params_delete)

            db.commit()

    def reset_shop(self):
        with self.get_connection() as db:
            query_items = "DELETE FROM owned_items"
            query_balance = "UPDATE betting_balance SET tokens=100"
            self.execute_query(db, query_items)
            self.execute_query(db, query_balance)

    def get_event_sound(self, disc_id, event):
        with self.get_connection() as db:
            query = "SELECT sound FROM event_sounds WHERE disc_id=? AND event=?"
            result = self.execute_query(db, query, (disc_id, event)).fetchone()
            return result[0] if result is not None else None

    def set_event_sound(self, disc_id, sound, event):
        with self.get_connection() as db:
            query = "REPLACE INTO event_sounds(disc_id, sound, event) VALUES (?, ?, ?)"
            self.execute_query(db, query, (disc_id, sound, event))

    def remove_event_sound(self, disc_id, event):
        with self.get_connection() as db:
            query = "DELETE FROM event_sounds WHERE disc_id=? AND event=?"
            self.execute_query(db, query, (disc_id, event))

    def create_list(self, disc_id, name):
        with self.get_connection() as db:
            query = "INSERT INTO champ_lists(name, owner_id) VALUES (?, ?)"
            try:
                self.execute_query(db, query, (name, disc_id))
                return True, self.execute_query(db, "SELECT last_insert_rowid()").fetchone()[0]
            except DatabaseError: # Duplicate champion inserted.
                return False, None

    def rename_list(self, list_id, new_name):
        with self.get_connection() as db:
            query = "UPDATE champ_lists SET name=? WHERE id=?"
            self.execute_query(db, query, (new_name, list_id))

    def delete_list(self, list_id):
        with self.get_connection() as db:
            query = "DELETE FROM list_items WHERE list_id=?"
            self.execute_query(db, query, (list_id,))
            query = "DELETE FROM champ_lists WHERE id=?"
            self.execute_query(db, query, (list_id,))

    def get_lists(self, disc_id=None):
        with self.get_connection() as db:
            query = (
                "SELECT champ_lists.id, champ_lists.owner_id, name, COUNT(list_items.id) " +
                "FROM champ_lists LEFT JOIN list_items ON champ_lists.id=list_id "
            )
            params = None
            if disc_id is not None:
                query += "WHERE owner_id=? "
                params = (disc_id,)

            query += "GROUP BY champ_lists.id"

            return self.execute_query(db, query, params).fetchall()

    def get_list_by_name(self, name):
        with self.get_connection() as db:
            query = "SELECT id FROM champ_lists WHERE LOWER(name)=?"
            result = self.execute_query(db, query, (name.lower(),)).fetchone()
            if result is None:
                return None, None

            list_id = result[0]

            return list_id, self.get_list_items(list_id)

    def get_list_data(self, list_id):
        with self.get_connection() as db:
            query = "SELECT name, owner_id FROM champ_lists WHERE id=?"
            return self.execute_query(db, query, (list_id,)).fetchone()

    def get_list_from_item_id(self, item_id):
        with self.get_connection() as db:
            query = "SELECT list_id FROM list_items WHERE id=?"
            list_id = self.execute_query(db, query, (item_id,)).fetchone()
            if list_id is None:
                return None

            list_data = self.get_list_data(list_id[0])
            if list_data is None:
                return None

            return list_id + list_data

    def add_item_to_list(self, champ_id, list_id):
        with self.get_connection() as db:
            query = "INSERT INTO list_items(champ_id, list_id) VALUES (?, ?)"
            try:
                self.execute_query(db, query, (champ_id, list_id))
                return True
            except DatabaseError: # Duplicate champion inserted.
                return False

    def add_items_to_list(self, items):
        with self.get_connection() as db:
            query = "INSERT INTO list_items(champ_id, list_id) VALUES (?, ?)"
            try:
                db.cursor().executemany(query, items)
                db.commit()
                return True
            except DatabaseError: # Duplicate champion inserted.
                return False

    def get_list_items(self, list_id):
        with self.get_connection() as db:
            query = "SELECT id, champ_id FROM list_items WHERE list_id=?"
            return self.execute_query(db, query, (list_id,)).fetchall()

    def delete_item_from_list(self, item_id):
        with self.get_connection() as db:
            query = "DELETE FROM list_items WHERE id=?"
            self.execute_query(db, query, (item_id,))

    def delete_items_from_list(self, item_ids):
        with self.get_connection() as db:
            query = "DELETE FROM list_items WHERE id=?"
            db.cursor().executemany(query, item_ids)
            db.commit()

    def get_lifetime_activity(self):
        with self.get_connection() as db:
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
            return self.execute_query(db, query).fetchall()

    def get_weekday_activity(self):
        with self.get_connection() as db:
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
            return self.execute_query(db, query).fetchall()

    def get_hourly_activity(self):
        with self.get_connection() as db:
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
            return self.execute_query(db, query).fetchall()

    def get_best_comps(self, participants):
        with self.get_connection() as db:
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

            return self.execute_query(db, query).fetchall()
