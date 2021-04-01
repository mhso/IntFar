from sys import argv
import sqlite3

if len(argv) == 1:
    exit(0)

database = argv[1]

conn = sqlite3.connect("resources/" + database + ".db")

if len(argv) > 2:
    filename = argv[2]
    with open(filename + ".sql", "r") as fp:
        result = conn.cursor().execute(fp.read())
        rows_returned = 0
        for row in result:
            print(row)
            rows_returned += 1
        conn.commit()
        rows_affected = conn.cursor().execute("SELECT changes()").fetchone()[0]
        if rows_affected > 0:
            print(f"Rows affected: {rows_affected}")
        else:
            print(f"Rows returned: {rows_returned}")
    exit(0)

try:
    while True:
        try:
            query = input(">")
            if query in ("q", "quit", "exit"):
                break
            result = conn.cursor().execute(query).fetchall()
            for row in result:
                print(row)
            if result != []:
                print(f"Rows returned: {len(result)}")
            else:
                rows_affected = conn.cursor().execute("SELECT changes()").fetchone()[0]
                print(f"Rows affected: {rows_affected}")

            conn.commit()
        except (sqlite3.OperationalError, sqlite3.ProgrammingError) as exc:
            print(exc.args)
        except KeyboardInterrupt:
            pass
finally:
    conn.close()
