def get_discord_data(pipe, command_type, command, *params):
    pipe.send((command_type, command, params))
    return pipe.recv()
