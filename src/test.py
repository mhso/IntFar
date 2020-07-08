import json
import riot_api
import config

auth = json.load(open("auth.json"))

conf = config.Config()
conf.riot_key = auth["riotDevKey"] if conf.use_dev_token else auth["riotAPIKey"]

api = riot_api.APIClient(conf)
game_info = api.get_game_details(4698011399)

filtered_stats = []
active_users = [
    ("Dave", "a8acI9mAGm3mxTNPEqJPZmQ9LYkPnL5BNYG_tRWVMv_u-5E"),
    ("Muds", "z6svwF0nkD_TY5SLXAOEW3MaDLqJh1ziqOsE9lbqPQavp3o"),
    ("Gual", "LRjsmujd76mwUe5ki-cOhcfrpAVsMpsLeA9BZqSl6bMiOI0")
]
for summ_name, summ_id in active_users:
    for part_info in game_info["participantIdentities"]:
        if summ_id == part_info["player"]["summonerId"]:
            for participant in game_info["participants"]:
                if part_info["participantId"] == participant["participantId"]:
                    filtered_stats.append((summ_name, summ_id, participant["stats"]))
                    break
            break

intfar_disc_id, intfar_summ_id = None, None

def calc_kda(data):
    stats = data[2]
    return (stats["kills"] + stats["assists"]) / stats["deaths"]

sorted_by_kda = sorted(filtered_stats, key=calc_kda)
for data in sorted_by_kda:
    print(f"{data[0]}'s KDA: {calc_kda(data)}")
