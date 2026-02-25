from argparse import ArgumentParser, ArgumentTypeError
from datetime import datetime
import inspect
import json
import os

from jinja2.environment import Environment
from jinja2.loaders import BaseLoader
from jinja2.exceptions import TemplateNotFound

from intfar.api import util
from intfar.api import lan
from intfar.api.config import Config
from intfar.api.game_databases import get_database_client
from intfar.api.game_databases.lol import LoLGameDatabase

parser = ArgumentParser()
PARTICIPANTS_DICT = {
    "dave": 115142485579137029,
    "murt": 172757468814770176,
    "gual": 267401734513491969,
    "muds": 331082926475182081,
    "nønø": 347489125877809155,
    "thommy": 219497453374668815,
}

def datetime_type(iso_string, max_date):
    try:
        dt = datetime.fromisoformat(iso_string)
        if len(iso_string) <= 10:
            if max_date:
                dt = dt.replace(hour=23, minute=59, second=59)

        return dt
    except ValueError:
        raise ArgumentTypeError("Invalid ISO datetime string")

class TemplateLoader(BaseLoader):
    def __init__(self, config: Config):
        self.path = config.misc_folder

    def get_source(self, environment, template):
        path = os.path.join(self.path, template)
        if not os.path.exists(path):
            raise TemplateNotFound(template)

        mtime = os.path.getmtime(path)
        with open(path) as f:
            source = f.read()

        return source, path, lambda: mtime == os.path.getmtime(path)

def render_lan_entry(args, date_key, config):
    participants = [(PARTICIPANTS_DICT[name], name.capitalize()) for name in PARTICIPANTS_DICT]

    jinja_env = Environment(loader=TemplateLoader(config))
    template = jinja_env.get_template("lan_entry.py.jinja")
    return template.render(
        date_key=date_key,
        start_time=repr(args.start).removeprefix("datetime."),
        end_time=repr(args.end).removeprefix("datetime."),
        participants=participants,
        guild_name=args.guild
    )

def insert_in_lan_entries(args, date_key, config: Config):
    """Insert into 'LAN_ENTRIES' in 'api/lan.py'"""
    all_lines = inspect.getsourcelines(lan)[0]
    found_dict = False
    for line_no, line in enumerate(all_lines):
        if line.strip() == "LAN_PARTIES = {":
            found_dict = True
        elif found_dict and line.strip() == "}":
            new_text = [f"{l}\n" for l in render_lan_entry(args, date_key, config).split("\n")]
            all_lines[line_no - 1] = all_lines[line_no - 1].removesuffix("\n") + ",\n"
            all_lines = all_lines[:line_no] + new_text + all_lines[line_no:]

    with open("api/lan.py", "w", encoding="utf-8") as fp:
        for line in all_lines:
            fp.write(line)

def set_now_playing_date(date_key):
    file_path = "/mnt/d/Misc_Scripts/now_playing/live_lol.py"
    lines = []
    with open(file_path, "r", encoding="utf-8") as fp:
        for line in fp:
            if line.strip().startswith("LAN_DATE = "):
                lines.append(f'LAN_DATE = "{date_key}"\n')
            else:
                lines.append(line)

    with open(file_path, "w", encoding="utf-8") as fp:
        for line in lines:
            fp.write(line)

parser.add_argument("start", type=lambda x: datetime_type(x, False), help="ISO format datetime string")
parser.add_argument("end", type=lambda x: datetime_type(x, True), help="ISO format datetime string")
parser.add_argument("-p", "--participants", type=str, nargs=5, default=[name for name in PARTICIPANTS_DICT if name != "thommy"])
parser.add_argument("-g", "--guild", choices=list(util.GUILD_MAP.keys()), default="core")

args = parser.parse_args()

config = Config()
database: LoLGameDatabase = get_database_client("lol", config)
date_key = f"{util.MONTH_NAMES[args.start.month - 1].lower()}_{str(args.start.year)[-2:]}"

insert_in_lan_entries(args, date_key, config)
lan.insert_bingo_challenges(database, date_key)

if config.env == "dev":
    set_now_playing_date(date_key)
