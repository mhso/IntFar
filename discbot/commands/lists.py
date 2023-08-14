import random

from api import lists
from api.util import get_website_link

async def handle_random_champ_msg(client, message, list_name=None):
    if list_name is None:
        champ_list = list(client.riot_api.champ_names.values())
    else:
        champ_list = client.database.get_list_by_name(list_name)[1]
        if champ_list is not None:
            champ_list = [client.riot_api.champ_names[tup[1]] for tup in champ_list]

    if champ_list is None:
        response = f"No champion list found with the name `{list_name}` " + "{emote_sadge}"
    else:
        index = random.randint(0, len(champ_list)-1)
        champ_name = champ_list[index]
        sampled_list = list_name if list_name is not None else "all champs"
        response = f"Random champ sampled from `{sampled_list}`:\n"
        response += f"**{champ_name}**"

    await message.channel.send(client.insert_emotes(response))

async def handle_random_unplayed_msg(client, message):
    all_champs = set(client.riot_api.champ_names.keys())
    played_champs = set(x[0] for x in client.database.get_played_league_champs(message.author.id))

    unplayed_champs = [client.riot_api.get_champ_name(champ) for champ in (all_champs - played_champs)]
    if len(unplayed_champs) == 0: # All champs have been played.
        response = "You have already played every champ {emote_woahpikachu}"
    else:
        index = random.randint(0, len(unplayed_champs)-1)
        champ_name = unplayed_champs[index]
        response = f"Random champ sampled from your unplayed champs:\n"
        response += f"**{champ_name}**"

    await message.channel.send(client.insert_emotes(response))

async def handle_champ_lists_msg(client, message, target_id=None):
    lists = client.database.get_lists(target_id)

    if lists == []:
        response = (
            "There are currently no champion lists. " +
            f"Create one at {get_website_link('lol')}/lists/"
        )
    else:
        if target_id is None:
            response = "All champion lists:\n"
        else:
            owner_name = client.get_discord_nick(target_id, message.guild.id)
            response = f"Champion lists by {owner_name}:\n"

        for _, owner_id, name, count in lists:
            champs_quantifier = "champ" if count == 1 else "champs"
            response += f"- `{name}`: **{count}** {champs_quantifier}"
            if target_id is None:
                owner_name = client.get_discord_nick(owner_id, message.guild.id)
                response += f" (by {owner_name})"
            response += "\n"

        response += f"\nSee which champs are in each list at {get_website_link('lol')}/lists/ "
        response += "\nor with `!champs [list]`"
        response += "\nSelect a random champ from a list with `!random_champ [list]`"

    await message.channel.send(response)

async def handle_champs_msg(client, message, list_name):
    list_id, champ_list = client.database.get_list_by_name(list_name)
    if champ_list is None:
        response = f"No champion list found with the name `{list_name}` " + "{emote_sadge}"
    else:
        name, owner_id = client.database.get_list_data(list_id)
        owner_name = client.get_discord_nick(owner_id, message.guild.id)
        list_desc = f"The list `{name}` by {owner_name} "

        if champ_list == []:
            response = f"{list_desc} contains no champions."
        else:
            max_champs = 12
            response = f"{list_desc} contains the following champions:"
            champions = [client.riot_api.champ_names[tup[1]] for tup in champ_list]
            champions.sort()
            for champ_name in champions[:max_champs]:
                response += f"\n- `{champ_name}`"

            if len(champions) > max_champs:
                champs_left = len(champions) - max_champs
                response += f"\n- `(and {champs_left} more)`"
                response += f"\nSee all the champs at: {get_website_link('lol')}/lists/{list_id}"

            response += f"\nWrite `!random_champ {name}` to pick a random champ from this list."

    await message.channel.send(client.insert_emotes(response))

async def handle_create_list_msg(client, message, list_name):
    success, response = lists.create_list(message.author.id, list_name, client.database)

    if success:
        response = f"Champion list `{list_name}` has been created " + "{emote_poggers}"
        response += f"\nUse `!add_champ {list_name} [champ1], [champ2], ...` "
        response += "to add champions to the list."
    else:
        response = f"Could not create list: {response}."

    await message.channel.send(client.insert_emotes(response))

def parse_champs_params(client, args):
    list_name = args[0]

    list_id = client.database.get_list_by_name(list_name)[0]
    if list_id is None:
        raise ValueError(f"No champion list found with the name `{list_name}` " + "{emote_sadge}")

    # Make new list, separated by commas instead of spaces.
    champ_args = " ".join(args[1:]).split(",")

    champ_ids = []
    for champ_name in champ_args:
        champ_id = client.riot_api.try_find_champ(champ_name)
        if champ_id is None:
            raise ValueError(f"Invalid champion name: `{champ_name}`")

        champ_ids.append(champ_id)

    return [list_id, champ_ids]

async def handle_add_champs(client, message, list_id, champ_ids):
    success, response = lists.add_champ_to_list(
        message.author.id, list_id, champ_ids, client.riot_api, client.database
    )
    if success:
        list_name = client.database.get_list_data(list_id)[0]
        response = f"{response} to `{list_name}`."
    else:
        response = f"Could not add champ to list: {response}."

    await message.channel.send(client.insert_emotes(response))

async def handle_delete_list(client, message, list_name):
    list_id = client.database.get_list_by_name(list_name)[0]
    if list_id is None:
        response = f"No champion list found with the name `{list_name}` " + "{emote_sadge}"
    else:
        success, response = lists.delete_list(message.author.id, list_id, client.database)
        if success:
            response = f"The list `{list_name}` has been deleted."
        else:
            response = f"Could not delete `{list_name}`: {response}."

    await message.channel.send(client.insert_emotes(response))

async def handle_remove_champ(client, message, list_id, champ_ids):
    success, response = lists.delete_by_champ_ids(
        message.author.id, list_id, champ_ids, client.database
    )
    if success:
        list_name = client.database.get_list_data(list_id)[0]
        response = f"{response} from `{list_name}`."
    else:
        response = f"Could not remove champ from list: {response}."

    await message.channel.send(client.insert_emotes(response))

async def handle_random_nochest(client, message, target_id=None):
    summ_data = client.database.game_user_data_from_discord_id(target_id, "lol")
    champion_mastery_data = client.riot_api.get_champion_mastery(summ_data.ingame_id)

    # Filter champs with no chest granted.
    no_chest_champs = []
    for mastery_data in champion_mastery_data:
        if not mastery_data["chestGranted"]:
            champion_id = mastery_data["championId"]
            no_chest_champs.append(client.riot_api.get_champ_name(champion_id))

    if len(no_chest_champs) == 0: # Chests have been earned on every champ.
        response = "You have already earned a chest on every champ {emote_woahpikachu}"
    else:
        index = random.randint(0, len(no_chest_champs)-1)
        champ_name = no_chest_champs[index]
        response = f"Random champ that you have not earned a chest on:\n"
        response += f"**{champ_name}**"

    await message.channel.send(client.insert_emotes(response))

async def handle_best_nochest(client, message, target_id=None):
    """
    Handler for 'best_nochest' command. Finds the champion with the highest winrate
    for the given player where no chest has yet been obtained.
    """
    summ_data = client.database.game_user_data_from_discord_id(target_id, "lol")
    champion_mastery_data = client.riot_api.get_champion_mastery(summ_data.ingame_id)

    # Filter champs with no chest granted.
    no_chest_champs = []
    for mastery_data in champion_mastery_data:
        if not mastery_data["chestGranted"]:
            no_chest_champs.append(mastery_data["championId"])

    if len(no_chest_champs) == 0: # Chests have been earned on every champ.
        response = "You have already earned a chest on every champ {emote_woahpikachu}"
    else:
        # Get highest winrate of all the champs with no chest gained.
        result = client.database.get_min_or_max_league_winrate_champ(
            target_id, True, no_chest_champs, return_top_n=5, min_games=3
        )

        if result == []:
            response = "No champs found with enough games, where you don't have a chest :("

        else:
            quantity_desc = f"These are the {len(result)} champs" if len(result) > 1 else "This is the champ"
            response = (
                f"{quantity_desc} with highest "
                "winrate and no chest earned:"
            )

            for winrate, games, champ_id in result:
                champ_name = client.riot_api.get_champ_name(champ_id)

                response += f"\n - **{champ_name}** "
                response += f"(**{winrate:.1f}%** wins in **{games}** games)"

    await message.channel.send(client.insert_emotes(response))
