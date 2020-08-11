import json
import asyncio
from database import Database, DBException
from config import Config
from discord_bot import DiscordClient

def generate_game_data(kills, deaths, assists, vision, damages, summ_names):
    partIds = []
    for p_id, sm in enumerate(summ_names, start=1):
        data = database_client.discord_id_from_summoner(sm)
        partIds.append({"participantId": p_id, "player": {"summonerId": data[2]}})

    participants = []
    golds = [200, 150, 100]
    for (p_id, (k, d, a, v, dmg)) in enumerate(zip(kills, deaths, assists, vision, damages), start=1):
        participants.append(
            {
                "participantId" : p_id,
                "teamId": 100,
                "stats" : {
                    "kills": k, "deaths": d, "assists": a, "visionScore" : v,
                    "totalDamageDealtToChampions": dmg, "turretKills": 3, "inhibitorKills": 3,
                    "goldEarned": golds[p_id-1]
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
        summoners = ["prince jarvan lv", "senile felines", "kazpariuz"]
        self.users_in_game = [
            self.database.discord_id_from_summoner(name) for name in summoners
        ]
        print(self.get_ifotm_lead_msg(115142485579137029))

auth = json.load(open("auth.json"))

conf = Config()

conf.discord_token = auth["discordToken"]
conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

conf.log("Initializing database...")

database_client = Database(conf)

test = []
for x, y, z in test:
    print("LOL")

# conf.log("Starting Discord Client...")

# client = TestMock(conf, database_client)

# client.run(conf.discord_token)
