import json
import flask
from time import time
from datetime import datetime
from hashlib import sha256

def register_discord_connection():
    bot_conn = flask.current_app.config["BOT_CONN"]
    conn_map = flask.current_app.config["CONN_MAP"]
    conn_lock = flask.current_app.config["CONN_LOCK"]
    sess_id = flask.session["user_id"]

    conn_lock.acquire()
    new_conn = discord_request("register", None, None, bot_conn)
    conn_lock.release()

    conn_map[sess_id] = new_conn

def create_session_id():
    if "user_id" not in flask.session:
        flask.current_app.config["USER_COUNT"] = flask.current_app.config["USER_COUNT"] + 1
        flask.session["user_id"] = flask.current_app.config["USER_COUNT"]

def discord_request(command_types, commands, params, pipe=None):
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
    conn_map = flask.current_app.config["CONN_MAP"]
    if flask.session["user_id"] not in conn_map and command_types != "register":
        register_discord_connection()

    sess_id = flask.session["user_id"]
    if pipe is None:
        pipe = conn_map[sess_id]

    args_tuple = (command_types, commands, params)
    any_list = any(isinstance(x, list) for x in args_tuple)
    command_type_list = command_types
    command_list = commands
    param_list = params
    if not any_list:
        command_type_list = [command_types]
        command_list = [commands]
        param_list = [params]
    else:
        max_len_args = max(len(x) for x in args_tuple if isinstance(x, list))
        if not isinstance(commands, list):
            command_list = [commands for _ in range(max_len_args)]
        if not isinstance(command_types, list):
            command_type_list = [command_types for _ in range(max_len_args)]
        if not isinstance(params, list):
            param_list = [params for _ in range(max_len_args)]

    tuple_params = []
    for param in param_list:
        if not isinstance(param, tuple):
            tuple_params.append((param,))
        else:
            tuple_params.append(param)
    try:
        pipe.send((sess_id, command_type_list, command_list, tuple_params))
        result = pipe.recv()
        return result if any_list else result[0]
    except (EOFError, BrokenPipeError, ConnectionResetError):
        register_discord_connection() # We timed out. Re-establish connection and try again.
        return discord_request(command_types, commands, params, conn_map[sess_id])

def get_game_info():
    active_game = flask.current_app.config["ACTIVE_GAME"]
    if active_game is None:
        active_game = discord_request("func", "get_active_game", None)
        if active_game is None:
            return None
        flask.current_app.config["ACTIVE_GAME"] = active_game

    active_game["game_duration"] = time() - active_game["start"]

    return active_game

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
    logged_in_user = get_logged_in_user(database, flask.request.cookies.get("user_id"))

    if flask.current_app.config["LOGGED_IN_USERS"].get(logged_in_user) is not None:
        return (logged_in_user,) + flask.current_app.config["LOGGED_IN_USERS"][logged_in_user]

    logged_in_name = "Unknown"
    logged_in_avatar = None
    if logged_in_user is not None:
        discord_data = discord_request("func", ["get_discord_nick", "get_discord_avatar"], logged_in_user)
        logged_in_name = discord_data[0]
        avatar = discord_data[1]
        if avatar is not None:
            logged_in_avatar = flask.url_for("static", filename=avatar.replace("app/static/", ""))

        flask.current_app.config["LOGGED_IN_USERS"][logged_in_user] = (logged_in_name, logged_in_avatar)

    return logged_in_user, logged_in_name, logged_in_avatar

def format_bet_timestamp(timestamp):
    if timestamp == 0:
        return None
    return datetime.fromtimestamp(timestamp).strftime("%d-%m-%y %H:%M:%S")

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
