import json

data = json.load(open("champions.json"))

for champ in data["data"]:
    print(data["data"][champ]["key"])
