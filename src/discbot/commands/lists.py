import random

from api import lists
from api.util import get_website_link
from discbot.commands.base import *

_GAME = "lol"

class RandomChampCommand(Command):
    NAME = "random_champ"
    DESCRIPTION = (
        "Pick a random champion. If a list is given, only champs from this list is used. " +
        f"Champion lists can be created at {get_website_link('lol')}/lists/"
    )
    OPTIONAL_PARAMS = [CommandParam("list")]

    async def handle(self, list_name: str = None):
        if list_name is None:
            champ_list = list(self.client.api_clients[_GAME].champ_names.values())
        else:
            champ_list = self.client.game_databases[_GAME].get_list_by_name(list_name)[1]
            if champ_list is not None:
                champ_list = [self.client.api_clients[_GAME].champ_names[tup[1]] for tup in champ_list]

        if champ_list is None:
            response = f"No champion list found with the name `{list_name}` " + "{emote_sadge}"
        else:
            index = random.randint(0, len(champ_list)-1)
            champ_name = champ_list[index]
            sampled_list = list_name if list_name is not None else "all champs"
            response = f"Random champ sampled from `{sampled_list}`:\n"
            response += f"**{champ_name}**"

        await self.message.channel.send(self.client.insert_emotes(response))

class RandomUnplayedCommand(Command):
    NAME = "random_unplayed"
    DESCRIPTION = (
        "Pick a random champion. If a list is given, only champs from this list is used. " +
        f"Champion lists can be created at {get_website_link('lol')}/lists/"
    )
    OPTIONAL_PARAMS = [CommandParam("list")]

    async def handle(self, target_id: int):
        all_champs = set(self.client.api_clients[_GAME].champ_names.keys())
        played_champs = set(x[0] for x in self.client.game_databases[_GAME].get_played_ids(target_id))

        unplayed_champs = [self.client.api_clients[_GAME].get_champ_name(champ) for champ in (all_champs - played_champs)]
        if len(unplayed_champs) == 0: # All champs have been played.
            response = "You have already played every champ {emote_woahpikachu}"
        else:
            index = random.randint(0, len(unplayed_champs)-1)
            champ_name = unplayed_champs[index]
            response = f"Random champ sampled from your unplayed champs:\n"
            response += f"**{champ_name}**"

        await self.message.channel.send(self.client.insert_emotes(response))

class ChampListsCommand(Command):
    NAME = "champ_lists"
    DESCRIPTION = "See a list of all champion lists, or those created by a specific person."
    TARGET_ALL = True
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = [TargetParam("person", None)]

    async def handle(self, target_id: int = None): 
        lists = self.client.game_databases[_GAME].get_lists(target_id)

        if lists == []:
            response = (
                "There are currently no champion lists. " +
                f"Create one at {get_website_link('lol')}/lists/"
            )
        else:
            if target_id is None:
                response = "All champion lists:\n"
            else:
                owner_name = self.client.get_discord_nick(target_id, self.message.guild.id)
                response = f"Champion lists by {owner_name}:\n"

            for _, owner_id, name, count in lists:
                champs_quantifier = "champ" if count == 1 else "champs"
                response += f"- `{name}`: **{count}** {champs_quantifier}"
                if target_id is None:
                    owner_name = self.client.get_discord_nick(owner_id, self.message.guild.id)
                    response += f" (by {owner_name})"
                response += "\n"

            response += f"\nSee which champs are in each list at {get_website_link('lol')}/lists/ "
            response += "\nor with `!champs [list]`"
            response += "\nSelect a random champ from a list with `!random_champ [list]`"

        await self.message.channel.send(response)

class ChampsCommand(Command):
    NAME = "champs"
    DESCRIPTION = "See what champs are in a given champion list."
    MANDATORY_PARAMS = [CommandParam("list")]

    async def handle(self, list_name: str):
        list_id, champ_list = self.client.game_databases[_GAME].get_list_by_name(list_name)
        if champ_list is None:
            response = f"No champion list found with the name `{list_name}` " + "{emote_sadge}"
        else:
            name, owner_id = self.client.game_databases[_GAME].get_list_data(list_id)
            owner_name = self.client.get_discord_nick(owner_id, self.message.guild.id)
            list_desc = f"The list `{name}` by {owner_name} "

            if champ_list == []:
                response = f"{list_desc} contains no champions."
            else:
                max_champs = 12
                response = f"{list_desc} contains the following champions:"
                champions = [self.client.api_clients[_GAME].champ_names[tup[1]] for tup in champ_list]
                champions.sort()
                for champ_name in champions[:max_champs]:
                    response += f"\n- `{champ_name}`"

                if len(champions) > max_champs:
                    champs_left = len(champions) - max_champs
                    response += f"\n- `(and {champs_left} more)`"
                    response += f"\nSee all the champs at: {get_website_link('lol')}/lists/{list_id}"

                response += f"\nWrite `!random_champ {name}` to pick a random champ from this list."

        await self.message.channel.send(self.client.insert_emotes(response))

class CreateListCommand(Command):
    NAME = "create_list"
    DESCRIPTION = "Create a list of champions."
    MANDATORY_PARAMS = [CommandParam("name")]

    async def handle_create_list_msg(self, list_name):
        success, response = lists.create_list(self.message.author.id, list_name, self.client.game_databases[_GAME])

        if success:
            response = f"Champion list `{list_name}` has been created " + "{emote_poggers}"
            response += f"\nUse `!add_champ {list_name} [champ1], [champ2], ...` "
            response += "to add champions to the list."
        else:
            response = f"Could not create list: {response}."

        await self.message.channel.send(self.client.insert_emotes(response))

class AddOrRemoveCommand(Command):
    async def parse_args(self, args: List[str]):
        list_name = args[0]

        list_id = self.client.game_databases[_GAME].get_list_by_name(list_name)[0]
        if list_id is None:
            raise ValueError(f"No champion list found with the name `{list_name}` " + "{emote_sadge}")

        # Make new list, separated by commas instead of spaces.
        champ_args = " ".join(args[1:]).split(",")

        champ_ids = []
        for champ_name in champ_args:
            champ_id = self.client.api_clients[_GAME].try_find_playable_id(champ_name)
            if champ_id is None:
                raise ValueError(f"Invalid champion name: `{champ_name}`")

            champ_ids.append(champ_id)

        return [list_id, champ_ids]

class AddChampsCommand(AddOrRemoveCommand):
    NAME = "add_champ"
    DESCRIPTION = (
        "Add champion(s) to given list. Add more than one champ at once " +
        "with comma-separated list. Fx. `!add_champ some_list aatrox, ahri, akali`"
    )
    ACCESS_LEVEL = "all"
    MANDATORY_PARAMS = [CommandParam("list"), CommandParam("champion(s)")]

    async def handle(self, list_id: int, champ_ids: List[int]):
        success, response = lists.add_champ_to_list(
            self.message.author.id, list_id, champ_ids, self.client.api_clients[_GAME], self.client.game_databases[_GAME]
        )
        if success:
            list_name = self.client.game_databases[_GAME].get_list_data(list_id)[0]
            response = f"{response} to `{list_name}`."
        else:
            response = f"Could not add champ to list: {response}."

        await self.message.channel.send(self.client.insert_emotes(response))

class RemoveChampsCommand(AddOrRemoveCommand):
    NAME = "remove_champ"
    DESCRIPTION = (
        "Remove champion(s) from given list. Remove more than one champ at once " +
        "with comma-separated list. Fx. `!remove_champ some_list aatrox, ahri, akali`"
    )
    ACCESS_LEVEL = "all"
    MANDATORY_PARAMS = [CommandParam("list"), CommandParam("champion(s)")]

    async def handle(self, list_id: int, champ_ids: List[int]):
        success, response = lists.delete_by_champ_ids(
            self.message.author.id, list_id, champ_ids, self.client.game_databases[_GAME]
        )
        if success:
            list_name = self.client.game_databases[_GAME].get_list_data(list_id)[0]
            response = f"{response} from `{list_name}`."
        else:
            response = f"Could not remove champ from list: {response}."

        await self.message.channel.send(self.client.insert_emotes(response))

class DeleteListCommand(Command):
    NAME = "delete_list"
    DESCRIPTION = "Delete a champion list that you own."
    ACCESS_LEVEL = "all"
    MANDATORY_PARAMS = [CommandParam("list")]

    async def handle(self, list_name: str):
        list_id = self.client.game_databases[_GAME].get_list_by_name(list_name)[0]
        if list_id is None:
            response = f"No champion list found with the name `{list_name}` " + "{emote_sadge}"
        else:
            success, response = lists.delete_list(self.message.author.id, list_id, self.client.game_databases[_GAME])
            if success:
                response = f"The list `{list_name}` has been deleted."
            else:
                response = f"Could not delete `{list_name}`: {response}."

        await self.message.channel.send(self.client.insert_emotes(response))

class RandomNochestCommand(Command):
    NAME = "random_nochest"
    DESCRIPTION = (
        "Pick a random champion that you (or someone else) have not yet earned a chest on (from all champs)."
    )
    ACCESS_LEVEL = "all"
    OPTIONAL_PARAMS = [TargetParam("person")]

    async def handle(self, target_id: int = None):
        summ_data = self.client.game_databases[_GAME].game_user_data_from_discord_id(target_id)
        champion_mastery_data = await self.client.api_clients[_GAME].get_champion_mastery(summ_data.player_id[0])

        # Filter champs with no chest granted.
        no_chest_champs = []
        for mastery_data in champion_mastery_data:
            if not mastery_data["chestGranted"]:
                champ_id = mastery_data["championId"]
                no_chest_champs.append(self.client.api_clients[_GAME].get_champ_name(champ_id))

        if len(no_chest_champs) == 0: # Chests have been earned on every champ.
            response = "You have already earned a chest on every champ {emote_woahpikachu}"
        else:
            index = random.randint(0, len(no_chest_champs)-1)
            champ_name = no_chest_champs[index]
            response = f"Random champ that you have not earned a chest on:\n"
            response += f"**{champ_name}**"

        await self.message.channel.send(self.client.insert_emotes(response))

class BestNochestCommand(Command):
    NAME = "best_nochest"
    DESCRIPTION = (
        "Get the highest winrate champ that you have no yet earned a chest on."
    )
    ACCESS_LEVEL = "self"
    OPTIONAL_PARAMS = optional_params=[TargetParam("person")]

    async def handle(self, target_id: int = None):
        """
        Handler for 'best_nochest' command. Finds the champion with the highest winrate
        for the given player where no chest has yet been obtained.
        """
        summ_data = self.client.game_databases[_GAME].game_user_data_from_discord_id(target_id)
        champion_mastery_data = await self.client.api_clients[_GAME].get_champion_mastery(summ_data.player_id[0])

        # Filter champs with no chest granted.
        no_chest_champs = []
        for mastery_data in champion_mastery_data:
            if not mastery_data["chestGranted"]:
                no_chest_champs.append(mastery_data["championId"])

        if len(no_chest_champs) == 0: # Chests have been earned on every champ.
            response = "You have already earned a chest on every champ {emote_woahpikachu}"
        else:
            # Get highest winrate of all the champs with no chest gained.
            result = self.client.game_databases[_GAME].get_min_or_max_winrate_played(
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
                    champ_name = self.client.api_clients[_GAME].get_champ_name(champ_id)

                    response += f"\n- **{champ_name}** "
                    response += f"(**{winrate:.1f}%** wins in **{games}** games)"

        await self.message.channel.send(self.client.insert_emotes(response))
