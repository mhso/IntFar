import json
import config
import riot_api
import game_stats

game_id = 4700352835

auth = json.load(open("auth.json"))

conf = config.Config()
conf.riot_key = auth["riotAPIKey"]

riot_api = riot_api.APIClient(conf)

game_info = riot_api.get_game_details(game_id)

print(game_stats.get_game_summary(game_info, "LRjsmujd76mwUe5ki-cOhcfrpAVsMpsLeA9BZqSl6bMiOI0"))
