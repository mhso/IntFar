from flask import request, current_app, url_for
import secrets
from hashlib import sha256
from app.util import get_discord_data

def generate_secret():
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
    if current_app.config.get("LOGGED_IN_USER") is not None:
        return (
            current_app.config["LOGGED_IN_USER"],
            current_app.config["LOGGED_IN_NAME"],
            current_app.config["LOGGED_IN_AVATAR"]
        )

    database = current_app.config["DATABASE"]
    bot_conn = current_app.config["BOT_CONN"]
    logged_in_user = get_logged_in_user(database, request.cookies.get("user_id"))
    logged_in_name = "Unknown"
    logged_in_avatar = None
    if logged_in_user is not None:
        logged_in_name = get_discord_data(bot_conn, "func", "get_discord_nick", logged_in_user)
        avatar = get_discord_data(bot_conn, "func", "get_discord_avatar", logged_in_user)
        if avatar is not None:
            logged_in_avatar = url_for("static", filename=avatar.replace("app/static/", ""))

        current_app.config["LOGGED_IN_USER"] = logged_in_user
        current_app.config["LOGGED_IN_NAME"] = logged_in_name
        current_app.config["LOGGED_IN_AVATAR"] = logged_in_avatar

    return logged_in_user, logged_in_name, logged_in_avatar
