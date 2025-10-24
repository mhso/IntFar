import asyncio
from datetime import datetime
from glob import glob
from threading import Thread
from dateutil.relativedelta import relativedelta
import importlib
import os
import json
import secrets
import math

from intfar.api.config import Config

import Levenshtein
from PIL import Image, ImageDraw, ImageFont
import numpy as np

MAIN_GUILD_ID = 619073595561213953
MY_GUILD_ID  = 512363920044982272

SUPPORTED_GAMES = {
    "lol": "League of Legends",
    "cs2": "Counter Strike 2"
}

GUILD_IDS = [ # List of ids of guilds that Int-Far is active in.
    MAIN_GUILD_ID, 347488541397483543, 803987403932172359
]

GUILD_ABBREVIATIONS = {
    MAIN_GUILD_ID: "LN",
    347488541397483543: "DC",
    803987403932172359: "LN"
}

GUILD_MAP = {
    "nibs": MAIN_GUILD_ID, "circus": 347488541397483543, "core": 803987403932172359
}

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"
]

JEOPARDY_ITERATION = 5
_suffix = ["st", "nd", "rd", "th"]
JEOPADY_EDITION = f"{JEOPARDY_ITERATION}{_suffix[min(len(_suffix) - 1, JEOPARDY_ITERATION - 1)]} Edition"
JEOPARDY_REGULAR_ROUNDS = 2

def load_flavor_texts(config: Config, filename, game=None):
    path = f"{config.resources_folder}/flavor_texts"
    if game is not None:
        path = f"{path}/{game}"
    path = f"{path}/{filename}.txt"

    with open(path, "r", encoding="utf-8") as f:
        return [x.replace("\n", "") for x in f.readlines()]

def current_month():
    return MONTH_NAMES[datetime.now().month-1]

def zero_pad(number):
    if number < 10:
        return "0" + str(number)
    return str(number)

def round_digits(number):
    if type(number) == float:
        return f"{number:.2f}"
    return str(number)

def format_duration(dt_1: datetime, dt_2: datetime):
    if dt_1.timestamp() > dt_2.timestamp():
        delta = relativedelta(dt_1, dt_2)
    else:
        delta = relativedelta(dt_2, dt_1)

    years = delta.years
    months = delta.months
    days = delta.days
    hours = delta.hours
    minutes = delta.minutes
    seconds = delta.seconds

    response = f"{zero_pad(hours)}h, {zero_pad(minutes)}m, {zero_pad(seconds)}s"
    if minutes == 0:
        response = f"{seconds} seconds"
    else:
        response = f"{zero_pad(minutes)} minutes & {zero_pad(seconds)} seconds"
    if hours > 0:
        response = f"{zero_pad(hours)}h, {zero_pad(minutes)}m, {zero_pad(seconds)}s"
    if days > 0:
        response = f"{days} days, " + response
    if months > 0:
        response = f"{months} months, " + response
    if years > 0:
        response = f"{years} years, " + response

    return response

def format_duration_seconds(seconds):
    now = datetime.now()
    then = now - relativedelta(seconds=seconds)
    return format_duration(then, now)

def format_tokens_amount(tokens):
    if tokens is None:
        return None

    as_str = str(tokens)
    if tokens < 1000:
        return as_str

    formatted = ""
    for i in range(len(as_str), 0, -1):
        reverse_i = len(as_str) - i
        if reverse_i > 0 and i % 3 == 0:
            formatted += "."
        formatted += as_str[reverse_i]

    return formatted

def parse_amount_str(amount_str, balance=None):
    mult = 1
    multiplier_values = [("t", 1e12), ("b", 1e9), ("m", 1e6), ("k", 1e3)]
    for identifier, mult_val in multiplier_values:
        if amount_str[-1].lower() == identifier:
            mult = mult_val
            amount_str = amount_str[:-1]
            break

    try:
        return int(float(amount_str) * mult)

    except ValueError as e:
        if balance is not None:
            if amount_str[-1] == "%":
                return int(float(amount_str[:-1]) * 0.01 * balance)

            if amount_str == "all":
                return balance
            if amount_str == "half":
                return balance // 2
            if amount_str == "third":
                return balance // 3
            if amount_str == "quarter":
                return balance // 4
        raise e

def generate_user_secret():
    return secrets.token_hex(nbytes=32)

def get_guild_abbreviation(guild_id):
    return GUILD_ABBREVIATIONS.get(guild_id, "")

def format_timestamp(timestamp):
    seconds = timestamp
    minutes = 0
    if seconds >= 60:
        minutes = int(seconds / 60)
        seconds = seconds % 60

    return f"{zero_pad(minutes)}:{zero_pad(seconds)}"

def get_website_link(game=None):
    base_url = "https://mhooge.com/intfar"
    if game is None:
        return base_url

    return f"{base_url}/{game}"

def find_subclasses_in_dir(dir, base_class):
    config = Config()

    modules = map(lambda x: x.replace(".py", ""), glob(f"{config.startup_folder}/{dir}/*.py"))

    subclasses = {}
    for module_name in modules:
        module_key = os.path.basename(module_name)
        if module_key not in SUPPORTED_GAMES:
            continue

        rel_path = module_name.replace(config.startup_folder + "/", "")

        module = importlib.import_module(rel_path.replace("\\", ".").replace("/", "."))
        for subclass in base_class.__subclasses__():
            if hasattr(module, subclass.__name__):
                subclasses[module_key] = subclass
                break

    return subclasses

def create_predictions_timeline_image(config: Config):
    filename = f"{config.resources_folder}/predictions_temp.json"

    if not os.path.exists(filename):
        return None

    json_data = json.load(open(filename, "r", encoding="utf-8"))

    if len(json_data["predictions"]) < 2:
        return None

    img_w = int(len(json_data["predictions"]) * 70)
    img_h = 420
    image_shape = (img_h, img_w, 3)
    arr = np.zeros(image_shape, dtype="uint8")
    arr[:, :, 0] = 15
    arr[:, :, 1] = 15
    arr[:, :, 2] = 15
    image = Image.fromarray(arr)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("resouces/consola.ttf", 20)

    line_color = (10, 150, 180)

    pad_x = 20
    pad_y = 20
    step_x = (img_w  - (pad_x * 2)) / (len(json_data["predictions"])-1)

    points = []

    for index, datapoint in enumerate(json_data["predictions"][1:]):
        timestamp = int(datapoint["timestamp"])
        prediction = float(datapoint["prediction"])

        prev_datapoint = json_data["predictions"][index]

        prev_timestamp = int(prev_datapoint["timestamp"])
        prev_prediction = float(prev_datapoint["prediction"])

        prev_x = index * step_x + pad_x
        curr_x = (index + 1) * step_x + pad_x

        prev_y = img_h - ((prev_prediction * 0.01) * (img_h - (pad_y * 2)) + pad_y)
        curr_y = img_h - ((prediction * 0.01) * (img_h - (pad_y * 2)) + pad_y)

        if index == 0:
            points.append((prev_x, prev_y, prev_prediction, prev_timestamp))

        points.append((curr_x, curr_y, prediction, timestamp))

    for index, (x, y, _, _) in enumerate(points[1:]):
        prev_x, prev_y, _, _ = points[index]

        draw.line((prev_x, prev_y, x, y), fill=line_color, width=3)

    for index, (x, y, prediction, timestamp) in enumerate(points):
        vert_anchor = "a" if index % 2 == 0 else "d"
        y_offset = 10 if index % 2 == 0 else -10

        y_1 = y + y_offset
        y_2 = y + y_offset * 3.6

        hor_anchor = "m"
        if index == 0:
            hor_anchor = "l"
        if index == len(points) - 1:
            hor_anchor = "r"

        anchor = hor_anchor + vert_anchor

        radius = 5
        draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill=(255, 0, 0))
        draw.text(
            (x, y_1 if index % 2 == 0 else y_2), format_timestamp(timestamp),
            font=font, fill=(220, 220, 220), anchor=anchor,
            align="center", stroke_fill=(0, 0, 0), stroke_width=2
        )
        draw.text(
            (x, y_2 if index % 2 == 0 else y_1), f"{prediction}%",
            font=font, fill=(220, 220, 220), anchor=anchor,
            align="center", stroke_fill=(0, 0, 0), stroke_width=2
        )

    return image

def get_closest_match(search_str: str, possible_matches: list[str], max_score: int=8) -> str | None:
    """
    Find the element in `possible_matches` that closest matches `search_str`.
    This is calculated using Levenshtein distance.
    """
    closest_match = None
    closest_match_distance = max_score or math.inf
    for possible_match in possible_matches:
        if possible_match.startswith(search_str) or possible_match.endswith(search_str):
            return possible_match

        distance = Levenshtein.distance(search_str, possible_match)
        if distance < closest_match_distance:
            closest_match = possible_match
            closest_match_distance = distance

    return closest_match

def _run_task_in_thread(func, result, exception, *args):
    try:
        result.append(func(*args))
    except Exception as exc:
        exception.append(exc)

async def run_async_in_thread(func, *args, sleep_time=0.1):
    result = []
    exception = []
    thread = Thread(target=_run_task_in_thread, args=(func, result, exception, *args))
    thread.start()

    while result == [] and exception == []:
        await asyncio.sleep(sleep_time)

    if exception != []:
        raise exception.pop()

    return result.pop()
