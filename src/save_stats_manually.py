import json
import threading
from time import sleep
from database import Database
from config import Config
from discord_bot import DiscordClient
import game_stats
import riot_api

GAME_ID = 4705933274

auth = json.load(open("auth.json"))

conf = Config()

conf.discord_token = auth["discordToken"]
conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

conf.log("Initializing database...")

database_client = Database(conf)

conf.log("Starting Discord Client...")

client = DiscordClient(conf, database_client)

api = riot_api.APIClient(conf)

def save_stats(disc_client, api_client):
    sleep(10)
    print(disc_client.database.summoners)
    disc_client.active_users = [
        disc_client.database.discord_id_from_summoner("Senile Felines"),
        disc_client.database.discord_id_from_summoner("Dumbledonger"),
        disc_client.database.discord_id_from_summoner("Prince Jarvan lV")
    ]
    game_info = api_client.get_game_details(GAME_ID)
    filtered_stats = disc_client.get_filtered_stats(game_info)
    disc_client.database.record_stats(None, 0000, GAME_ID, filtered_stats, filtered_stats[0][1]["kills_by_team"])

threading.Thread(target=save_stats, args=(client, api)).start()

client.run(conf.discord_token)
