import json
import asyncio
from database import Database
from config import Config
from discord_bot import DiscordClient

def generate_game_data(kills, deaths, assists, vision, damages, summ_names):
    partIds = []
    for p_id, sm in enumerate(summ_names, start=1):
        data = database_client.discord_id_from_summoner(sm)
        partIds.append({"participantId": p_id, "player": {"summonerId": data[2]}})

    participants = []
    for (p_id, (k, d, a, v, dmg)) in enumerate(zip(kills, deaths, assists, vision, damages), start=1):
        participants.append(
            {
                "participantId" : p_id,
                "teamId": 100,
                "stats" : {
                    "kills": k, "deaths": d, "assists": a, "visionScore" : v,
                    "totalDamageDealtToChampions": dmg, "turretKills": 3, "inhibitorKills": 3
                },
                "timeline": {}
            }
        )

    return {
        "participantIdentities" : partIds,
        "participants" : participants,
        "gameCreation": 100000,
        "mapId": 11,
        "teams": [
            {
                "teamId": 100,
                "baronKills": 0,
                "dragonKills": 0,
                "riftHeraldKills": 0
            },
            {
                "teamId": 200,
                "baronKills": 0,
                "dragonKills": 0,
                "riftHeraldKills": 0
            }
        ]
    }

class TestMock(DiscordClient):
    async def on_ready(self):
        await super().on_ready()
        summoners = ["prince jarvan lv", "senile felines", "nønø", "stirred martini", "kazpariuz"]
        self.users_in_game = [
            self.database.discord_id_from_summoner(name) for name in summoners
        ]
        kills = [5, 8, 11, 10, 3]
        deaths = [3, 12, 8, 9, 7]
        assists = [12, 13, 8, 15, 28]
        visions = [20, 20, 20, 20, 20]
        damages = [30000, 30000, 30000, 30000, 30000]
        data = generate_game_data(kills, deaths, assists, visions, damages, summoners)
        filtered = self.get_filtered_stats(data)
        intfar_details = self.get_intfar_details(filtered)
        intfar_counts = {}
        max_intfar_count = 1
        max_count_intfar = None
        intfar_data = {}

        # Look through details for the people qualifying for Int-Far.
        # The one with most criteria met gets chosen.
        for (index, (tied_intfars, stat_value)) in enumerate(intfar_details):
            if tied_intfars is not None:
                for intfar_disc_id in tied_intfars:
                    if intfar_disc_id not in intfar_counts:
                        intfar_counts[intfar_disc_id] = 0
                        intfar_data[intfar_disc_id] = []
                    current_intfar_count = intfar_counts[intfar_disc_id] + 1
                    intfar_counts[intfar_disc_id] = current_intfar_count
                    if current_intfar_count >= max_intfar_count:
                        max_intfar_count = current_intfar_count
                        max_count_intfar = intfar_disc_id
                    intfar_data[intfar_disc_id].append((index, stat_value))

        final_intfar = self.resolve_intfar_ties(intfar_data, max_intfar_count, filtered)
        print(final_intfar, flush=True)

auth = json.load(open("auth.json"))

conf = Config()

conf.discord_token = auth["discordToken"]
conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

conf.log("Initializing database...")

database_client = Database(conf)

conf.log("Starting Discord Client...")

print(database_client.get_longest_no_intfar_streak(115142485579137029))

#client = TestMock(conf, database_client)

#client.run(conf.discord_token)
