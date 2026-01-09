from datetime import datetime
from typing import Dict, Tuple

from mhooge_flask.logging import logger

from intfar.api.game_databases.lol import LoLGameDatabase
from intfar.api.game_data import get_stat_quantity_descriptions, get_formatted_stat_names, get_formatted_stat_value

def has_ranks_reset(database: LoLGameDatabase, player_ranks: Dict[str, Tuple[str, str]]):
    all_reset = True
    for player_id in player_ranks:
        curr_rank_solo, curr_rank_flex = database.get_current_rank(player_id)
        new_rank_solo, new_rank_flex = player_ranks[player_id]

        if all(rank is None for rank in (curr_rank_solo, curr_rank_flex, new_rank_solo, new_rank_flex)):
            continue

        if (
            (curr_rank_solo is not None and new_rank_solo is not None)
            or (curr_rank_flex is not None and new_rank_flex is not None)
        ):
            all_reset = False
            break

    return all_reset

def should_send_split_message(database, disc_id, prev_split_start, curr_split_start):
    min_games = 10
    latest_timestamp = database.get_split_message_status(disc_id)

    return (
        latest_timestamp is None
        or (
            latest_timestamp < curr_split_start
            and database.get_games_count(disc_id, prev_split_start)[0] >= min_games
        )
    )

def get_val_str(val_before, val_now, maximize=True, fmt_func=None):
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

def get_end_of_split_msg(database, api_client, disc_id, prev_split_start, curr_split_start):
    stats_to_get = list(get_stat_quantity_descriptions("lol").keys())
    stat_names = get_formatted_stat_names("lol")
    split_data = database.get_split_summary_data(disc_id, stats_to_get, prev_split_start, curr_split_start)

    logger.bind(event="end_of_split_data", split_data=split_data).info(f"End of split data: {split_data}")

    split_start_fmt = datetime.fromtimestamp(curr_split_start).strftime("%Y-%m-%d")
    split_end_fmt = datetime.now().strftime("%Y-%m-%d")

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
        "Howdy fellow *League of Legends* enjoyer!\n"
        "Here is your ranked split summary "
        f"for **{split_start_fmt}** - **{split_end_fmt}** " + "{emote_nono}\n\n"
        "**Note:** Most stats are shown as a comparison between previous split " 
        "and this split, so you can see if you've goten better or worse!\n\n"
    )

    # Add games played to message
    games_before = split_data["games_before"][0]
    games_now = split_data["games_after"][0]
    game_time_before = split_data["games_before"][3]
    wins_before = split_data["games_before"][4]
    wins_now = split_data["games_after"][4]
    game_time_after = split_data["games_after"][3]

    message += f"**Games played**: {get_val_str(games_before, games_now)}\n"

    def fmt_winrate(val):
        return f"{val:.2f}%"
    
    def fmt_playtime(val):
        return f"{val / 60 / 60:.1f} hours"

    message += f"**Winrate**: {get_val_str(wins_before / games_before * 100, wins_now / games_now * 100, fmt_func=fmt_winrate)}\n"
    message += f"**Total playtime**: {get_val_str(game_time_before, game_time_after, fmt_func=fmt_playtime)}\n\n"

    # Add info about champs played
    played_before = split_data["played_before"]
    played_after = split_data["played_after"]

    message += f"**Unique champs played**: {played_before} -> {played_after}\n\n"

    # Add highest/lowest winrate champ to message
    best_champ_wr, best_champ_games, best_champ_id = split_data["best_wr_champ"]
    if best_champ_wr is not None:
        best_champ_name = api_client.get_playable_name(best_champ_id)
        message += f"**Best Champ** (min. 5 games): **{best_champ_name}** ({best_champ_wr:.2f}% winrate in {best_champ_games} games)\n"
    
    worst_champ_wr, worst_champ_games, worst_champ_id = split_data["worst_wr_champ"]
    if worst_champ_wr is not None:
        worst_champ_name = api_client.get_playable_name(worst_champ_id)
        message += f"**Worst Champ** (min. 5 games): **{worst_champ_name}** ({worst_champ_wr:.2f}% winrate in {worst_champ_games} games)\n\n"

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

    current_rank_solo = split_data["solo_current"]
    highest_rank_solo = split_data["solo_highest"]

    # Add solo rank info to message
    message += "**-=-=-=-=- Solo/Duo Rank -=-=-=-=-**\n"
    message += (
        f"**Current**: {get_formatted_stat_value('lol', 'rank_solo', current_rank_solo)}\n"
        f"**Peak**: {get_formatted_stat_value('lol', 'rank_solo', highest_rank_solo)}"
    )

    # Add flex rank info to message
    current_rank_flex = split_data["flex_current"]
    highest_rank_flex = split_data["flex_highest"]
    message += "\n\n**-=-=-=-=- Flex Rank -=-=-=-=-**\n"
    message += (
        f"**Current**: {get_formatted_stat_value('lol', 'rank_solo', current_rank_flex)}\n"
        f"**Peak**: {get_formatted_stat_value('lol', 'rank_solo', highest_rank_flex)}"
    )

    # Add stats data to message
    if stats_data != []:
        message += "\n\n**-=-=-=-=- Average Stats -=-=-=-=-**\n"
        message += "\n".join(stats_data)

    # Add role winrate data to message
    roles_data = []
    for winrate, games, role in split_data["role_winrates"]:
        if winrate is None:
            continue

        role_str = f"* **{role}**: **{winrate:.2f}%** winrate in {games} games"
        roles_data.append(role_str)

    if roles_data != []:
        message += "\n\n**-=-=-=-=- Role Winrates -=-=-=-=-**\n"
        message += "\n".join(roles_data)

    return message
