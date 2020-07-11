import json
import threading
from time import sleep
from database import Database
from config import Config
import discord_bot
import game_stats
import riot_api

def generate_test_data():
    intfar_vision_score = {
        "participantIdentities" : [
            {
                "participantId" : 1,
                "player" : {"summonerId" : "LRjsmujd76mwUe5ki-cOhcfrpAVsMpsLeA9BZqSl6bMiOI0"}
            }
        ],
        "participants" : [
            {
                "participantId" : 1,
                "teamId": 100,
                "stats" : {
                    "kills": 5, "deaths": 7, "assists": 5, "visionScore" : 4
                }
            }
        ]
    }
    intfar_kp_score = {
        "participantIdentities" : [
            {
                "participantId" : 1,
                "player" : {"summonerId" : "LRjsmujd76mwUe5ki-cOhcfrpAVsMpsLeA9BZqSl6bMiOI0"}
            },
            {
                "participantId" : 2,
                "player" : {"summonerId" : "z6svwF0nkD_TY5SLXAOEW3MaDLqJh1ziqOsE9lbqPQavp3o"}
            }
        ],
        "participants" : [
            {
                "participantId" : 1,
                "teamId": 200,
                "stats" : {
                    "kills": 2, "deaths": 1, "assists": 1, "visionScore" : 20
                }
            },
            {
                "participantId" : 2,
                "teamId": 200,
                "stats" : {
                    "kills": 30, "deaths": 7, "assists": 25, "visionScore" : 4
                }
            }
        ]
    }
    return intfar_vision_score, intfar_kp_score

GAME_ID = 4701602782

auth = json.load(open("auth.json"))

conf = Config()

conf.discord_token = auth["discordToken"]
conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

conf.log("Initializing database...")

database_client = Database(conf)

conf.log("Starting Discord Client...")

client = discord_bot.DiscordClient(conf, database_client)


def check_stuff(disc_client):
    sleep(5)
    disc_client.active_users = [
        disc_client.database.discord_id_from_summoner("Senile Felines"),
        disc_client.database.discord_id_from_summoner("Dumbledonger"),
    ]
    intfar_vs, intfar_kp = generate_test_data()
    filtered_stats, kills_by_our_team = disc_client.get_filtered_stats(intfar_vs)
    print(disc_client.get_intfar_details(filtered_stats, kills_by_our_team), flush=True)
    filtered_stats, kills_by_our_team = disc_client.get_filtered_stats(intfar_kp)
    print(disc_client.get_intfar_details(filtered_stats, kills_by_our_team), flush=True)

threading.Thread(target=check_stuff, args=(client,)).start()

client.run(conf.discord_token)
