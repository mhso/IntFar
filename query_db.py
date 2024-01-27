import os
from time import time
from argparse import ArgumentParser
import sqlite3
from api.config import Config
from api.meta_database import MetaDatabase
from api.game_databases import get_database_client
from api.util import SUPPORTED_GAMES

parser = ArgumentParser()

parser.add_argument("-db", "--database", default="meta", type=str)
parser.add_argument("--query", default=None, type=str, nargs="+")
parser.add_argument("--raw", action="store_true")
parser.add_argument("--print", action="store_true")

args = parser.parse_args()

config = Config()

if args.database == "meta":
    database = MetaDatabase(config)
elif args.database in SUPPORTED_GAMES:
    database = get_database_client(args.database, config)
else:
    print("Database does not seem to exist. Exiting...")
    exit(0)

def _try_cast(param):
    try:
        return int(param)
    except ValueError:
        try:
            return float(param)
        except ValueError:
            return str(param)

def run_query(database, query, *params, raw=False, print_query=False):
    if not hasattr(database, query):
        print("The query is not supported by the given database. Exiting...")
        exit(0)

    query_func = getattr(database, query)
    params = list(map(_try_cast, params))

    query_obj = query_func(*params)

    if print_query:
        print(query_obj)
        exit(0)

    time_start = time()
    result = query_obj(raw=raw)
    rows_returned = 0

    if raw:
        for row in result:
            print(row)
            rows_returned += 1
    else:
        print(result)
        try:
            rows_returned = len(result)
        except AttributeError:
            rows_returned = None

    time_end = time()
    time_taken = f"{time_end - time_start:.3f} seconds."

    rows_affected = database.connection.cursor().execute("SELECT changes()").fetchone()[0]
    if rows_affected > 0:
        print(f"Rows affected: {rows_affected} in {time_taken}")
    elif rows_affected is None:
        print("Unknown rows affected.")
    else:
        print(f"Rows returned: {rows_returned} in {time_taken}")

with database:
    # Execute a single given query
    if args.query is not None:
        query, *params = args.query
        run_query(database, query, *params, raw=args.raw, print_query=args.print)

    else:
        # Launch REPL-like loop
        conn = database.connection
        while True:
            try:
                query = input(">")
                if query in ("q", "quit", "exit"):
                    break

                if query.startswith("run"):
                    _, query, *params = query.split(" ")
                    run_query(database, query, *params, raw=True)
                    continue

                time_start = time()
                result = conn.cursor().execute(query)

                column_names = result.description
                if column_names is not None:
                    print(", ".join(tup[0] for tup in column_names))
                    print("-" * 100)

                rows_returned = 0
                for row in result:
                    print(", ".join(str(v) for v in row))
                    rows_returned += 1

                conn.commit()
                time_end = time()
                time_taken = f"{time_end - time_start:.3f} seconds."

                if rows_returned != 0:
                    print(f"Rows returned: {rows_returned} in {time_taken}")
                else:
                    rows_affected = conn.cursor().execute("SELECT changes()").fetchone()[0]
                    print(f"Rows affected: {rows_affected} in {time_taken}")

            except (sqlite3.OperationalError, sqlite3.ProgrammingError) as exc:
                print(exc.args)
            except KeyboardInterrupt:
                pass
