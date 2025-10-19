import json
import random
from datetime import datetime
from time import time
from dataclasses import dataclass, field
from typing import Dict, List
from gevent import sleep

import flask
from flask_socketio import join_room, leave_room, emit
from mhooge_flask.logging import logger
from mhooge_flask.routing import socket_io

from api.util import JEOPARDY_ITERATION, JEOPADY_EDITION, JEOPARDY_REGULAR_ROUNDS, MONTH_NAMES
from api.lan import is_lan_ongoing, get_latest_lan_info
import app.util as app_util
from discbot.commands.util import ADMIN_DISC_ID

TRACK_UNUSED = True
DO_DAILY_DOUBLE = True

QUESTIONS_PER_ROUND = 30
# Round when Final Jeopardy is played
FINALE_ROUND = JEOPARDY_REGULAR_ROUNDS + 1
ROUND_NAMES = ["Jeopardy!"] + (["Double Jeopardy!"] * (JEOPARDY_REGULAR_ROUNDS - 1)) + ["Final Jeopardy!"]

FINALE_CATEGORY = "history"

QUESTIONS_FILE = f"app/static/data/jeopardy_questions_{JEOPARDY_ITERATION}.json"
USED_QUESTIONS_FILE = f"app/static/data/jeopardy_used_{JEOPARDY_ITERATION}.json"

PLAYER_NAMES = {
    115142485579137029: "Dave",
    172757468814770176: "Murt",
    331082926475182081: "Muds",
    219497453374668815: "Tommy"
}

PLAYER_INDEXES = list(PLAYER_NAMES.keys())

PLAYER_BACKGROUNDS = {
    115142485579137029: "coven_nami.png",
    172757468814770176: "pentakill_olaf.png", 
    331082926475182081: "crime_city_tf.png",
    219497453374668815: "bard_splash.png"
}

# Sounds for answering questions correctly/wrong.
ANSWER_SOUNDS = [
    [
        "easy_money",
        "how_lovely",
        "outta_my_face",
        "yeah",
        "heyheyhey",
        "peanut",
        "never_surrender",
        "exactly",
        "hell_yeah",
        "ult",
        "wheeze",
        "demon",
        "myoo",
        "rimelig_stor",
        "worst_laugh",
        "nyong",
        "climax",
        "cackle",
        "kabim",
        "kvinder",
        "uhu",
        "porn",
        "package_boy",
        "skorpion",
        "goblin",
        "ngh",
    ],
    [
        "mmnonono",
        "what",
        "whatemagonodo",
        "yoda",
        "daisy",
        "bass",
        "despair",
        "ahhh",
        "spil",
        "fedtmand",
        "no_way",
        "hehehe",
        "braindead",
        "big_nej",
        "junge",
        "sad_animal",
        "hold_da_op",
        "daser",
        "oh_no",
        "i_dont_know_dude",
        "disappoint",
        "nej",
        "wilhelm",
        "migjuana",
        "ah_nej",
        "dave_angy",
    ]
]

# Sounds played when a specific player buzzes in first
BUZZ_IN_SOUNDS = {
    115142485579137029: "buzz_dave",
    172757468814770176: "buzz_murt",
    331082926475182081: "buzz_muds",
    219497453374668815: "buzz_thommy",
}

@dataclass
class PowerUp:
    power_id: str
    name: str
    enabled: bool = False
    used: bool = False

    def to_json(self):
        return json.dumps(self.__dict__, default=lambda o: list(o))

    def __eq__(self, other: object) -> bool:
        return self.power_id == other.power_id

    def __hash__(self) -> int:
        return hash(self.power_id)

def _init_powerups():
    return [
        PowerUp("hijack", "Hijack"),
        PowerUp("freeze", "Freeze"),
        PowerUp("rewind", "Rewind"),
    ]

POWER_UP_IDS = [power.power_id for power in _init_powerups()]

@dataclass
class Contestant:
    disc_id: int
    index: int
    name: str
    avatar: str
    color: str
    score: int = 0
    buzzes: int = 0
    hits: int = 0
    misses: int = 0
    ping: int = field(default=30, init=False)
    sid: str = field(default=None, init=False)
    n_ping_samples: int = field(default=10, init=False)
    latest_buzz: int = field(default=None, init=False)
    power_ups: List[PowerUp] = field(default_factory=_init_powerups, init=False)
    finale_wager: int = field(default=0, init=False)
    finale_answer: int = field(default=None, init=False)
    _ping_samples: list[float] = field(default=None, init=False)

    def calculate_ping(self, time_sent, time_received):
        if self._ping_samples is None:
            self._ping_samples = []

        self._ping_samples.append((time_received - time_sent) / 2)
        self.ping = sum(self._ping_samples) / self.n_ping_samples

        if len(self._ping_samples) == self.n_ping_samples:
            self._ping_samples.pop(0)

    @staticmethod
    def from_json(json_str: str):
        data = json.loads(json_str)
        data["disc_id"] = int(data["disc_id"])
        return Contestant(**data)

    def to_json(self):
        return json.dumps(self.__dict__)

    def get_power(self, power_id: str) -> PowerUp:
        for power_up in self.power_ups:
            if power_up.power_id == power_id:
                return power_up

        return None

@dataclass
class State:
    jeopardy_round: int
    round_name: str
    player_data: list[dict]
    total_rounds: int = field(init=False, default=FINALE_ROUND)
    base_folder: str = field(init=False, default=f"img/jeopardy/{JEOPARDY_ITERATION}/")

    @classmethod
    def from_json(cls, json_str: str):
        data = json.loads(json_str)
        data["disc_id"] = int(data["disc_id"])
        return cls(**data)

    def to_json(self):
        return json.dumps(self.__dict__)

    def __post_init__(self):
        self.__dict__["total_rounds"] = self.total_rounds
        self.__dict__["base_folder"] = self.base_folder

@dataclass
class RoundState(State):
    question_num: int
    player_turn: int

@dataclass
class SelectionState(RoundState):
    questions: dict
    categories: list[str]

@dataclass
class QuestionState(RoundState):
    category_name: str
    bg_image: str
    question: dict
    question_value: int
    buzz_time: int
    daily_double: bool
    question_asked_time: float = field(default=None, init=False)
    buzz_winner_decided: bool = field(default=False, init=False)
    power_use_decided: bool = field(default=False, init=False)

@dataclass
class FinaleState(State):
    question: dict
    category_name: str

@dataclass
class EndscreenState(State):
    winner_desc: str
    winner_ids: list[str]
    winner_avatars: list[str]

jeopardy_presenter_page = flask.Blueprint("jeopardy_presenter", __name__, template_folder="templates")

@jeopardy_presenter_page.route("/")
def home():
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID and flask.current_app.config["APP_ENV"] != "dev":
        return flask.abort(404)

    active_contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]
    joined_players = [contestant.__dict__ for contestant in active_contestants.values()]
    guild_name = "CoreNibbas"
    if is_lan_ongoing(time()):
        guild_name = get_latest_lan_info().guild_name

    pregame_state = State(0, "Lobby", joined_players)
    now = datetime.now()
    date = f"{MONTH_NAMES[now.month-1]} {now.year}"

    flask.current_app.config["JEOPARDY_DATA"]["state"] = pregame_state

    return app_util.make_template_context(
        "jeopardy/presenter_lobby.html",
        **pregame_state.__dict__,
        edition=JEOPADY_EDITION,
        date=date,
        guild_name=guild_name
    )

@jeopardy_presenter_page.route("/reset_questions", methods=["POST"])
def reset_questions():
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID and flask.current_app.config["APP_ENV"] != "dev":
        return flask.abort(404)

    with open(USED_QUESTIONS_FILE, encoding="utf-8") as fp:
        used_questions = json.load(fp)

    for cat in used_questions:
        used_questions[cat] = [
            {"active": True, "used": [], "double": False}
            for _ in range(5)
        ]

    with open(USED_QUESTIONS_FILE, "w", encoding="utf-8") as fp:
        json.dump(used_questions, fp, indent=4)

    return app_util.make_text_response("Questions reset", 200)

def _sync_contestants(player_data, contestants):
    for data in player_data:
        disc_id = int(data["disc_id"])
        if disc_id not in contestants:
            contestants[disc_id] = Contestant(disc_id, data["index"], data["name"], data["avatar"], data["color"])

def get_round_data(request_args):
    player_data = []
    contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]

    for index in range(1, 5):
        id_key = f"i{index}"
        name_key = f"n{index}"
        score_key = f"s{index}"
        color_key = f"c{index}"

        if id_key in request_args:
            disc_id =  int(request_args[id_key])
            buzzes = 0
            hits = 0
            misses = 0
            finale_wager = 0
            score = int(request_args.get(score_key, 0))
            power_ups = []

            # Args from URL
            name = request_args[name_key]
            turn_id = PLAYER_INDEXES.index(disc_id)
            color = request_args[color_key]

            if disc_id in contestants:
                avatar = contestants[disc_id].avatar
                buzzes = contestants[disc_id].buzzes
                hits = contestants[disc_id].hits
                misses = contestants[disc_id].misses
                finale_wager = contestants[disc_id].finale_wager

                if contestants[disc_id].score != score:
                    contestants[disc_id].score = score

                power_ups = contestants[disc_id].power_ups
            else:
                avatar = app_util.discord_request(
                    "func", "get_discord_avatar", (disc_id, 128)
                )
                if avatar is not None:
                    avatar = flask.url_for("static", _external=True, filename=avatar.replace("app/static/", ""))
                else:
                    avatar = flask.url_for("static", _external=True, filename="img/questionmark.png")

            player_data.append({
                "disc_id": str(disc_id),
                "name": name,
                "index": turn_id,
                "avatar": avatar,
                "score": score,
                "buzzes": buzzes,
                "hits": hits,
                "misses": misses,
                "finale_wager": finale_wager,
                "color": color,
                "power_ups": [power_up.__dict__ for power_up in power_ups],
            })

    try:
        player_turn = int(request_args["turn"])
    except ValueError:
        player_turn = -1

    try:
        question_num = int(request_args["question"])
    except ValueError:
        question_num = 0

    return player_data, player_turn, question_num

@jeopardy_presenter_page.route("/<jeopardy_round>/<category>/<tier>")
def question_view(jeopardy_round, category, tier):
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID and flask.current_app.config["APP_ENV"] != "dev":
        return flask.abort(404)

    jeopardy_round = int(jeopardy_round)
    tier = int(tier) - 1

    with open(QUESTIONS_FILE, encoding="utf-8") as fp:
        questions = json.load(fp)

    with open(USED_QUESTIONS_FILE, encoding="utf-8") as fp:
        used_questions = json.load(fp)

    if jeopardy_round < FINALE_ROUND:
        question = questions[category]["tiers"][tier]["questions"][jeopardy_round - 1]
    else:
        # If we are at Final Jeopardy, choose a random question from the relevant category
        question = random.choice(questions[category]["tiers"][tier]["questions"])

    question["id"] = jeopardy_round - 1
    buzz_time = questions[category].get("buzz_time", 10)

    if TRACK_UNUSED:
        used_questions[category][tier]["used"].append(question["id"])
        used_questions[category][tier]["active"] = False

        with open(USED_QUESTIONS_FILE, "w", encoding="utf-8") as fp:
            json.dump(used_questions, fp, indent=4)

    is_daily_double = DO_DAILY_DOUBLE and used_questions[category][tier]["double"]

    # If question is multiple-choice, randomize order of choices
    if "choices" in question:
        random.shuffle(question["choices"])

    with flask.current_app.config["JEOPARDY_JOIN_LOCK"]:
        # Get player names and scores from query parameters
        player_data, player_turn, question_num = get_round_data(flask.request.args)
        contestants: Dict[int, Contestant] = flask.current_app.config["JEOPARDY_DATA"]["contestants"]
        _sync_contestants(player_data, contestants)

        # Disable hijack if question is daily double
        for contestant in contestants.values():
            for power_up in contestant.power_ups:
                power_up.enabled = power_up.power_id == "hijack" and not is_daily_double

        question_state = QuestionState(
            jeopardy_round,
            ROUND_NAMES[jeopardy_round - 1],
            player_data,
            question_num,
            player_turn,
            questions[category]["name"],
            questions[category]["background"],
            question,
            questions[category]["tiers"][tier]["value"] * jeopardy_round,
            buzz_time,
            is_daily_double
        )
        flask.current_app.config["JEOPARDY_DATA"]["state"] = question_state

        # Get random sounds that plays for correct/wrong answers
        correct_sound = random.choice(ANSWER_SOUNDS[0])
        possible_wrong_sounds = list(ANSWER_SOUNDS[1])
        random.shuffle(possible_wrong_sounds)
        wrong_sounds = possible_wrong_sounds[:4]

        socket_io.emit("state_changed", to="contestants")

    return app_util.make_template_context(
        "jeopardy/presenter_question.html",
        buzz_sounds=BUZZ_IN_SOUNDS,
        correct_sound=correct_sound,
        wrong_sounds=wrong_sounds,
        power_ups=POWER_UP_IDS,
        **question_state.__dict__
    )

@jeopardy_presenter_page.route("/<jeopardy_round>")
def active_jeopardy(jeopardy_round):
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID and flask.current_app.config["APP_ENV"] != "dev":
        return flask.abort(404)

    jeopardy_round = int(jeopardy_round)

    with flask.current_app.config["JEOPARDY_JOIN_LOCK"]:
        # Get player names and scores from query parameters
        player_data, player_turn, question_num = get_round_data(flask.request.args)
        contestants: Dict[int, Contestant] = flask.current_app.config["JEOPARDY_DATA"]["contestants"]
        _sync_contestants(player_data, contestants)

        if question_num == QUESTIONS_PER_ROUND:
            # Round done, onwards to next one
            jeopardy_round += 1
            question_num = 0

            if 1 < jeopardy_round < FINALE_ROUND:
                # The player with the lowest score at the start of a new regular round gets the turn
                lowest_score = player_data[0]["score"]
                lowers_score_index = 0

                for index, data in enumerate(player_data):
                    if data["score"] < lowest_score:
                        lowest_score = data["score"]
                        lowers_score_index = index

                player_turn = lowers_score_index

        with open(QUESTIONS_FILE, encoding="utf-8") as fp:
            questions = json.load(fp)

        with open(USED_QUESTIONS_FILE, encoding="utf-8") as fp:
            used_questions = json.load(fp)

        if jeopardy_round == FINALE_ROUND:
            ordered_categories = ["history"]
        else:
            ordered_categories = [None] * 6
            for category in questions:
                if questions[category]["order"] < 6:
                    ordered_categories[questions[category]["order"]] = category

            if question_num == 0:
                # If it's the first question of a round, set all categories to active and reset daily doubles
                for category in used_questions:
                    for tier_info in used_questions[category]:
                        tier_info["active"] = True
                        tier_info["double"] = False

                # Reset used power-ups
                for data in player_data:
                    contestant = contestants[int(data["disc_id"])]
                    fresh_power_ups = _init_powerups()
                    contestant.power_ups = fresh_power_ups
                    data["power_ups"] = [power_up.__dict__ for power_up in fresh_power_ups]

                if DO_DAILY_DOUBLE:
                    # Choose 1 or 2 random category/tier combination to be daily double
                    previous_double = None
                    for _ in range(jeopardy_round):
                        category = ordered_categories[random.randint(0, 5)]
                        tier = random.randint(0, 4)

                        while (category, tier) == previous_double:
                            category = ordered_categories[random.randint(0, 5)]
                            tier = random.randint(0, 4)

                        previous_double = (category, tier)

                        used_questions[category][tier]["double"] = True

                if TRACK_UNUSED:
                    with open(USED_QUESTIONS_FILE, "w", encoding="utf-8") as fp:
                        json.dump(used_questions, fp, indent=4)

            for category in used_questions:
                for tier, info in enumerate(used_questions[category]):
                    questions_left = any(index not in info["used"] for index in range(len(questions[category]["tiers"][tier]["questions"])))
                    questions[category]["tiers"][tier]["active"] = (not TRACK_UNUSED or (info["active"] and questions_left))
                    questions[category]["tiers"][tier]["double"] = info["double"]

        selection_state = SelectionState(
            jeopardy_round,
            ROUND_NAMES[jeopardy_round-1],
            player_data,
            question_num + 1,
            player_turn,
            questions,
            ordered_categories
        )
        flask.current_app.config["JEOPARDY_DATA"]["state"] = selection_state

        socket_io.emit("state_changed", to="contestants")

    return app_util.make_template_context("jeopardy/presenter_selection.html", **selection_state.__dict__)

@jeopardy_presenter_page.route("/finale")
def final_jeopardy():
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID and flask.current_app.config["APP_ENV"] != "dev":
        return flask.abort(404)

    question_id = 0

    with open(QUESTIONS_FILE, encoding="utf-8") as fp:
        questions = json.load(fp)

    question = questions[FINALE_CATEGORY]["tiers"][-1]["questions"][question_id]
    category_name = questions[FINALE_CATEGORY]["name"]

    player_data = get_round_data(flask.request.args)[0]
    _sync_contestants(player_data, flask.current_app.config["JEOPARDY_DATA"]["contestants"])

    contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]
    for data in player_data:
        disc_id = int(data["disc_id"])
        wager = contestants[disc_id].finale_wager
        data["wager"] = wager if wager > 0 else "intet"
        answer = contestants[disc_id].finale_answer
        data["answer"] = "ikke" if answer is None else f"'{answer}'"

    finale_state = FinaleState(
        FINALE_ROUND,
        ROUND_NAMES[FINALE_ROUND-1], 
        player_data,
        question,
        category_name
    )

    flask.current_app.config["JEOPARDY_DATA"]["state"] = finale_state

    return app_util.make_template_context("jeopardy/presenter_finale.html", **finale_state.__dict__)

@jeopardy_presenter_page.route("/endscreen")
def jeopardy_endscreen():
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID and flask.current_app.config["APP_ENV"] != "dev":
        return flask.abort(404)

    with flask.current_app.config["JEOPARDY_JOIN_LOCK"]:
        player_data = get_round_data(flask.request.args)[0]

        # Game over! Go to endscreen
        player_data = sorted(
            (
                dict(map(lambda x: (x, int(data[x]) if x == "disc_id" else data[x]), data))
                for data in player_data
            ),
            key=lambda x: x["score"],
            reverse=True
        )

        jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
        contestants = jeopardy_data["contestants"]

        if player_data[0]["disc_id"] in contestants:
            avatar = contestants[player_data[0]["disc_id"]].avatar
        else:
            avatar = app_util.discord_request("func", "get_discord_avatar", player_data[0]["disc_id"])
            if avatar is not None:
                avatar = flask.url_for("static", _external=True, filename=avatar.replace("app/static/", ""))

        avatars = [avatar]
        ties = 0
        for index, data in enumerate(player_data[1:], start=1):
            if player_data[index-1]["score"] > data["score"]:
                break

            if data["disc_id"] in contestants:
                avatar = contestants[data["disc_id"]].avatar
            else:
                avatar = app_util.discord_request("func", "get_discord_avatar", data["disc_id"])
                if avatar is not None:
                    avatar = flask.url_for("static", _external=True, filename=avatar.replace("app/static/", ""))

            avatars.append(avatar)

            ties += 1

        if ties == 0:
            winner_desc = f'<span style="color: #{player_data[0]["color"]}; font-weight: 800;">{player_data[0]["name"]}</span> wonnered!!! All hail the king!'

        elif ties == 1:
            winner_desc = (
                f'<span style="color: #{player_data[0]["color"]}">{player_data[0]["name"]}</span> '
                f'og <span style="color: #{player_data[1]["color"]}; font-weight: 800;">{player_data[1]["name"]}</span> '
                "har lige mange point, de har begge to vundet!!!"
            )

        elif ties > 1:
            players_tied = ", ".join(
                f'<span style="color: #{data["color"]}; font-weight: 800;">{data["name"]}</span>' for data in player_data[:ties]
            ) + f', og <span style="color: #{player_data[ties]["color"]}; font-weight: 800;">{player_data[ties]["name"]}</span>'

            winner_desc = (
                f"{players_tied} har alle lige mange point! De har alle sammen vundet!!!"
            )

        logger.bind(event="jeopardy_player_data", player_data=player_data).info(f"Jeopardy player data at endscreen: {player_data}")

        winner_ids = [str(data["disc_id"]) for data in player_data[:ties + 1]]
        endscreen_state = EndscreenState(
            4, "Endscreen", player_data, winner_desc, winner_ids, avatars
        )

        jeopardy_data["state"] = endscreen_state
        guild_id = get_latest_lan_info().guild_id

        if TRACK_UNUSED and flask.current_app.config["APP_ENV"] == "production" and is_lan_ongoing(time(), guild_id):
            app_util.discord_request("func", "announce_jeopardy_winner", (player_data, guild_id))

        socket_io.emit("state_changed", to="contestants")

    return app_util.make_template_context("jeopardy/presenter_endscreen.html", **endscreen_state.__dict__)

@jeopardy_presenter_page.route("/cheatsheet")
def cheatsheet():
    if (
        flask.request.authorization is None
        or (password := flask.request.authorization.parameters.get("password")) is None
        or password != flask.current_app.config["APP_CONFIG"].jeopardy_cheetsheet_pass
    ):
        response = app_util.make_text_response("Wrong password", 401)
        response.headers.add("WWW-Authenticate", "Basic")
        return response

    with open(QUESTIONS_FILE, encoding="utf-8") as fp:
        questions = json.load(fp)

    return app_util.make_template_context("jeopardy/cheat_sheet.html", questions=questions)

@socket_io.event
def presenter_joined():
    join_room("presenter")

@socket_io.event
def join_lobby(disc_id: str, nickname: str, avatar: str, color: str):
    disc_id = int(disc_id)

    with flask.current_app.config["JEOPARDY_JOIN_LOCK"]:
        active_contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]

        turn_id = PLAYER_INDEXES.index(disc_id)
        contestant = active_contestants[disc_id]
        # Check if attributes for contestant has changed
        attributes = [("index", turn_id), ("name", nickname), ("color", color)]
        for attr_name, value in attributes:
            if getattr(contestant, attr_name) != value:
                setattr(contestant, attr_name, value)

        emit("player_joined", (str(disc_id), turn_id, nickname, avatar, color), to="presenter")

        # Add socket IO session ID to contestant and join 'contestants' room
        print(f"User with name {nickname}, disc_id {disc_id}, and SID {flask.request.sid} joined the lobby")
        leave_room("contestants", contestant.sid)
        join_room("contestants")
        contestant.sid = flask.request.sid
        active_contestants[disc_id] = contestant

@socket_io.event
def enable_buzz(active_players_str: str):
    active_player_ids = json.loads(active_players_str)
    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    contestants = jeopardy_data["contestants"]
    state: QuestionState = jeopardy_data["state"]

    active_ids = []
    for contestant in contestants.values():
        contestant.latest_buzz = None
        if active_player_ids[contestant.index]:
            active_ids.append(contestant.index)

    state.buzz_winner_decided = False
    state.question_asked_time = time()

    emit("buzz_enabled", active_ids, to="contestants")

@socket_io.event
def enable_powerup(disc_id: str, power_id: str):
    if disc_id is not None:
        disc_id = int(disc_id)

    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    state: QuestionState = jeopardy_data["state"]
    contestants: Dict[str, Contestant] = jeopardy_data["contestants"]

    if disc_id is not None:
        player_ids = [disc_id]

    else:
        player_ids = list(contestants.keys())

    skip_contestants = []
    for player_id in player_ids:
        contestant = contestants[player_id]
        power_up = contestant.get_power(power_id)
        if power_up.used:
            skip_contestants.append(contestant.sid)
            continue

        power_up.enabled = True

    state.power_use_decided = False

    if skip_contestants != [] and disc_id is not None:
        return

    send_to = contestants[disc_id].sid if disc_id is not None else "contestants"
    emit("power_up_enabled", power_id, to=send_to, skip_sid=skip_contestants)

@socket_io.event
def disable_powerup(disc_id: str | None, power_id: str | None):
    if disc_id is not None:
        disc_id = int(disc_id)

    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    state: QuestionState = jeopardy_data["state"]
    contestants: Dict[str, Contestant] = jeopardy_data["contestants"]

    if disc_id is not None:
        player_ids = [disc_id]

    else:
        player_ids = list(contestants.keys())

    power_ids = [power_id] if power_id is not None else list(POWER_UP_IDS)
    for player_id in player_ids:
        contestant = contestants[player_id]
        for pow_id in power_ids:
            power = contestant.get_power(pow_id)
            power.enabled = False

    state.power_use_decided = True

    send_to = contestants[disc_id].sid if disc_id is not None else "contestants"
    emit("power_ups_disabled", power_ids, to=send_to)

@socket_io.event
def buzzer_pressed(disc_id: str):
    disc_id = int(disc_id)
    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    contestants = jeopardy_data["contestants"]
    state: QuestionState = jeopardy_data["state"]

    contestant = contestants.get(disc_id)

    if contestant is None:
        return

    contestant.latest_buzz = time() - (contestant.ping / 1000)
    time_taken = f"{contestant.latest_buzz - state.question_asked_time:.2f}"
    contestant.buzzes += 1

    emit("buzz_received", (contestant.index, time_taken), to="presenter")
    print(f"Buzz from {contestant.name} (#{contestant.index}, {contestant.sid}): {contestant.latest_buzz}, ping: {contestant.ping}", flush=True)

    sleep(min(max(max(c.ping / 1000, 0.01) for c in contestants.values()), 1))

    # Make sure no other requests can declare a winner by using a lock
    with flask.current_app.config["JEOPARDY_BUZZ_LOCK"]:
        if state.buzz_winner_decided:
            return

        state.buzz_winner_decided = True

        earliest_buzz_time = time()
        earliest_buzz_player = None
        for c in contestants.values():
            if c.latest_buzz is not None and c.latest_buzz < earliest_buzz_time:
                earliest_buzz_time = c.latest_buzz
                earliest_buzz_player = c

        # Reset buzz-in times
        for c in contestants.values():
            c.latest_buzz = None

        emit("buzz_winner", to=earliest_buzz_player.sid)
        emit("buzz_winner", earliest_buzz_player.index, to="presenter")
        emit("buzz_loser", to="contestants", skip_sid=earliest_buzz_player.sid)

@socket_io.event
def correct_answer(turn_id: int, value: int):
    disc_id = PLAYER_INDEXES[turn_id]
    contestant: Contestant = flask.current_app.config["JEOPARDY_DATA"]["contestants"].get(disc_id)

    if contestant is None:
        return

    contestant.hits += 1
    contestant.score += value

@socket_io.event
def wrong_answer(turn_id: int):
    disc_id = PLAYER_INDEXES[turn_id]
    contestant: Contestant = flask.current_app.config["JEOPARDY_DATA"]["contestants"].get(disc_id)

    if contestant is None:
        return

    contestant.misses += 1

@socket_io.event
def disable_buzz():
    state = flask.current_app.config["JEOPARDY_DATA"]["state"]

    with flask.current_app.config["JEOPARDY_BUZZ_LOCK"]:
        state.buzz_winner_decided = True

    emit("buzz_disabled", to="contestants")

@socket_io.event
def first_turn(turn_id: int):
    emit("turn_chosen", int(turn_id), to="contestants")

@socket_io.event
def use_power_up(disc_id: str, power_id: str):
    disc_id = int(disc_id)

    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    state: QuestionState = jeopardy_data["state"]
    contestant: Contestant = jeopardy_data["contestants"].get(disc_id)

    if contestant is None:
        return

    print(f"Power up '{power_id}' used by {contestant.name}", flush=True)

    with flask.current_app.config["JEOPARDY_POWER_LOCK"]:
        if state.power_use_decided:
            return

        state.power_use_decided = True

        power_up = contestant.get_power(power_id)
        if power_up.used: # Contestant has already used this power_up
            return

        power_up.used = True

        if power_id in ("hijack", "rewind"):
            emit("buzz_disabled", to="contestants", skip_sid=contestant.sid)

        emit("power_ups_disabled", list(POWER_UP_IDS), to="contestants")
        emit("power_up_used", (contestant.index, power_id), to="presenter")
        emit("power_up_used", power_id, to=contestant.sid)

@socket_io.event
def enable_finale_wager():
    emit("finale_wager_enabled", to="contestants")

@socket_io.event
def reveal_finale_category():
    emit("finale_category_revealed", to="contestants")
