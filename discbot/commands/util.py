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
        return False, False # Command is not valid.

    if message.guild.id not in COMMANDS[valid_cmd].guilds:
        return False, False # Command is not valid in the current guild.  

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

def get_main_command(cmd):
    if cmd in COMMANDS:
        return COMMANDS[cmd]
    
    for possible_alias in COMMANDS:
        if cmd in COMMANDS[possible_alias].aliases:
            return COMMANDS[possible_alias]
     
    return None
