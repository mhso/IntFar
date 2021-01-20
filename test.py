from api.database import Database
from api.config import Config

def lift(text, start, end):
    try:
        start_name_index = text.index(start) + len(start)
    except ValueError:
        return None

    if text[start_name_index] == "!":
        start_name_index += 1
    shortened_line = text[start_name_index:]
    end_name_index = shortened_line.index(end)
    return int(shortened_line[:end_name_index].replace(".", ""))

def read_line(line, prev_date):
    split = line.split(" - ", 1)
    if len(split) == 1:
        return prev_date, split[0]

    try:
        timestamp = float(split[0])
        return timestamp, split[1]
    except ValueError:
        return prev_date, line

conf = Config()
database = Database(conf)

all_bets = database.get_bets(False)
bet_counts = {x: 0 for x, _, _ in database.summoners}
found_bets = {x: [] for x, _, _ in database.summoners}

bet_count = 0
with open("all_messages.txt", "r", encoding="utf-8") as fp:
    lines = fp.readlines()
    date = None
    index = 0
    while index < len(lines):
        date, line = read_line(lines[index], date)
        if line.startswith("Result of bets"):
            disc_id = lift(line, "<@", ">")
            index += 1
            date, line = read_line(lines[index], date)
            while line.startswith(" - "):
                bet_details = all_bets[disc_id][bet_counts[disc_id]]
                payout = lift(line, "awarded **", "**")
                cost = None
                if payout is None:
                    payout = None
                    cost = lift(line, "cost **", "**")

                if (cost is not None and sum(bet_details[2]) != cost) or bet_details[-1] != payout:
                    found_bets[disc_id].append((int(date), None, None))
                    bet_counts[disc_id] += 1

                    print(f"{disc_id} - {bet_details[0]} - Out of sync!")

                found_bets[disc_id].append((int(date), cost, payout))
                bet_counts[disc_id] += 1
                index += 1
                date, line = read_line(lines[index], date)
                bet_count += 1
        else:
            index += 1

with database.get_connection() as db:
    for disc_id in all_bets:
        print(f"========= {disc_id} ({len(found_bets[disc_id])} / {len(all_bets[disc_id])}) ==========")

        for index in range(len(all_bets[disc_id])):
            bet_details_db = all_bets[disc_id][index]
            bet_details_found = ""
            if index < len(found_bets[disc_id]):
                bet_details_found = found_bets[disc_id][index]

            query = "UPDATE bets SET timestamp=? WHERE id=?"
            for bet_id in bet_details_db[0]:
                database.execute_query(db, query, (bet_details_found[0], bet_id))

print(sum(bet_counts.values()))
print(sum(len(bets) for bets in all_bets.values()))
print(sorted([x for x in bet_counts.values() if x != 0]))
print(sorted([len(bets) for bets in all_bets.values()]))
