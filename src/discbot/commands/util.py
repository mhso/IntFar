ADMIN_DISC_ID = 267401734513491969

COMMANDS = {} # Instantiated in commands/__init__.py

CUTE_COMMANDS = {} # Also instantiated in commands/__init__.py

ADMIN_COMMANDS = {} # You guessed it, instantiated in commands/__init__.py

def extract_target_name(split, start_index, end_index=None, default="me"):
    end_index = len(split) if end_index is None else end_index
    if len(split) > start_index:
        return " ".join(split[start_index:end_index])
    return default

def get_main_command(cmd):
    if cmd in COMMANDS:
        return COMMANDS[cmd]
    
    for possible_alias in COMMANDS:
        if cmd in COMMANDS[possible_alias].ALIASES:
            return COMMANDS[possible_alias]
     
    return None
