import re

LEGAL_REGEX = re.compile("[^a-z0-9_]")
MAX_LISTS = 15

def verify_list_name(name):
    max_list_len = 32
    if name is None or name == "":
        return "List name is empty"
    if len(name) > max_list_len:
        return f"List name is too long (max {max_list_len} characters)"
    if LEGAL_REGEX.search(name):
        return f"Invalid character(s) in list name. Only 'a-z', '0-9', and '_' allowed"
    return None

def create_list(disc_id, list_name, database):
    error = verify_list_name(list_name)

    if error is not None:
        return False, error

    # Reject list creation if user has created too many lists.
    if len(database.get_lists(disc_id)) >= MAX_LISTS:
        error_msg = (
            f"You can create at most {MAX_LISTS} lists (storage space isn't free, yo)"
        )
        return False, error_msg

    success, list_id = database.create_list(disc_id, list_name)
    if not success:
        return False, f"List with name {list_name} already exists"

    return True, list_id

def rename_list(disc_id, list_id, new_name, database):
    if database.get_list_data(list_id)[1] != disc_id:
        return False, "You do not own this list"

    error = verify_list_name(new_name)

    if error is not None:
        return False, error

    database.rename_list(list_id, new_name)
    return True, None

def delete_list(disc_id, list_id, database):
    if database.get_list_data(list_id)[1] != disc_id:
        error_msg = "You do not own this list"
        return False, error_msg

    database.delete_list(list_id)
    return True, None

def verify_champ_id(champion, riot_api):
    if champion is None or champion == "":
        return "Champion to add is empty"
    if int(champion) not in riot_api.champ_names:
        return "Invalid champion given"
    return None

def add_champ_to_list(disc_id, list_id, champ_ids, riot_api, database):
    if not isinstance(champ_ids, list):
        champ_ids = [champ_ids]

    # Elimate duplicate entries.
    champ_ids = list(set(champ_ids))

    for champ_id in champ_ids:
        error = verify_champ_id(champ_id, riot_api)
        if error is not None:
            return False, error

    if database.get_list_data(list_id)[1] != disc_id:
        return False, "You do not own this list"

    if len(champ_ids) == 1: # Add just one champion to list.
        success = database.add_item_to_list(int(champ_ids[0]), list_id)
    else: # Add multiple champions to list at once.
        success = database.add_items_to_list(
            [(int(champ_id), list_id) for champ_id in champ_ids]
        )

    if not success:
        error_msg = "The champion" if len(champ_ids) == 1 else "One of the champions"
        return False, f"{error_msg} is already in the list"

    quantifier = "champion" if len(champ_ids) == 1 else "champions"
    return True, f"Successfully added **{len(champ_ids)}** {quantifier}"

def delete_champ_from_list(disc_id, item_id, database):
    list_data = database.get_list_from_item_id(item_id)

    # No list exists that contains the given item id.
    if list_data is None:
        return False, f"{item_id} is an invalid item ID"

    owner_id = list_data[2]

    if owner_id is None or owner_id != disc_id:
        # List does not exist, or list is not owned by user.
        return False, "Maybe you don't own this list"

    database.delete_item_from_list(item_id)

    return True, "Champion successfully deleted from list"

def delete_by_champ_ids(disc_id, list_id, champ_ids, database):
    if database.get_list_data(list_id)[1] != disc_id:
        return False, "You do not own this list"

    if not isinstance(champ_ids, list):
        champ_ids = [champ_ids]

    # Elimate duplicate entries.
    champ_ids = list(set(champ_ids))

    list_items = database.get_list_items(list_id)
    ids_to_delete = []
    for item_id, champ_id in list_items:
        if champ_id in champ_ids:
            ids_to_delete.append(item_id)

    if len(ids_to_delete) != len(champ_ids):
        error_msg = "The given champion" if len(champ_ids) == 1 else "One of the given champions"
        return False, f"{error_msg} is not in the list"

    if len(ids_to_delete) == 1: # Delete just one champion from list.
        database.delete_item_from_list(ids_to_delete[0])
    else: # Delete multiple champions from list at once.
        database.delete_items_from_list([(x,) for x in ids_to_delete])

    quantifier = "champion" if len(champ_ids) == 1 else "champions"
    return True, f"Successfully removed **{len(champ_ids)}** {quantifier}"
