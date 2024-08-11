import json

from api.config import Config

def _iterate_recursively(data):
    if isinstance(data, dict):
        output_dict = {}
        for key in data:
            output_dict[key] = _iterate_recursively(data[key])
        return output_dict
    elif isinstance(data, list):
        output_list = []
        for val in data:
            output_list.append(_iterate_recursively(val))
        return output_list

    else:
        return type(data).__name__

def generate_schema(game_data: dict, filename: str, game: str, config: Config):
    output_file = f"{config.resources_folder}/game_data_schemas/{game}/{filename}"

    schema = _iterate_recursively(game_data)

    with open(output_file, "w", encoding="utf-8") as fp:
        json.dump(schema, fp, indent=4)
