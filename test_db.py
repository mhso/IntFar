from sys import argv
import sqlite3

if len(argv) == 1:
    exit(0)

database = argv[1]

conn = sqlite3.connect(database + ".db")

try:
    while True:
        query = input(">")
        result = None
        if query.startswith("!"):
            with open(query[1:] + ".sql") as f:
                result = conn().cursor().executescript(f.read())
        else:
            result = conn.cursor().execute(query)
        for row in result:
            print(row)
        conn.commit()
finally:
    conn.close()
