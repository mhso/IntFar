import api.util as api_util

async def handle_intfar_msg(client, message, target_id):
    current_month = api_util.current_month()

    def format_for_all(disc_id, monthly=False):
        person_to_check = client.get_discord_nick(disc_id, message.guild.id)
        games_played, intfar_reason_ids = client.database.get_intfar_stats(disc_id, monthly)
        games_played, intfars, _, pct_intfar = api_util.organize_intfar_stats(games_played, intfar_reason_ids)
        msg = f"{person_to_check}: Int-Far **{intfars}** times "
        msg += f"**({pct_intfar}%** of {games_played} games) "
        msg = client.insert_emotes(msg)
        return msg, intfars, pct_intfar

    def format_for_single(disc_id):
        person_to_check = client.get_discord_nick(disc_id, message.guild.id)
        games_played, intfar_reason_ids = client.database.get_intfar_stats(disc_id, False)
        games_played, intfars, intfar_counts, pct_intfar = api_util.organize_intfar_stats(games_played, intfar_reason_ids)
        intfars_of_the_month = client.database.get_intfars_of_the_month()
        user_is_ifotm = intfars_of_the_month != [] and intfars_of_the_month[0][0] == disc_id

        msg = f"{person_to_check} has been Int-Far **{intfars}** times "
        msg += "{emote_unlimited_chins}"
        if intfars > 0:
            monthly_games, monthly_infar_ids = client.database.get_intfar_stats(disc_id, True)
            monthly_games, monthly_intfars, _, pct_monthly = api_util.organize_intfar_stats(monthly_games, monthly_infar_ids)

            ratio_desc = "\n" + f"In total, he was Int-Far in **{pct_intfar}%** of his "
            ratio_desc += f"{games_played} games played.\n"
            ratio_desc += f"In {current_month}, he was Int-Far in **{monthly_intfars}** "
            ratio_desc += f"of his {monthly_games} games played (**{pct_monthly}%**)\n"

            reason_desc = "Int-Fars awarded so far:\n"
            for reason_id, reason in enumerate(api_util.INTFAR_REASONS):
                reason_desc += f" - {reason}: **{intfar_counts[reason_id]}**\n"

            longest_streak = client.database.get_longest_intfar_streak(disc_id)
            streak_desc = f"His longest Int-Far streak was **{longest_streak}** "
            streak_desc += "games in a row " + "{emote_suk_a_hotdok}\n"

            longest_non_streak = client.database.get_longest_no_intfar_streak(disc_id)
            no_streak_desc = "His longest streak of *not* being Int-Far was "
            no_streak_desc += f"**{longest_non_streak}** games in a row " + "{emote_pog}\n"

            relations_data = get_intfar_relation_stats(client, disc_id)[0]
            most_intfars_nick = client.get_discord_nick(relations_data[0], message.guild.id)
            relations_desc = f"He has inted the most when playing with {most_intfars_nick} "
            relations_desc += f"where he inted {relations_data[2]} games ({relations_data[3]}% "
            relations_desc += f"of {relations_data[1]} games)"
            relations_desc += "{emote_smol_gual}"

            msg += ratio_desc + reason_desc + streak_desc + no_streak_desc + relations_desc
            if user_is_ifotm:
                msg += f"\n**{person_to_check} currently stands to be Int-Far of the Month "
                msg += f"of {current_month}!** :tada:"
        msg = client.insert_emotes(msg)
        return msg

    response = ""
    if target_id is None: # Check intfar stats for everyone.
        messages_all_time = []
        messages_monthly = []
        for disc_id, _, _ in client.database.summoners:
            resp_str_all_time, intfars, pct_all_time = format_for_all(disc_id)
            resp_str_month, intfars_month, pct_month = format_for_all(disc_id, monthly=True)

            messages_all_time.append((resp_str_all_time, intfars, pct_all_time))
            messages_monthly.append((resp_str_month, intfars_month, pct_month))

        messages_all_time.sort(key=lambda x: (x[1], x[2]), reverse=True)
        messages_monthly.sort(key=lambda x: (x[1], x[2]), reverse=True)

        response = "**--- All time stats ---**\n"
        for data in messages_all_time:
            response += f"- {data[0]}\n"
        response += f"**--- Stats for {current_month} ---**\n"
        for data in messages_monthly:
            response += f"- {data[0]}\n"
    else: # Check intfar stats for a specific person.
        response = format_for_single(target_id)

    await message.channel.send(response)

def get_intfar_relation_stats(client, target_id):
    data = []
    games_relations, intfars_relations = client.database.get_intfar_relations(target_id)
    total_intfars = len(client.database.get_intfar_stats(target_id)[1])
    for disc_id, total_games in games_relations.items():
        intfars = intfars_relations.get(disc_id, 0)
        data.append(
            (
                disc_id, total_games, intfars, int((intfars / total_intfars) * 100),
                int((intfars / total_games) * 100)
            )
        )

    return sorted(data, key=lambda x: x[2], reverse=True)

async def handle_intfar_relations_msg(client, message, target_id):
    data = get_intfar_relation_stats(client, target_id)

    response = (
        f"Breakdown of players {client.get_discord_nick(target_id, message.guild.id)} " +
        "has inted with:\n"
    )
    for disc_id, total_games, intfars, intfar_ratio, games_ratio in data:
        nick = client.get_discord_nick(disc_id, message.guild.id)
        response += f"- {nick}: **{intfars}** times (**{intfar_ratio}%**) "
        response += f"(**{games_ratio}%** of **{total_games}** games)\n"

    await message.channel.send(response)

async def handle_intfar_criteria_msg(client, message, criteria=None):
    valid_criteria = True
    if criteria == "kda":
        crit_1 = client.config.kda_lower_threshold
        crit_2 = client.config.kda_death_criteria
        response = ("Criteria for being Int-Far by low KDA:\n" +
                    " - Having the lowest KDA of the people playing\n" +
                    f" - Having a KDA of less than {crit_1}\n" +
                    f" - Having more than {crit_2} deaths")
    elif criteria == "deaths":
        crit_1 = client.config.death_lower_threshold
        crit_2 = client.config.death_kda_criteria
        response = ("Criteria for being Int-Far by many deaths:\n" +
                    " - Having the most deaths of the people playing\n" +
                    f" - Having more than {crit_1} deaths\n"
                    f" - Having less than {crit_2} KDA")
    elif criteria == "kp":
        crit_1 = client.config.kp_lower_threshold
        crit_2 = client.config.kp_takedowns_criteria
        crit_3 = client.config.kp_structures_criteria
        response = ("Criteria for being Int-Far by low KP:\n" +
                    " - Having the lowest KP of the people playing\n" +
                    f" - Having a KP of less than {crit_1}%\n" +
                    f" - Having less than {crit_2} kills + assists\n" +
                    f" - Having less than {crit_3} structures destroyed")
    elif criteria == "vision":
        crit_1 = client.config.vision_score_lower_threshold
        crit_2 = client.config.vision_kda_criteria
        response = (
            "Criteria for being Int-Far by low vision score:\n" +
            " - Having the lowest vision score of the people playing\n" +
            f" - Having less than {crit_1} vision score\n" +
            f" - Having less than {crit_2} KDA\n" +
            " - The game being longer than 20 minutes"
        )
    else:
        response = "Possible criterias for getting Int-Far:"
        response += (
            "\n- Low KDA (kda)\n- Many Deaths (deaths)" +
            "\n- Low Kill Participation (kp)\n- Low Vision Score (vision)"
        )
        valid_criteria = False

    if valid_criteria:
        response += "\nThese criteria must all be met to be Int-Far."

    await message.channel.send(response)
