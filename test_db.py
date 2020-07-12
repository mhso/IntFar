from sys import argv
import sqlite3

if len(argv) == 1:
    exit(0)

database = argv[1]

conn = sqlite3.connect(database + ".db")

try:
    while True:
        query = input(">")
        for row in conn.cursor().execute(query):
            print(row)
        conn.commit()
finally:
    conn.close()
