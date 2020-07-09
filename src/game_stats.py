def calc_kda(stats):
    return (stats["kills"] + stats["assists"]) / stats["deaths"]

def calc_kill_participation(stats, all_entries):
    total_kills = sum(entry[1]["kills"] for entry in all_entries)
    return int(float(stats["kills"]) / float(total_kills) * 100)

def get_outlier(data, key, asc=True):
    if key == "kda":
        sorted_data = sorted(data, key=lambda x: calc_kda(x[1]), reverse=not asc)
        return sorted_data[0]
    elif key == "kp":
        sorted_data = sorted(data, key=lambda x: calc_kill_participation(x[1], data), reverse=not asc)
        return sorted_data[0]

    sorted_data = sorted(data, key=lambda entry: entry[1][key], reverse=not asc)
    return sorted_data[0]

def get_outlier_stat(stat, data):
    most_id, stats = get_outlier(data, stat, asc=True)
    most = stats[stat]
    least_id, stats = get_outlier(data, stat, asc=False)
    least = stats[stat]
    return most_id, most, least_id, least
