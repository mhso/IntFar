import json
import flask
import secrets
from hashlib import sha256

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

def get_game_info():
    active_game = flask.current_app.config["ACTIVE_GAME"]
    if active_game is None:
        return { "game_duration": 3, "game_mode": "CLASSIC" }

    riot_api = flask.current_app.config["RIOT_API"]
    game_data = riot_api.get_game_details(active_game)

    data = {
        "game_duration": game_data["gameLength"],
        "game_mode": game_data["gameMode"]
    }
    return data

def generate_user_secret():
    return secrets.token_hex(nbytes=32)

def get_hashed_secret(secret):
    return sha256(bytes(secret, encoding="utf-8")).hexdigest()

def get_logged_in_user(database, user_id):
    if user_id is None:
        return None

    users = database.get_all_registered_users()
    for tup in users:
        if get_hashed_secret(tup[3]) == user_id:
            return tup[0]
    return None

def get_user_details():
    database = flask.current_app.config["DATABASE"]
    bot_conn = flask.current_app.config["BOT_CONN"]
    logged_in_user = get_logged_in_user(database, flask.request.cookies.get("user_id"))

    if flask.current_app.config["LOGGED_IN_USERS"].get(logged_in_user) is not None:
        return (logged_in_user,) + flask.current_app.config["LOGGED_IN_USERS"][logged_in_user]

    logged_in_name = "Unknown"
    logged_in_avatar = None
    if logged_in_user is not None:
        discord_data = discord_request(bot_conn, "func", ["get_discord_nick", "get_discord_avatar"], logged_in_user)
        logged_in_name = discord_data[0]
        avatar = discord_data[1]
        if avatar is not None:
            logged_in_avatar = flask.url_for("static", filename=avatar.replace("app/static/", ""))

        flask.current_app.config["LOGGED_IN_USERS"][logged_in_user] = (logged_in_name, logged_in_avatar)

    return logged_in_user, logged_in_name, logged_in_avatar

def make_json_response(data, http_code):
    if not isinstance(data, dict):
        data = {"response": str(data)}

    resp = flask.Response(response=json.dumps(data), status=http_code, mimetype="application/json")
    resp.headers["Content-Type"] = "application/json; charset=utf-8"
    return resp

def get_persistent_data():
    logged_in_user, logged_in_name, logged_in_avatar = get_user_details()
    data = {
        "logged_in_user": logged_in_user,
        "logged_in_name": logged_in_name,
        "logged_in_avatar": logged_in_avatar,
    }
    game_info = get_game_info()
    if game_info is not None:
        data.update(game_info)

    return data

def make_template_context(template, **variables):
    variables.update(get_persistent_data())
    return flask.render_template(template, **variables)
