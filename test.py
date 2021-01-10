from time import time
from sys import argv
import json
import requests

def send_game_update(endpoint, data):
    try:
        response = requests.post(f"http://mhooge.com:5000/intfar/{endpoint}", data=data)
        print(response.text)
    except requests.exceptions.RequestException as e:
        print("Error ignored in online_monitor: " + str(e))

auth = json.load(open("discbot/auth.json"))
secret = auth["discordToken"]

req_data = {
    "secret": secret
}

if len(argv) == 1:
    exit(0)

if argv[1] == "start":
    active_game = {
        "id": 123,
        "start": time(),
        "map_id": 11,
        "game_mode": "CLASSIC"
    }
    req_data.update(active_game)

    send_game_update("game_started", req_data)
elif argv[1] == "end":
    send_game_update("game_ended", req_data)
