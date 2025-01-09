import json
import random
from datetime import datetime
from time import time
from dataclasses import dataclass, field
from gevent import sleep

import flask
from flask_socketio import join_room, leave_room, emit

from api.util import JEOPADY_EDITION, MONTH_NAMES, GUILD_MAP
from api.lan import is_lan_ongoing
import app.util as app_util
from discbot.commands.util import ADMIN_DISC_ID

TRACK_UNUSED = True
DO_DAILY_DOUBLE = True

QUESTIONS_PER_ROUND = 30
ROUND_NAMES = [
    "Jeopardy!",
    "Double Jeopardy!",
    "Final Jeopardy!"
]

FINALE_CATEGORY = "history"

QUESTIONS_FILE = "app/static/data/jeopardy_questions.json"
USED_QUESTIONS_FILE = "app/static/data/jeopardy_used.json"

PLAYER_NAMES = {
    115142485579137029: "Dave",
    172757468814770176: "Murt", 
    331082926475182081: "Muds",
    347489125877809155: "Nø"
}

PLAYER_INDEXES = list(PLAYER_NAMES.keys())

PLAYER_BACKGROUNDS = {
    115142485579137029: "coven_nami.png",
    172757468814770176: "pentakill_olaf.png", 
    331082926475182081: "crime_city_tf.png",
    347489125877809155: "gladiator_draven.png"
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
        "goblin"
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
        "ah_nej"
    ]
]

# Sounds played when a specific player buzzes in first
BUZZ_IN_SOUNDS = {
    115142485579137029: "buzz_dave",
    172757468814770176: "buzz_murt",
    331082926475182081: "buzz_muds",
    347489125877809155: "buzz_no",
}

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
    sid: int = field(default=None, init=False)
    n_ping_samples: int = field(default=10, init=False)
    latest_buzz: int = field(default=None, init=False)
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

@dataclass
class State:
    jeopardy_round: int
    round_name: str
    player_data: list[dict]

    @classmethod
    def from_json(cls, json_str: str):
        data = json.loads(json_str)
        data["disc_id"] = int(data["disc_id"])
        return cls(**data)

    def to_json(self):
        return json.dumps(self.__dict__)

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
    daily_double: bool
    question_asked_time: float = field(default=None, init=False)
    buzz_winner_decided: bool = field(default=False, init=False)

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

    pregame_state = State(0, "Lobby", joined_players)
    now = datetime.now()
    date = f"{MONTH_NAMES[now.month-1]} {now.year}"

    flask.current_app.config["JEOPARDY_DATA"]["state"] = pregame_state

    return app_util.make_template_context(
        "jeopardy/presenter_lobby.html",
        **pregame_state.__dict__,
        edition=JEOPADY_EDITION,
        date=date
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

def get_round_data(request_args):
    player_data = []
    contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]

    for index in range(1, len(PLAYER_NAMES) + 1):
        id_key = f"i{index}"
        name_key = f"n{index}"
        score_key = f"s{index}"
        color_key = f"c{index}"

        if id_key in request_args:
            disc_id =  int(request_args[id_key])
            buzzes = 0
            hits = 0
            misses = 0
            if disc_id in contestants:
                avatar = contestants[disc_id].avatar
                buzzes = contestants[disc_id].buzzes
                hits = contestants[disc_id].hits
                misses = contestants[disc_id].misses
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
                "name": request_args[name_key],
                "avatar": avatar,
                "score": int(request_args[score_key]),
                "buzzes": buzzes,
                "hits": hits,
                "misses": misses,
                "color": request_args[color_key],
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

    question = questions[category]["tiers"][tier]["questions"][jeopardy_round-1]
    question["id"] = jeopardy_round-1

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

        question_state = QuestionState(
            jeopardy_round,
            ROUND_NAMES[jeopardy_round-1],
            player_data,
            question_num,
            player_turn,
            questions[category]["name"],
            questions[category]["background"],
            question,
            questions[category]["tiers"][tier]["value"] * jeopardy_round,
            is_daily_double
        )
        flask.current_app.config["JEOPARDY_DATA"]["state"] = question_state

        # Get random sounds that plays for correct/wrong answers
        correct_sound = random.choice(ANSWER_SOUNDS[0])
        possible_wrong_sounds = list(ANSWER_SOUNDS[1])
        random.shuffle(possible_wrong_sounds)
        wrong_sounds = possible_wrong_sounds[:4]

        app_util.socket_io.emit("state_changed", to="contestants")

    return app_util.make_template_context(
        "jeopardy/presenter_question.html",
        buzz_sounds=BUZZ_IN_SOUNDS,
        correct_sound=correct_sound,
        wrong_sounds=wrong_sounds,
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

        with open(QUESTIONS_FILE, encoding="utf-8") as fp:
            questions = json.load(fp)

        with open(USED_QUESTIONS_FILE, encoding="utf-8") as fp:
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
            question_num,
            player_turn,
            questions,
            ordered_categories
        )
        flask.current_app.config["JEOPARDY_DATA"]["state"] = selection_state

        app_util.socket_io.emit("state_changed", to="contestants")

    return app_util.make_template_context("jeopardy/presenter_selection.html", **selection_state.__dict__)

@jeopardy_presenter_page.route("/finale/<question_id>")
def final_jeopardy(question_id):
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID and flask.current_app.config["APP_ENV"] != "dev":
        return flask.abort(404)

    question_id = int(question_id)

    with open(QUESTIONS_FILE, encoding="utf-8") as fp:
        questions = json.load(fp)

    question = questions[FINALE_CATEGORY]["tiers"][-1]["questions"][question_id]
    category_name = questions[FINALE_CATEGORY]["name"]

    player_data = get_round_data(flask.request.args)[0]

    contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]
    for data in player_data:
        disc_id = int(data["disc_id"])
        data["wager"] = contestants[disc_id].finale_wager
        answer = contestants[disc_id].finale_answer
        data["answer"] = "ikke" if answer is None else f"'{answer}'"

    jeopardy_round = 3

    finale_state = FinaleState(
        jeopardy_round,
        ROUND_NAMES[jeopardy_round-1], 
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
        player_data.sort(key=lambda x: x["score"], reverse=True)

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

        winner_ids = [str(data["disc_id"]) for data in player_data[:ties + 1]]
        endscreen_state = EndscreenState(
            4, "Endscreen", player_data, winner_desc, winner_ids, avatars
        )

        jeopardy_data["state"] = endscreen_state
        guild_id = GUILD_MAP["core"]

        if TRACK_UNUSED and flask.current_app.config["APP_ENV"] == "production" and is_lan_ongoing(time(), guild_id):
            app_util.discord_request("func", "announce_jeopardy_winner", (player_data,))

        app_util.socket_io.emit("state_changed", to="contestants")

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

@app_util.socket_io.event
def presenter_joined():
    join_room("presenter")

@app_util.socket_io.event
def join_lobby(disc_id: str, nickname: str, avatar: str, color: str):
    disc_id = int(disc_id)

    with flask.current_app.config["JEOPARDY_JOIN_LOCK"]:
        active_contestants = flask.current_app.config["JEOPARDY_DATA"]["contestants"]

        turn_id = PLAYER_INDEXES.index(disc_id)
        contestant = active_contestants.get(disc_id)
        if contestant is None:
            contestant = Contestant(disc_id, turn_id, nickname, avatar, color)
        else:
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

@app_util.socket_io.event
def enable_buzz(active_players_str: str):
    active_player_ids = json.loads(active_players_str)
    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    contestants = jeopardy_data["contestants"]
    state = jeopardy_data["state"]

    active_ids = []
    for contestant in contestants.values():
        contestant.latest_buzz = None
        if active_player_ids[contestant.index]:
            active_ids.append(contestant.index)

    state.buzz_winner_decided = False
    state.question_asked_time = time()

    emit("buzz_enabled", active_ids, to="contestants")

@app_util.socket_io.event
def buzzer_pressed(disc_id: str):
    disc_id = int(disc_id)
    jeopardy_data = flask.current_app.config["JEOPARDY_DATA"]
    contestants = jeopardy_data["contestants"]
    state = jeopardy_data["state"]

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

@app_util.socket_io.event
def correct_answer(turn_id: int):
    disc_id = PLAYER_INDEXES[turn_id]
    contestant = flask.current_app.config["JEOPARDY_DATA"]["contestants"].get(disc_id)

    if contestant is None:
        return

    contestant.hits += 1

@app_util.socket_io.event
def wrong_answer(turn_id: int):
    disc_id = PLAYER_INDEXES[turn_id]
    contestant = flask.current_app.config["JEOPARDY_DATA"]["contestants"].get(disc_id)

    if contestant is None:
        return

    contestant.misses += 1

@app_util.socket_io.event
def disable_buzz():
    state = flask.current_app.config["JEOPARDY_DATA"]["state"]

    flask.current_app.config["JEOPARDY_BUZZ_LOCK"].acquire()
    state.buzz_winner_decided = True
    flask.current_app.config["JEOPARDY_BUZZ_LOCK"].release()

    emit("buzz_disabled", to="contestants")

@app_util.socket_io.event
def first_turn(turn_id: int):
    emit("turn_chosen", turn_id, to="contestants")

@app_util.socket_io.event
def reveal_finale_category():
    emit("finale_category_revealed", to="contestants")
