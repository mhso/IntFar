from api.util import SUPPORTED_GAMES
from api.awards import get_doinks_reasons, organize_doinks_stats

async def handle_doinks_msg(client, message, game, target_id):
    database = client.game_databases[game]
    doinks_reasons = get_doinks_reasons(game)

    def get_doinks_stats(disc_id, expanded=True):
        person_to_check = client.get_discord_nick(disc_id, message.guild.id)
        doinks_reason_ids = database.get_doinks_stats(disc_id)
        total_doinks = database.get_doinks_count(disc_id)[1]
        doinks_counts = organize_doinks_stats(game, doinks_reason_ids)

        played_id, played_count = database.get_played_with_most_doinks(disc_id)()
        played_name = client.api_clients[game].get_playable_name(played_id)

        msg = f"{person_to_check} has earned {total_doinks} " + "{emote_Doinks}"
        if expanded and total_doinks > 0:
            msg += "\nHe has earned the most {emote_Doinks} " 
            msg += f"when playing **{played_name}** (**{played_count}** times)"

            reason_desc = "\n" + "Big doinks awarded so far:"
            for reason_id, reason in enumerate(doinks_reasons):
                reason_desc += f"\n- {doinks_reasons[reason]}: **{doinks_counts[reason_id]}**"

            msg += reason_desc

        return client.insert_emotes(msg), total_doinks

    response = ""
    if target_id is None: # Check doinks for everyone.
        messages = []
        for disc_id in database.game_users.keys():
            resp_str, doinks = get_doinks_stats(disc_id, expanded=False)
            messages.append((resp_str, doinks))

        messages.sort(key=lambda x: x[1], reverse=True)
        for resp_str, _ in messages:
            response += "- " + resp_str + "\n"

    else: # Check doinks for a specific person.
        response = get_doinks_stats(target_id)[0]

    await message.channel.send(response)

def get_doinks_relation_stats(client, game, target_id):
    database = client.game_databases[game]
    data = []
    games_relations, doinks_relations = database.get_doinks_relations(target_id)
    doinks_games = database.get_doinks_count(target_id)[0]
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

async def handle_doinks_criteria_msg(client, message, game):
    doinks_reasons = get_doinks_reasons(game)
    game_name = SUPPORTED_GAMES[game]

    response = "Criteria for being awarded {emote_Doinks}: in " + game_name + "\n"
    for reason in doinks_reasons:
        response += f"- **{reason}**: {doinks_reasons[reason]}\n"

    response += "Any of these being met will award 1 {emote_Doinks}"

    await message.channel.send(client.insert_emotes(response))
