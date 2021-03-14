from datetime import tzinfo, timedelta, datetime
from os.path import exists
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import secrets
import json

MAIN_GUILD_ID = 619073595561213953

GUILD_IDS = [ # List of ids of guilds that Int-Far is active in.
    MAIN_GUILD_ID, 347488541397483543, 803987403932172359
]

GUILD_ABBREVIATIONS = {
    MAIN_GUILD_ID: "LN",
    347488541397483543: "DC",
    803987403932172359: "LN"
}

INTFAR_REASONS = ["Low KDA", "Many deaths", "Low KP", "Low Vision Score"]

DOINKS_REASONS = [
    "KDA larger than or equal to 10", "20 kills or more", "Half of the teams damage",
    "Getting a pentakill", "Vision score larger than 80", "Kill participation over 80%",
    "Securing all epic monsters (and more than 3)", "More than 8 cs/min"
]

STAT_COMMANDS = [
    "kills", "deaths", "kda", "damage", "cs", "cs_per_min",
    "gold", "kp", "vision_wards", "vision_score", "first_blood"
]

STAT_QUANTITY_DESC = [
    ("most", "fewest"), ("fewest", "most"), ("highest", "lowest"), ("most", "least"),
    ("most", "least"), ("most", "lowest"), ("most", "least"), ("highest", "lowest"),
    ("most", "fewest"), ("highest", "lowest"), (None, None)
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

def parse_amount_str(amount_str):
    mult = 1
    if amount_str[-1].lower() == "t":
        mult = 1e12
        amount_str = amount_str[:-1]
    elif amount_str[-1].lower() == "b":
        mult = 1e9
        amount_str = amount_str[:-1]
    elif amount_str[-1].lower() == "m":
        mult = 1e6
        amount_str = amount_str[:-1]
    elif amount_str[-1].lower() == "k":
        mult = 1e3
        amount_str = amount_str[:-1]

    return int(float(amount_str) * mult)

def generate_user_secret():
    return secrets.token_hex(nbytes=32)

def organize_intfar_stats(games_played, intfar_reason_ids):
    intfar_counts = {x: 0 for x in range(len(INTFAR_REASONS))}
    for reason_id in intfar_reason_ids:
        intfar_ids = [int(x) for x in reason_id[0]]
        for index, intfar_id in enumerate(intfar_ids):
            if intfar_id == 1:
                intfar_counts[index] += 1

    pct_intfar = (0 if games_played == 0
                  else int(len(intfar_reason_ids) / games_played * 100))
    return games_played, len(intfar_reason_ids), intfar_counts, pct_intfar

def organize_doinks_stats(doinks_reason_ids):
    doinks_counts = {x: 0 for x in range(len(DOINKS_REASONS))}
    for reason_id in doinks_reason_ids:
        intfar_ids = [int(x) for x in reason_id[0]]
        for index, intfar_id in enumerate(intfar_ids):
            if intfar_id == 1:
                doinks_counts[index] += 1
    return doinks_counts

def get_guild_abbreviation(guild_id):
    return GUILD_ABBREVIATIONS.get(guild_id, "")

def format_timestamp(timestamp):
    seconds = timestamp
    minutes = 0
    if seconds >= 60:
        minutes = int(seconds / 60)
        seconds = seconds % 60

    return f"{zero_pad(minutes)}:{zero_pad(seconds)}"

def create_predictions_timeline_image():
    filename = "resources/predictions_temp.json"

    if not exists(filename):
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
