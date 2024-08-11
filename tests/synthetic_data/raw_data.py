import json
from uuid import uuid1
from tests.synthetic_data.spec import DataSpec, apply_specs

def _get_required_lol_data(game_database):
    specs = {
        "gameId": DataSpec(uuid1().hex),
        "teams.0.teamId": DataSpec(100),
        "teams.1.teamId": DataSpec(200),
        "participants.5-10.teamId": DataSpec(200),
    }

    positions = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
    roles = ["NONE", "NONE", "SOLO", "CARRY", "SUPPORT"]
    for index, player_id in enumerate(game_database.game_users.keys()):
        specs[f"participants.{index}.summonerId"] = DataSpec(game_database.game_users[player_id].player_id[0])
        specs[f"participants.{index}.teamId"] = DataSpec(100)
        specs[f"participants.{index}.teamPosition"] = DataSpec(positions[index])
        specs[f"participants.{index}.role"] = DataSpec(roles[index])
        specs["gameDuration"] = DataSpec(20 * 60)

    specs["participants.5-10.teamId"] = DataSpec(200)

    return specs

def create_synthetic_data(game, game_databases, data: dict[str, DataSpec]):
    specs = _get_required_lol_data(game_databases[game])
    specs.update(data)

    with open(f"resources/game_data_schemas/{game}/game_data.json", "r", encoding="utf-8") as fp:
        schema = json.load(fp)

    return apply_specs(schema, specs)
