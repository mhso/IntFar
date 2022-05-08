from sys import argv
from time import time
import sqlite3

if len(argv) == 1:
    exit(0)

database = argv[1]

conn = sqlite3.connect("resources/" + database + ".db")

if len(argv) > 2:
    filename = f"misc/queries/{argv[2]}"
    with open(filename + ".sql", "r") as fp:
        time_start = time()
        result = conn.cursor().execute(fp.read())
        rows_returned = 0
        for row in result:
            print(row)
            rows_returned += 1
        conn.commit()
        time_end = time()
        time_taken = f"{time_end - time_start:.3f} seconds."
        rows_affected = conn.cursor().execute("SELECT changes()").fetchone()[0]
        if rows_affected > 0:
            print(f"Rows affected: {rows_affected} in {time_taken}")
        else:
            print(f"Rows returned: {rows_returned} in {time_taken}")
    exit(0)

try:
    while True:
        try:
            query = input(">")
            if query in ("q", "quit", "exit"):
                break
            time_start = time()
            result = conn.cursor().execute(query).fetchall()
            for row in result:
                print(row)
            conn.commit()
            time_end = time()
            time_taken = f"{time_end - time_start:.3f} seconds."

            if result != []:
                print(f"Rows returned: {len(result)} in {time_taken}")
            else:
                rows_affected = conn.cursor().execute("SELECT changes()").fetchone()[0]
                print(f"Rows affected: {rows_affected} in {time_taken}")

        except (sqlite3.OperationalError, sqlite3.ProgrammingError) as exc:
            print(exc.args)
        except KeyboardInterrupt:
            pass
finally:
    conn.close()
