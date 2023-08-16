from datetime import datetime

TESTING = False

class LANInfo:
    def __init__(self, start_time, end_time, participants, guild_id):
        self.start_time = start_time
        self.end_time = end_time
        self.participants = participants
        self.guild_id = guild_id

if not TESTING:
    LAN_PARTIES = {
        "october_21": LANInfo(
            datetime(2021, 10, 30, 14, 0, 0).timestamp(),
            datetime(2021, 10, 31, 12, 0, 0).timestamp(),
            {
                115142485579137029: "Dave",
                172757468814770176: "Murt",
                267401734513491969: "Gual",
                331082926475182081: "Muds",
                347489125877809155: "Nønø"
            },
            803987403932172359 # Core Nibs
        ),
        "april_22": LANInfo(
            datetime(2022, 4, 15, 14, 0, 0).timestamp(),
            datetime(2022, 4, 16, 12, 0, 0).timestamp(),
            {
                115142485579137029: "Dave",
                172757468814770176: "Murt",
                267401734513491969: "Gual",
                331082926475182081: "Muds",
                347489125877809155: "Nønø"
            },
            803987403932172359 # Core Nibs
        ),
        "september_23": LANInfo(
            datetime(2023, 9, 9, 14, 0, 0).timestamp(),
            datetime(2023, 9, 10, 12, 0, 0).timestamp(),
            {
                115142485579137029: "Dave",
                172757468814770176: "Murt",
                267401734513491969: "Gual",
                331082926475182081: "Muds",
                347489125877809155: "Nønø"
            },
            803987403932172359 # Core Nibs
        )
    }
else: # Use old data for testing.
    LAN_PARTIES = {
        "april_22": LANInfo(
            1631470327,
            1631655446,
            {
                115142485579137029: "Dave",
                172757468814770176: "Murt",
                267401734513491969: "Gual",
                331082926475182081: "Muds",
                347489125877809155: "Nønø"
            },
            619073595561213953 # League Nibs
        )
    }

def is_lan_ongoing(timestamp, guild_id=None):
    lan_date = list(filter(
        lambda x: timestamp > LAN_PARTIES[x].start_time and timestamp < LAN_PARTIES[x].end_time,
        LAN_PARTIES
    ))

    if lan_date == []:
        return False

    latest_lan_info = LAN_PARTIES[lan_date[0]]

    # Check if guild_id matches, if given.
    return guild_id is None or guild_id == latest_lan_info.guild_id

def get_tilt_value(recent_games):
    # Tilt value ranges from 0-12
    tilt_value = 0
    max_value = 12
    max_contribution = 4
    min_contribution = 1
    win_contribution = 0.75
    prev_result = 0
    streak = 1
    for index, result in enumerate(recent_games):
        tilt_contribution = max(max_contribution - index, min_contribution)
        if index > 0:
            if prev_result == result:
                streak += 1
            else:
                streak = 1

            tilt_contribution *= (streak // 2)

        if result == 1:
            tilt_contribution *= -win_contribution

        tilt_value += tilt_contribution

        prev_result = result

    # Clamp value to between 0-12
    tilt_value = max(min(tilt_value, max_value), 0)

    colors = [
        "rgb(124, 252, 0)", "rgb(156, 252, 0)", "rgb(188, 253, 0)",
        "rgb(220, 253, 0)", "rgb(252, 253, 0)", "rgb(252, 223, 0)",
        "rgb(253, 191, 0)", "rgb(254, 159, 0)", "rgb(254, 128, 0)",
        "rgb(254, 96, 0)", "rgb(254, 64, 0)", "rgb(255, 0, 0)"
    ]
    color = colors[min(round(tilt_value), 11)]

    # Convert to percent.
    return int((tilt_value / max_value) * 100), color

def get_average_stats(database, lan_info):
    all_stats = database.get_league_lan_stats(
        time_after=lan_info.start_time,
        time_before=lan_info.end_time,
        guild_id=lan_info.guild_id
    )

    if all_stats == []:
        return None, None

    keys = [
        "Kills", "Deaths", "KDA", "CS", "CS/min", "Damage",
        "Gold", "KP", "Vision Wards", "Vision Score"
    ]

    all_avg_stats = {key: [] for key in keys}
    for disc_id in all_stats:
        avg_stats = [0 for _ in keys]
        total_kda = 0

        for stat_tuple in all_stats[disc_id]:
            total_kda += (stat_tuple[0] + stat_tuple[2]) / stat_tuple[1]
            for index, stat_value in enumerate(stat_tuple):
                avg_stats[index] += stat_value
            avg_stats[2] = total_kda

        for index, sum_value in enumerate(avg_stats):
            all_avg_stats[keys[index]].append((disc_id, sum_value / len(all_stats[disc_id])))

    for key in all_avg_stats:
        reverse = False if key == "Deaths" else True
        all_avg_stats[key].sort(key=lambda x: x[1], reverse=reverse)

    all_ranks = {}

    for stat_name in all_avg_stats:
        stats = all_avg_stats[stat_name]

        for index, (disc_id, _) in enumerate(stats):
            all_ranks[disc_id] = all_ranks.get(disc_id, 0) + (index + 1)

    all_ranks_list = [(k, v) for k, v in all_ranks.items()]
    all_ranks_list.sort(key=lambda x: x[1])

    return all_avg_stats, all_ranks_list
