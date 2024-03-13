import json
import random
from time import time
from dataclasses import dataclass, field
from gevent import sleep

import flask
from flask_socketio import join_room, emit

import app.util as app_util
from discbot.commands.util import ADMIN_DISC_ID

TRACK_UNUSED = True
QUESTIONS_PER_ROUND = 30
ROUND_NAMES = [
    "Jeopardy!",
    "Double Jeopardy!",
    "Final Jeopardy!"
]
FINALE_CATEGORY = "bois"
PLAYER_NAMES = {
    115142485579137029: "Dave",
    172757468814770176: "Murt", 
    331082926475182081: "Muds",
    347489125877809155: "Nø"
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
        "package_boy"
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
        "dåser",
        "oh_no",
        "i_dont_know_dude",
        "disappoint",
        "nej",
        "wilhelm"
    ]
]

LOBBY_CODE = "LoLJeopardy2024"

@dataclass
class Contestant:
    disc_id: int
    index: int
    name: str
    avatar: str
    color: str
    score: int = 0
    ping: int = field(default=30, init=False)
    n_ping_samples: int = field(default=10, init=False)
    latest_buzz: int = field(default=None, init=False)
    _ping_samples: list[float] = field(default=None, init=False)

    def calculate_ping(self, client_time):
        server_time = time() * 1000
        if self._ping_samples is None:
            self._ping_samples = []

        self._ping_samples.append(server_time - client_time)
        self.ping = sum(self._ping_samples) / self.n_ping_samples

        if len(self._ping_samples) == self.n_ping_samples:
            self._ping_samples.pop(0)

    def calculate_buzz_time(self):
        self.latest_buzz = time() * 1000 - self.ping

    @staticmethod
    def from_json(json_str: str):
        data = json.loads(json_str)
        data["disc_id"] = int(data["disc_id"])
        return Contestant(**data)

    def to_json(self):
        return json.dumps(self.__dict__)

@dataclass
class State:
    jeopardy_round: int
    round_name: str
    question_num: int
    player_data: list[dict]
    player_turn: int

    @classmethod
    def from_json(cls, json_str: str):
        data = json.loads(json_str)
        data["disc_id"] = int(data["disc_id"])
        return cls(**data)

    def to_json(self):
        return json.dumps(self.__dict__)

@dataclass
class SelectionState(State):
    questions: dict
    categories: list[str]

@dataclass
class QuestionState(State):
    category_name: str
    bg_image: str
    question: dict
    question_value: int
    daily_double: bool
    buzz_winner_decided: bool = field(default=False, init=False)

jeopardy_presenter_page = flask.Blueprint("jeopardy_presenter", __name__, template_folder="templates")

@jeopardy_presenter_page.route("/")
def home():
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID and flask.current_app.config["APP_ENV"] != "dev":
        return flask.abort(404)

    active_contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]
    joined_players = [contestant.__dict__ for contestant in active_contestants.values()]

    return app_util.make_template_context(
        "jeopardy/menu.html",
        200,
        lobby_code=LOBBY_CODE,
        joined_players=joined_players
    )

@jeopardy_presenter_page.route("/reset_questions", methods=["POST"])
def reset_questions():
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID and flask.current_app.config["APP_ENV"] != "dev":
        return flask.abort(404)

    used_questions_file = "app/static/jeopardy_used.json"

    with open(used_questions_file, encoding="utf-8") as fp:
        used_questions = json.load(fp)

    for cat in used_questions:
        used_questions[cat] = [
            {"active": True, "used": [], "double": False}
            for _ in range(5)
        ]

    with open(used_questions_file, "w", encoding="utf-8") as fp:
        json.dump(used_questions, fp, indent=4)

    return app_util.make_text_response("Questions reset", 200)

def get_round_data(request_args):
    player_data = []
    contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]

    for index in range(1, len(PLAYER_NAMES) + 1):
        id_key = f"i{index}"
        score_key = f"s{index}"
        color_key = f"c{index}"

        if id_key in request_args:
            disc_id =  int(request_args[id_key])
            if disc_id in contestants:
                avatar = contestants[contestants].avatar
            else:
                avatar = app_util.discord_request(
                    "func", "get_discord_avatar", (disc_id, 128)
                )
            if avatar is not None:
                avatar = flask.url_for("static", filename=avatar.replace("app/static/", ""))

            player_data.append({
                "id": str(disc_id),
                "name": PLAYER_NAMES[disc_id],
                "avatar": avatar,
                "score": int(request_args[score_key]),
                "color": request_args[color_key]
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

    questions_file = "app/static/jeopardy_questions.json"
    used_questions_file = "app/static/jeopardy_used.json"

    with open(questions_file, encoding="utf-8") as fp:
        questions = json.load(fp)

    with open(used_questions_file, encoding="utf-8") as fp:
        used_questions = json.load(fp)

    question_possibilities = []
    for index, question in enumerate(questions[category]["tiers"][tier]["questions"]):
        if not TRACK_UNUSED or index not in used_questions[category][tier]["used"]:
            question_possibilities.append(question)
            question["id"] = index

    question_index = random.randint(0, len(question_possibilities)-1)
    question = question_possibilities[question_index]

    if TRACK_UNUSED:
        used_questions[category][tier]["used"].append(question["id"])
        used_questions[category][tier]["active"] = False

        with open(used_questions_file, "w", encoding="utf-8") as fp:
            json.dump(used_questions, fp, indent=4)

    is_daily_double = used_questions[category][tier]["double"]

    # If question is multiple-choice, randomize order of choices
    if "choices" in question:
        random.shuffle(question["choices"])

    # Get player names and scores from query parameters
    player_data, player_turn, question_num = get_round_data(flask.request.args)

    question_state = QuestionState(
        jeopardy_round,
        ROUND_NAMES[jeopardy_round-1],
        question_num,
        player_data,
        player_turn,
        questions[category]["name"],
        questions[category]["background"],
        question,
        questions[category]["tiers"][tier]["value"] * jeopardy_round,
        is_daily_double
    )
    flask.current_app.config["JEOPARDY_DATA"]["state"] = question_state

    app_util.socket_io.emit("state_changed", to="contestants")

    return app_util.make_template_context(
        "jeopardy/question.html",
        sounds=ANSWER_SOUNDS,
        **question_state.__dict__
    )

@jeopardy_presenter_page.route("/<jeopardy_round>")
def active_jeopardy(jeopardy_round):
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID and flask.current_app.config["APP_ENV"] != "dev":
        return flask.abort(404)

    jeopardy_round = int(jeopardy_round)

    # Get player names and scores from query parameters
    player_data, player_turn, question_num = get_round_data(flask.request.args)        

    if question_num == QUESTIONS_PER_ROUND:
        # Round 1 done, onwards to next one
        jeopardy_round += 1
        question_num = 0

        if jeopardy_round == 2:
            # The player with the lowest score at the start of round 2 gets the turn
            lowest_score = player_data[0]["score"]
            lowers_score_index = 0

            for index, data in enumerate(player_data):
                if data["score"] < lowest_score:
                    lowest_score = data["score"]
                    lowers_score_index = index

            player_turn = lowers_score_index

    questions_file = "app/static/jeopardy_questions.json"
    used_questions_file = "app/static/jeopardy_used.json"

    with open(questions_file, encoding="utf-8") as fp:
        questions = json.load(fp)

    with open(used_questions_file, encoding="utf-8") as fp:
        used_questions = json.load(fp)

    if jeopardy_round == 3:
        ordered_categories = ["bois"]
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

            # Choose 1 or 2 random category/tier combination to be daily double
            double_questions = jeopardy_round
            previous_double = None
            for _ in range(double_questions):
                category = ordered_categories[random.randint(0, 5)]
                tier = random.randint(0, 4)

                while (category, tier) == previous_double:
                    category = ordered_categories[random.randint(0, 5)]
                    tier = random.randint(0, 4)

                previous_double = (category, tier)

                used_questions[category][tier]["double"] = True

            if TRACK_UNUSED:
                with open(used_questions_file, "w", encoding="utf-8") as fp:
                    json.dump(used_questions, fp, indent=4)

        for category in used_questions:
            for tier, info in enumerate(used_questions[category]):
                questions_left = any(index not in info["used"] for index in range(len(questions[category]["tiers"][tier]["questions"])))
                questions[category]["tiers"][tier]["active"] = (not TRACK_UNUSED or (info["active"] and questions_left))
                questions[category]["tiers"][tier]["double"] = info["double"]

    selection_state = SelectionState(
        jeopardy_round,
        ROUND_NAMES[jeopardy_round-1],
        question_num,
        player_data,
        player_turn,
        questions,
        ordered_categories
    )
    flask.current_app.config["JEOPARDY_DATA"]["state"] = selection_state

    app_util.socket_io.emit("state_changed", to="contestants")

    return app_util.make_template_context("jeopardy/selection.html", **selection_state.__dict__)

@jeopardy_presenter_page.route("/finale/<question_id>")
def final_jeopardy(question_id):
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID and flask.current_app.config["APP_ENV"] != "dev":
        return flask.abort(404)

    question_id = int(question_id)

    questions_file = "app/static/jeopardy_questions.json"

    with open(questions_file, encoding="utf-8") as fp:
        questions = json.load(fp)

    question = questions[FINALE_CATEGORY]["tiers"][-1]["questions"][question_id]
    category_name = questions[FINALE_CATEGORY]["name"]

    player_data = get_round_data(flask.request.args)[0]

    return app_util.make_template_context(
        "jeopardy/finale.html",
        round=3,
        question=question,
        category_name=category_name,
        player_data=player_data
    )

@jeopardy_presenter_page.route("/endscreen")
def jeopardy_endscreen():
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID and flask.current_app.config["APP_ENV"] != "dev":
        return flask.abort(404)

    player_data = get_round_data(flask.request.args)[0]

    # Game over! Go to endscreen
    player_data.sort(key=lambda x: x["score"], reverse=True)

    avatar = app_util.discord_request("func", "get_discord_avatar", player_data[0]["id"])
    if avatar is not None:
        avatar = flask.url_for("static", filename=avatar.replace("app/static/", ""))

    avatars = [avatar]
    ties = 0
    for index, data in enumerate(player_data[1:], start=1):
        if player_data[index-1]["score"] > data["score"]:
            break

        avatar = app_util.discord_request("func", "get_discord_avatar", data["id"])
        if avatar is not None:
            avatar = flask.url_for("static", filename=avatar.replace("app/static/", ""))

        avatars.append(avatar)

        ties += 1

    if ties == 0:
        winner_desc = f'<span style="color: #{player_data[0]["color"]}">{player_data[0]["name"]}</span> wonnered!!! All hail the king!'

    elif ties == 1:
        winner_desc = (
            f'<span style="color: #{player_data[0]["color"]}">{player_data[0]["name"]}</span> '
            f'og <span style="color: #{player_data[1]["color"]}">{player_data[1]["name"]}</span> '
            "har lige mange point, de har begge to vundet!!!"
        )

    elif ties > 1:
        players_tied = ", ".join(
            f'<span style="color: #{data["color"]}">{data["name"]}</span>' for data in player_data[:ties]
        ) + f', og <span style="color: #{player_data[ties]["color"]}">{player_data[ties]["name"]}</span>'

        winner_desc = (
            f"{players_tied} har alle lige mange point! De har alle sammen vundet!!!"
        )

    app_util.discord_request("func", "announce_jeopardy_winner", (player_data,))

    return app_util.make_template_context(
        "jeopardy/endscreen.html",
        player_data=player_data,
        winner_desc=winner_desc,
        winner_avatars=avatars
    )

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

    questions_file = "app/static/jeopardy_questions.json"

    with open(questions_file, encoding="utf-8") as fp:
        questions = json.load(fp)

    return app_util.make_template_context("jeopardy/cheat_sheet.html", questions=questions)

@app_util.socket_io.event
def presenter_joined():
    print(f"Presenter is ready")
    join_room("presenter")

@app_util.socket_io.event
def join_lobby(disc_id, nickname, avatar, color):
    disc_id = int(disc_id)

    active_contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]
    if disc_id not in active_contestants:
        print(f"User with name {nickname} and ID {disc_id} joined the lobby")
        turn_id = list(PLAYER_NAMES.keys()).index(disc_id)
        active_contestants[disc_id] = Contestant(disc_id, turn_id, nickname, avatar, color)
        join_room("contestants")
        emit("player_joined", (str(disc_id), nickname, avatar, color), to="presenter")

@app_util.socket_io.event
def buzzer_pressed(disc_id):
    disc_id = int(disc_id)
    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    contestants = jeopardy_data["contestants"]
    state = jeopardy_data["state"]

    contestant = contestants.get(disc_id)
    print(f"User with ID {disc_id} pressed the buzzer")

    if contestant is not None:
        contestant.calculate_buzz_time()

        sleep(max(c.ping for c in contestants))

        if state.buzz_winner_decided:
            return

        # Make sure no other requests can declare a winner using a lock
        flask.current_app.config["JEOPARDY_LOCK"].acquire()

        state.buzz_winner_decided = True

        earliest_buzz_time = time()
        earliest_buzz_player = None
        for c in contestants:
            if c.latest_buzz < earliest_buzz_time:
                earliest_buzz_time = c.latest_buzz
                earliest_buzz_player = c.disc_id

        emit("buzz_winner", earliest_buzz_player, include_self=False, broadcast=True)
        flask.current_app.config["JEOPARDY_LOCK"].release()
