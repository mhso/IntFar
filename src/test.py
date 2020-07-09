import json
import config
import riot_api
import game_stats

game_id = 4699244357

auth = json.load(open("auth.json"))

conf = config.Config()
conf.riot_key = auth["riotAPIKey"]

riot_api = riot_api.APIClient(conf)

game_info = riot_api.get_game_details(game_id)
active_users = [
    (347489125877809155, "Nønø", "vWqeigv3NlpebAwh309gZ8zWul9rNIv6zUKXGFeRWqih9ko"),
    (267401734513491969, "Senile Felines", "LRjsmujd76mwUe5ki-cOhcfrpAVsMpsLeA9BZqSl6bMiOI0"),
]
kills_per_team = {100: 0, 200: 0}
our_team = 100
filtered_stats = []
for part_info in game_info["participantIdentities"]:
    for participant in game_info["participants"]:
        if part_info["participantId"] == participant["participantId"]:
            kills_per_team[participant["teamId"]] += participant["stats"]["kills"]
            for disc_id, _, summ_id in active_users:
                if summ_id == part_info["player"]["summonerId"]:
                    our_team = participant["teamId"]
                    filtered_stats.append((disc_id, participant["stats"]))

print(filtered_stats[0][1]["kills"])
print(game_stats.calc_kill_participation(filtered_stats[0][1], kills_per_team[our_team]))
