import hashlib
import secrets
from hashlib import sha256

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
