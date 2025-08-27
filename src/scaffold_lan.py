from argparse import ArgumentParser, ArgumentTypeError
from datetime import datetime
import inspect
import json
import os

from jinja2.environment import Environment
from jinja2.loaders import BaseLoader
from jinja2.exceptions import TemplateNotFound

from api import util
from api import lan
from api.config import Config
from api.game_databases import get_database_client

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

def bump_jeopardy_version():
    new_version = util.JEOPARDY_ITERATION + 1
    all_lines = inspect.getsourcelines(util)[0]
    for line_no, line in enumerate(all_lines):
        if line.strip().startswith("JEOPARDY_ITERATION = "):
            all_lines[line_no] = f"JEOPARDY_ITERATION = {new_version}\n"
            break

    with open("api/lan.py", "w", encoding="utf-8") as fp:
        for line in all_lines:
            fp.write(line)

    return new_version

def create_jeopardy_folder(version: int, config: Config):
    os.mkdir(os.path.join(config.static_folder, f"img/jeopardy/{version}"))

def create_jeopardy_question_files(version: int, config: Config):
    # Create empty 'jeopardy_questions' file
    file_old = f"{config.static_folder}/data/jeopardy_questions_{version - 1}.json"
    with open(file_old, "r") as fp:
        data = json.load(fp)
        for category in data:
            for index in range(len(data[category]["tiers"])):
                data[category]["tiers"][index]["questions"] = []

    file_new = f"{config.static_folder}/data/jeopardy_questions_{version}.json"
    with open(file_new, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=4)

    # Create empty 'jeopardy_used' file
    used_file = f"{config.static_folder}/data/jeopardy_used_{version}.json"
    used_questions = {}
    for category in data:
        used_questions[category] = [
            {"active": True, "used": [], "double": False}
            for _ in range(5)
        ]

    with open(used_file, "w", encoding="utf-8") as fp:
        json.dump(used_questions, fp, indent=4)

def set_now_playing_date(date_key):
    file_path = "D:/Misc_Scripts/now_playing/live_lol.py"
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
database = get_database_client("lol", config)
date_key = f"{util.MONTH_NAMES[args.start.month - 1].lower()}_{str(args.start.year)[-2:]}"

insert_in_lan_entries(args, date_key, config)
jeopardy_version = bump_jeopardy_version()
create_jeopardy_folder(jeopardy_version, config)
create_jeopardy_question_files(jeopardy_version, config)
lan.insert_bingo_challenges(database, date_key)

if config.env == "dev":
    set_now_playing_date(date_key)
