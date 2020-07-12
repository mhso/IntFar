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
                },
                "timeline": {}
            }
        ],
        "teams": {
            "baronKills": 0,
            "dragonKills": 0
        }
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
                },
                "timeline": {}
            },
            {
                "participantId" : 2,
                "teamId": 200,
                "stats" : {
                    "kills": 30, "deaths": 7, "assists": 25, "visionScore" : 4
                },
                "timeline": {}
            }
        ],
        "teams": {
            "baronKills": 0,
            "dragonKills": 0
        }
    }
    mentions_1 = {
        "participantIdentities" : [
            {
                "participantId" : 1,
                "player" : {"summonerId" : "LRjsmujd76mwUe5ki-cOhcfrpAVsMpsLeA9BZqSl6bMiOI0"}
            }
        ],
        "participants" : [
            {
                "participantId" : 1,
                "teamId": 200,
                "stats" : {
                    "kills": 3,
                    "visionWardsBoughtInGame" : 0,
                    "totalDamageDealtToChampions": 5500
                },
                "timeline": {
                    "creepsPerMinDeltas": {
                        "10-20": 2,
                        "0-10": 1.5
                    },
                    "role": "NONE",
                    "lane": "JUNGLE"
                }
            }
        ],
        "teams": {
            "baronKills": 0,
            "dragonKills": 0
        }
    }
    mentions_2 = {
        "participantIdentities" : [
            {
                "participantId" : 1,
                "player" : {"summonerId" : "LRjsmujd76mwUe5ki-cOhcfrpAVsMpsLeA9BZqSl6bMiOI0"}
            }
        ],
        "participants" : [
            {
                "participantId" : 1,
                "teamId": 200,
                "stats" : {
                    "kills": 3,
                    "visionWardsBoughtInGame" : 0,
                    "totalDamageDealtToChampions": 552
                },
                "timeline": {
                    "creepsPerMinDeltas": {
                        "10-20": 7,
                        "0-10": 3.5
                    },
                    "role": "DUO_SUPPORT",
                    "lane": "BOTTOM"
                }
            }
        ],
        "teams": {
            "baronKills": 0,
            "dragonKills": 0
        }
    }
    return [intfar_vision_score, intfar_kp_score, mentions_1, mentions_2]

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
    disc_client.active_users = [
        disc_client.database.discord_id_from_summoner("Senile Felines"),
        disc_client.database.discord_id_from_summoner("Dumbledonger"),
    ]
    print(disc_client.active_users)
    test_data = generate_test_data()
    filtered_stats = disc_client.get_filtered_stats(test_data[0])
    response = disc_client.get_intfar_details(filtered_stats, filtered_stats[0][1]["kills_by_team"])
    print(response)
    filtered_stats = disc_client.get_filtered_stats(test_data[1])
    response = disc_client.get_intfar_details(filtered_stats, filtered_stats[0][1]["kills_by_team"])
    print(response)
    filtered_stats = disc_client.get_filtered_stats(test_data[2])
    response = disc_client.get_honorable_mentions(filtered_stats)
    print(response)
    filtered_stats = disc_client.get_filtered_stats(test_data[3])
    response = disc_client.get_honorable_mentions(filtered_stats)
    print(response)

check_stuff(client)
