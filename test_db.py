from sys import argv
import sqlite3

if len(argv) == 1:
    exit(0)

database = argv[1]

conn = sqlite3.connect(database + ".db")

if len(argv) > 2:
    filename = argv[2]
    with open(filename + ".sql", "r") as fp:
        result = conn.cursor().execute(fp.read())
        for row in result:
            print(row)
        conn.commit()
    exit(0)

try:
    while True:
        query = input(">")
        result = conn.cursor().execute(query)
        for row in result:
            print(row)
        conn.commit()
finally:
    conn.close()
