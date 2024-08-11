from dataclasses import dataclass
import json
import random
from typing import Any

@dataclass
class DataSpec:
    min_val: Any = None
    max_val: Any = None


def _get_curr_instructions(curr_path, key: str, spec: DataSpec) -> list[str | DataSpec]:
    if curr_path == "":
        return key.split(".")[0]

    path_split = curr_path.split(".")
    spec_path_split = key.split(".")
    if len(path_split) > len(spec_path_split):
        return None

    if len(path_split) == len(spec_path_split):
        curr_instruction = spec
    else:
        curr_instruction = spec_path_split[len(path_split)]

    return curr_instruction

def _get_spec_value(spec: DataSpec):
    if spec.max_val is None:
        return spec.min_val

    return random.randint(spec.min_val, spec.max_val)

def _add_to_path(curr_path, part):
    if curr_path == "":
        return part

    return f"{curr_path}.{part}"

def _iterate_recursively(data, key: str, spec: DataSpec, curr_path: list[str]):
    instruction = _get_curr_instructions(curr_path, key, spec)

    if instruction is None:
        return data

    if isinstance(instruction, DataSpec):
        data = _get_spec_value(instruction)

    elif instruction == "*" or ("-" in instruction and instruction.index("-") > 0):
        if "-" in instruction:
            start, end = tuple(map(int, instruction.split("-")))
            container = range(start, end)
        else:
            container = data

        if isinstance(data, dict):
            for data_key in container:
                try:
                    entry = data[data_key]
                except KeyError:
                    entry = data[str(data_key)]

                data[data_key] = _iterate_recursively(entry, key, spec, _add_to_path(curr_path, data_key))
        elif isinstance(data, list):
            if "-" not in instruction:
                container = range(len(data))

            for index in container:
                data[index] = _iterate_recursively(data[index], key, spec, _add_to_path(curr_path, index))

        else:
            raise ValueError("Can't iterate through data type: " + type(data).__name__)

    else:
        try:
            index = int(instruction)
            data[index] = _iterate_recursively(data[index], key, spec, _add_to_path(curr_path, index))

        except ValueError:
            data[instruction] = _iterate_recursively(data[instruction], key, spec, _add_to_path(curr_path, instruction))

    return data

def _fill_with_defualt_values(data):
    if isinstance(data, dict):
        output_dict = {}
        for key in data:
            output_dict[key] = _fill_with_defualt_values(data[key])
        return output_dict
    elif isinstance(data, list):
        output_list = []
        for val in data:
            output_list.append(_fill_with_defualt_values(val))
        return output_list
    elif data == "float":
        return 0.0
    if data == "int":
        return 0
    if data == "bool":
        return False

    return ""

def apply_specs(
    schema: dict,
    specs: dict[str, DataSpec]
) -> dict:
    data = _fill_with_defualt_values(schema)
    for key, spec in specs.items():
        data.update(_iterate_recursively(dict(data), key, spec, ""))
    
    return data

if __name__ == "__main__":
    with open("resources/game_data_schemas/lol/game_data.json", "r", encoding="utf-8") as fp:
        data = json.load(fp)

    data = apply_specs(
        data,
        {
            "participants.*.kills": DataSpec(0, 10),
            "participants.*.assists": DataSpec(0, 10),
            "participants.*.deaths": DataSpec(0, 10),
        }
    )
    with open("test.json", "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=4)
