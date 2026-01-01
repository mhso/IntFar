from datetime import datetime
from intfar.api.game_data import get_stat_quantity_descriptions, get_formatted_stat_names, get_formatted_stat_value

def get_val_str(val_before, val_now, maximize=True, fmt_func = None):
    val_str = ""
    better = None

    if val_before is None:
        val_str += "Unknown -> "
    else:
        val_str += f"{fmt_func(val_before) if fmt_func else val_before} -> "
        better = val_now > val_before if maximize else val_now < val_before

    val_str += f"{fmt_func(val_now) if fmt_func else val_now}"
    if better is not None and val_now != val_before:
        emoji = "🔼" if better else "🔻"
        val_str += f" {emoji}"

    return val_str

async def handle_end_of_split_msg(client, disc_id):
    database = client.game_databases["lol"]

    offset_1 = 30 * 24 * 60 * 60
    offset_2 = 190 * 24 * 60 * 60

    curr_split_start = database.get_split_start(offset_1)
    prev_split_start = database.get_split_start(offset_2)

    stats_to_get = list(get_stat_quantity_descriptions("lol").keys())
    stat_names = get_formatted_stat_names("lol")
    split_data = database.get_split_summary_data(disc_id, stats_to_get, prev_split_start, curr_split_start)

    prev_split_fmt = datetime.fromtimestamp(prev_split_start).strftime("%Y-%m-%d")
    curr_split_fmt = datetime.fromtimestamp(curr_split_start).strftime("%Y-%m-%d")

    # Create list of average stats before / after
    stats_before = split_data["avg_stats_before"]
    stats_now = split_data["avg_stats_now"]
    stats_data = []
    for stat in stats_to_get:
        def fmt_stat_val(val):
            return get_formatted_stat_value("lol", stat, val)

        stat_line = f"* **{stat_names.get(stat, 'First blood')}**: "

        val_before = stats_before[stat][1]
        val_now = stats_now[stat][1]

        stat_line += get_val_str(val_before, val_now, stat != "deaths", fmt_stat_val)
        stats_data.append(stat_line)

    # Create final message
    message = (
        "Howdy partner!\n"
        "Here is your *League of Legends* ranked split summary "
        f"for **{prev_split_fmt}** - **{curr_split_fmt}**!!!\n"
        "Most stats are shown as <previous_split> -> <current_split> so you can see if you've goten better or worse!\n\n"
    )

    # Add games played to message
    games_before = split_data["games_before"][0]
    games_now = split_data["games_after"][0]
    wins_before = split_data["games_before"][3]
    wins_now = split_data["games_after"][3]
    message += f"**Games played**: {get_val_str(games_before, games_now)}\n"

    def fmt_winrate(val):
        return f"{val:.2f}%"

    message += f"**Winrate**: {get_val_str(wins_before / games_before * 100, wins_now / games_now * 100, fmt_func=fmt_winrate)}\n\n"

    # Add highest/lowest winrate champ to message
    best_champ_wr, best_champ_games, best_champ_id = split_data["best_wr_champ"]
    worst_champ_wr, worst_champ_games, worst_champ_id = split_data["worst_wr_champ"]

    best_champ_name = client.api_clients["lol"].get_playable_name(best_champ_id)
    worst_champ_name = client.api_clients["lol"].get_playable_name(worst_champ_id)

    message += f"**Best Champ**: {best_champ_name} ({best_champ_wr:.2f}% winrate in {best_champ_games} games)\n"
    message += f"**Worst Champ**: {worst_champ_name} ({worst_champ_wr:.2f}% winrate in {worst_champ_games} games)\n\n"

    # Add Int-Fars before / after to message
    intfars_before = split_data["intfars_before"]
    intfars_now = split_data["intfars_after"]

    message += f"**Int-Fars awarded**: {get_val_str(intfars_before, intfars_now)}\n"

    # Add Doinks before / after to message
    doinks_games_before, doinks_total_before = split_data["doinks_before"]
    doinks_games_now, doinks_total_now = split_data["doinks_after"]

    message += (
        f"**Games with doinks**: {get_val_str(doinks_games_before, doinks_games_now)}\n"
        f"**Total doinks**: {get_val_str(doinks_total_before, doinks_total_now)}\n\n"
    )

    # Add highest rank info to message
    highest_rank_solo = split_data["solo_highest"]
    highest_rank_flex = split_data["flex_highest"]

    message += (
        f"**Peak Solo rank**: {get_formatted_stat_value('lol', 'rank_solo', highest_rank_solo)}\n"
        f"**Peak Flex rank**: {get_formatted_stat_value('lol', 'rank_flex', highest_rank_flex)}"
    )

    # Add stats data to message
    if stats_data != []:
        message += "\n\n-=-=-=-=- Average Stats -=-=-=-=-\n"
        message += "\n".join(stats_data)

    # Add role winrate data to message
    roles_data = []
    for winrate, games, role in split_data["role_winrates"]:
        if winrate is None:
            continue

        role_str = f"* **{role}**: {winrate:.2f}% winrate in {games} games"
        roles_data.append(role_str)

    if roles_data != []:
        message += "\n\n-=-=-=-=- Role Winrates -=-=-=-=-\n"
        message += "\n".join(roles_data)

    # Add info about champs played
    played_before = split_data["played_before"]
    played_after = split_data["played_after"]

    message += f"**\n\nUnique champs played**: {played_before} -> {played_after}"

    await client.send_dm(message, disc_id)
