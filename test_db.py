import sqlite3

conn = sqlite3.connect("database.db")

try:
    while True:
        query = input(">")
        for row in conn.cursor().execute(query):
            print(row)
        conn.commit()
finally:
    conn.close()
