def calc_kda(data_entry):
    stats = data_entry[1]
    return (stats["kills"] + stats["assists"]) / stats["deaths"]

def calc_kill_participation(data_entry, all_entries):
    total_kills = sum(entry["kills"] for entry in all_entries)
    return float(data_entry["kills"]) / float(total_kills)

def get_outlier(data, key, asc=True):
    if key == "kda":
        sorted_data = sorted(data, key=calc_kda, reverse=asc)
        return sorted_data[0]
    elif key == "kp":
        sorted_data = sorted(data, key=lambda x: calc_kill_participation(x, data), reverse=asc)

    sorted_data = sorted(data, key=lambda entry: entry[1][key], reverse=asc)
    return sorted_data[0]
