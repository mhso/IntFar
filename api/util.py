from datetime import tzinfo, timedelta, datetime
from glob import glob
import importlib
import os
from dateutil.relativedelta import relativedelta
import json
import secrets

from PIL import Image, ImageDraw, ImageFont
import numpy as np

MAIN_GUILD_ID = 619073595561213953
MY_GUILD_ID  = 512363920044982272

SUPPORTED_GAMES = {
    "lol": "League of Legends",
    "cs2": "Counter Strike 2"
    #"csgo": "Counter Strike: Global Offensive"
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

DOINKS_REASONS = [
    "KDA larger than or equal to 10", "20 kills or more", "Half of the teams damage",
    "Getting a pentakill", "Vision score larger than 100", "Kill participation over 80%",
    "Securing all epic monsters (and more than 3)", "More than 8 cs/min"
]

STAT_COMMANDS = [
    "kills", "deaths", "assists", "kda", "damage", "cs", "cs_per_min", "gold",
    "kp", "vision_wards", "vision_score", "steals", "first_blood"
]

STAT_QUANTITY_DESC = [
    ("most", "fewest"), ("fewest", "most"), ("most", "fewest"), ("highest", "lowest"),
    ("most", "least"), ("most", "least"), ("most", "lowest"), ("most", "least"),
    ("highest", "lowest"), ("most", "fewest"), ("highest", "lowest"), ("most", "least"),
    ("most", "least"),
]

MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December"
]

class TimeZone(tzinfo):
    """
    Class for representing the time zone of Copenhagen (UTC+1).
    """
    def tzname(self, dt):
        return "Europe/Copenhagen"

    def utcoffset(self, dt):
        return self.dst(dt) + timedelta(0, 0, 0, 0, 0, 1, 0)

    def dst(self, dt):
        if dt.month < 10 or dt.month > 3:
            return timedelta(0, 0, 0, 0, 0, 0, 0)
        if dt.month == 10 and dt.day < 25:
            return timedelta(0, 0, 0, 0, 0, 1, 0)
        if dt.month == 3 and dt.day > 28:
            return timedelta(0, 0, 0, 0, 0, 0, 0)
        return timedelta(0, 0, 0, 0, 0, 1, 0)

def load_flavor_texts(filename, game=None):
    path = f"resources/flavor_texts"
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

def format_duration(dt_1, dt_2):
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

def format_duration_old(dt_1, dt_2):
    normed_dt = dt_2.replace(year=dt_1.year, month=dt_1.month)
    month_normed = dt_2.month if dt_2.month >= dt_1.month else dt_2.month + 12
    months = month_normed - dt_1.month
    if normed_dt < dt_1:
        months -= 1
    years = dt_2.year - dt_1.year
    if dt_2.month < dt_1.month:
        years -= 1
    if months == 0 and years == 0:
        td = dt_2 - dt_1
    else:
        td = normed_dt - dt_1
    days = td.days
    seconds = td.seconds
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
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
    modules = map(lambda x: x.replace(".py", ""), glob(f"{dir}/*.py"))

    subclasses = {}
    for module_name in modules:
        module_key = os.path.basename(module_name)
        if module_key not in SUPPORTED_GAMES:
            continue

        module = importlib.import_module(module_name.replace("\\", ".").replace("/", "."))
        for subclass in base_class.__subclasses__():
            if hasattr(module, subclass.__name__):
                subclasses[module_key] = subclass
                break

    return subclasses

def create_predictions_timeline_image():
    filename = "resources/predictions_temp.json"

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
