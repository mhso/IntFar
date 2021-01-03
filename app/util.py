def discord_request(pipe, command_types, commands, params):
    """
    Request some information from the Discord API.
    This is done by using a pipe to the separate process hosting the Discord Bot.

    @param pipe Multiprocessing Pipe object connecting to the process running the Discord Bot.
    @param command_types Type of command to execute in the other process ('func' or 'bot_command').
    Can either be a string or a list of strings.
    @param commands Command to execute, if 'command_types' is 'func' this should be the name of
    a function in the Discord Client class. Can either be a string or list of strings.
    @param params Parameters for each of the command_types/commands.
    Can either be a value, a tuple of values, or a list of values or tuple of values.
    """
    args_tuple = (command_types, commands, params)
    any_list = any(isinstance(x, list) for x in args_tuple)
    if not any_list:
        command_types = [command_types]
        commands = [commands]
        params = [params]
    else:
        max_len_args = max(len(x) for x in args_tuple if isinstance(x, list))
        if not isinstance(commands, list):
            commands = [commands for _ in range(max_len_args)]
        if not isinstance(command_types, list):
            command_types = [command_types for _ in range(max_len_args)]
        if not isinstance(params, list):
            params = [params for _ in range(max_len_args)]

    pipe.send((command_types, commands, params))
    result = pipe.recv()
    return result if any_list else result[0]
