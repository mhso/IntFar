from api.awards import get_doinks_reasons, organize_doinks_stats

async def handle_doinks_msg(client, message, game, target_id):
    doinks_reasons = get_doinks_reasons(game)

    def get_doinks_stats(disc_id, expanded=True):
        person_to_check = client.get_discord_nick(disc_id, message.guild.id)
        doinks_reason_ids = client.database.get_doinks_stats(game, disc_id)
        total_doinks = client.database.get_doinks_count(game, disc_id)[1]
        doinks_counts = organize_doinks_stats(game, doinks_reason_ids)

        if game == "lol":
            champ_id, champ_count = client.database.get_league_champ_with_most_doinks(disc_id)
            champ_name = client.api_clients["lol"].get_champ_name(champ_id)

        msg = f"{person_to_check} has earned {total_doinks} " + "{emote_Doinks}"
        if expanded and total_doinks > 0:
            if game == "lol":
                msg += "\nHe has earned the most {emote_Doinks} " 
                msg += f"when playing **{champ_name}** (**{champ_count}** times)"

            reason_desc = "\n" + "Big doinks awarded so far:"
            for reason_id, reason in enumerate(doinks_reasons):
                reason_desc += f"\n- {doinks_reasons[reason]}: **{doinks_counts[reason_id]}**"

            msg += reason_desc

        return client.insert_emotes(msg), total_doinks

    response = ""
    if target_id is None: # Check doinks for everyone.
        messages = []
        for disc_id in client.database.users_by_game[game].keys():
            resp_str, doinks = get_doinks_stats(disc_id, expanded=False)
            messages.append((resp_str, doinks))

        messages.sort(key=lambda x: x[1], reverse=True)
        for resp_str, _ in messages:
            response += "- " + resp_str + "\n"

    else: # Check doinks for a specific person.
        response = get_doinks_stats(target_id)[0]

    await message.channel.send(response)

def get_doinks_relation_stats(client, game, target_id):
    data = []
    games_relations, doinks_relations = client.database.get_doinks_relations(game, target_id)
    doinks_games = client.database.get_doinks_count(game, target_id)[0]
    for disc_id, total_games in games_relations.items():
        doinks = doinks_relations.get(disc_id, 0)
        data.append(
            (
                disc_id, total_games, doinks, int((doinks / doinks_games) * 100),
                int((doinks / total_games) * 100)
            )
        )

    return sorted(data, key=lambda x: x[2], reverse=True)

async def handle_doinks_relations_msg(client, message, game, target_id):
    data = get_doinks_relation_stats(client, game, target_id)

    response = (
        f"Breakdown of who {client.get_discord_nick(target_id, message.guild.id)} " +
        "has gotten Big Doinks with:\n"
    )
    for disc_id, total_games, doinks, doinks_ratio, games_ratio in data:
        nick = client.get_discord_nick(disc_id, message.guild.id)
        response += f"- {nick}: **{doinks}** times (**{doinks_ratio}%**) "
        response += f"(**{games_ratio}%** of **{total_games}** games)\n"

    await message.channel.send(response)

async def handle_doinks_criteria_msg(client, game, message):
    doinks_reasons = get_doinks_reasons(game)

    response = "Criteria for being awarded {emote_Doinks}:\n"
    for reason in doinks_reasons:
        response += f"- {reason}: {doinks_reasons[reason]}\n"

    response += "Any of these being met will award 1 {emote_Doinks}"

    await message.channel.send(client.insert_emotes(response))
