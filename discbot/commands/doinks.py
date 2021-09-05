import api.util as api_util

async def handle_doinks_msg(client, message, target_id):
    def get_doinks_stats(disc_id, expanded=True):
        person_to_check = client.get_discord_nick(disc_id, message.guild.id)
        doinks_reason_ids = client.database.get_doinks_stats(disc_id)
        doinks_counts = api_util.organize_doinks_stats(doinks_reason_ids)
        champ_id, champ_count = client.database.get_champ_with_most_doinks(disc_id)
        champ_name = client.riot_api.get_champ_name(champ_id)
        msg = f"{person_to_check} has earned {len(doinks_reason_ids)} " + "{emote_Doinks}"
        if expanded and len(doinks_reason_ids) > 0:
            msg += "\nHe has earned the most {emote_Doinks} " 
            msg += f"when playing **{champ_name}** (**{champ_count}** times)"
            reason_desc = "\n" + "Big doinks awarded so far:"
            for reason_id, reason in enumerate(api_util.DOINKS_REASONS):
                reason_desc += f"\n - {reason}: **{doinks_counts[reason_id]}**"

            msg += reason_desc

        return client.insert_emotes(msg), len(doinks_reason_ids)

    response = ""
    if target_id is None: # Check doinks for everyone.
        messages = []
        for disc_id, _, _ in client.database.summoners:
            resp_str, doinks = get_doinks_stats(disc_id, expanded=False)
            messages.append((resp_str, doinks))
        messages.sort(key=lambda x: x[1], reverse=True)
        for resp_str, _ in messages:
            response += "- " + resp_str + "\n"
    else: # Check doinks for a specific person.
        response = get_doinks_stats(target_id)[0]

    await message.channel.send(response)

def get_doinks_relation_stats(client, target_id):
    data = []
    games_relations, doinks_relations = client.database.get_doinks_relations(target_id)
    total_doinks = len(client.database.get_doinks_stats(target_id))
    for disc_id, total_games in games_relations.items():
        doinks = doinks_relations.get(disc_id, 0)
        data.append(
            (
                disc_id, total_games, doinks, int((doinks / total_doinks) * 100),
                int((doinks / total_games) * 100)
            )
        )

    return sorted(data, key=lambda x: x[2], reverse=True)

async def handle_doinks_relations_msg(client, message, target_id):
    data = client.get_doinks_relation_stats(target_id)

    response = (
        f"Breakdown of who {client.get_discord_nick(target_id, message.guild.id)} " +
        "has gotten Big Doinks with:\n"
    )
    for disc_id, total_games, doinks, doinks_ratio, games_ratio in data:
        nick = client.get_discord_nick(disc_id, message.guild.id)
        response += f"- {nick}: **{doinks}** times (**{doinks_ratio}%**) "
        response += f"(**{games_ratio}%** of **{total_games}** games)\n"

    await message.channel.send(response)

async def handle_doinks_criteria_msg(client, message):
    response = "Criteria for being awarded {emote_Doinks}:"
    for reason in api_util.DOINKS_REASONS:
        response += f"\n - {reason}"
    await message.channel.send(client.insert_emotes(response))
