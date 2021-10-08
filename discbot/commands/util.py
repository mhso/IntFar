ADMIN_DISC_ID = 267401734513491969

COMMANDS = {} # Defined in commands/__init__.py

CUTE_COMMANDS = {} # Also defined in commands/__init__.py

ADMIN_COMMANDS = {} # You guessed it, defined in commands/__init__.py

def valid_command(message, cmd, args):
    if cmd in ADMIN_COMMANDS:
        return message.author.id == ADMIN_DISC_ID, False

    if cmd in CUTE_COMMANDS:
        return True, False

    is_main_cmd = cmd in COMMANDS
    valid_cmd = None
    if is_main_cmd:
        valid_cmd = cmd

    for possible_alias in COMMANDS:
        if cmd in COMMANDS[possible_alias].aliases:
            valid_cmd = possible_alias
            break

    if valid_cmd is None:
        return False, False

    mandatory_params = COMMANDS[valid_cmd].mandatory_params

    for index in range(len(mandatory_params)):
        if args is None or len(args) <= index:
            return False, True

    return True, False

def extract_target_name(split, start_index, end_index=None, default="me"):
    end_index = len(split) if end_index is None else end_index
    if len(split) > start_index:
        return " ".join(split[start_index:end_index])
    return default

def try_find_champ(name, riot_api):
    search_name = name.strip().lower()
    candidates = []
    for champ_id in riot_api.champ_names:
        lowered = riot_api.champ_names[champ_id].lower()
        if search_name in lowered:
            candidates.append(champ_id)
            break

        # Remove apostrophe and period from name.
        if search_name in lowered.replace("'", "").replace(".", ""):
            candidates.append(champ_id)

    return candidates[0] if len(candidates) == 1 else None
