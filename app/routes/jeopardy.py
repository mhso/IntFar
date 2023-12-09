import json
import random

import flask

import app.util as app_util
from discbot.commands.util import ADMIN_DISC_ID

TRACK_UNUSED = False
ROUND_NAMES = [
    "Jeopardy!",
    "Double Jeopardy!",
    "Final Jeopardy!"
]

jeopardy_page = flask.Blueprint("jeopardy", __name__, template_folder="templates")

@jeopardy_page.route('/')
def home():
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID:
        return flask.abort(404)

    return app_util.make_template_context("jeopardy/menu.html", 200)

@jeopardy_page.route("/<jeopardy_round>/score")
def scoreboard_view(jeopardy_round):
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID:
        return flask.abort(404)

    contestants = flask.request.cookies.get("jeopardy_contestants", [])
    scores = int(flask.request.cookies.get("jeopardy_scores", []))

    return app_util.make_template_context(
        "jeopardy_score.html",
        200,
        round=int(jeopardy_round),
        contestants=contestants,
        scores=scores
    )

@jeopardy_page.route("/reset_questions", methods=["POST"])
def reset_questions():
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID:
        return flask.abort(404)

    used_questions_file = "app/static/jeopardy_used.json"

    with open(used_questions_file, encoding="utf-8") as fp:
        used_questions = json.load(fp)

    for cat in used_questions:
        used_questions[cat] = [
            {"active": True, "used": []}
            for _ in range(5)
        ]

    with open(used_questions_file, "w", encoding="utf-8") as fp:
        json.dump(used_questions, fp, indent=4)

    return app_util.make_text_response("Questions reset", 200)

def get_player_data(request_args):
    player_data = []

    max_players = 6
    for index in range(1, max_players + 1):
        name_key = f"p{index}"
        score_key = f"s{index}"
        color_key = f"c{index}"

        if name_key in request_args:
            player_data.append({
                "name": request_args[name_key],
                "score": int(request_args[score_key]),
                "color": request_args[color_key]
            })

    player_turns = list(map(int, request_args["turns"].split(",")))
    if len(player_turns) == 1 and player_turns[0] == -1:
        player_turns = []

    return player_data, player_turns

@jeopardy_page.route("/<jeopardy_round>/<category>/<tier>")
def question_view(jeopardy_round, category, tier):
    jeopardy_round = int(jeopardy_round)
    tier = int(tier) - 1

    questions_file = "app/static/jeopardy_questions.json"
    used_questions_file = "app/static/jeopardy_used.json"

    with open(questions_file, encoding="utf-8") as fp:
        questions = json.load(fp)

    with open(used_questions_file, encoding="utf-8") as fp:
        used_questions = json.load(fp)

    question_possibilities = []
    for question in questions[category]["tiers"][tier]["questions"]:
        if not TRACK_UNUSED or question["id"] not in used_questions[category][tier]["used"]:
            question_possibilities.append(question)

    question_index = random.randint(0, len(question_possibilities)-1)
    question = question_possibilities[question_index]

    if TRACK_UNUSED:
        used_questions[category][tier]["used"].append(question["id"])
        used_questions[category][tier]["active"] = False

        with open(used_questions_file, "w", encoding="utf-8") as fp:
            json.dump(used_questions, fp, indent=4)

    # Sounds for answering questions correctly/wrong.
    sounds = [
        [
            "easy_money",
            "how_lovely",
            "outta_my_face",
            "yeah",
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
            "nej"
        ]
    ]

    # Get player names and scores from query parameters
    player_data, player_turns = get_player_data(flask.request.args)

    all_data = {
        "round": jeopardy_round,
        "round_name": ROUND_NAMES[jeopardy_round-1],
        "category_name": questions[category]["name"],
        "question": question,
        "player_data": player_data,
        "player_turns": player_turns,
        "question_value": questions[category]["tiers"][tier]["value"] * jeopardy_round,
        "sounds": sounds
    }

    return app_util.make_template_context("jeopardy/question.html", **all_data)

@jeopardy_page.route("/<jeopardy_round>/<question_num>")
def active_jeopardy(jeopardy_round, question_num):
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID:
        return flask.abort(404)

    jeopardy_round = int(jeopardy_round)
    question_num = int(question_num)
    total_questions = 30

    if question_num == total_questions:
        # Round 1 done, onwards to next one
        jeopardy_round += 1

    questions_file = "app/static/jeopardy_questions.json"
    used_questions_file = "app/static/jeopardy_used.json"

    with open(questions_file, encoding="utf-8") as fp:
        questions = json.load(fp)

    with open(used_questions_file, encoding="utf-8") as fp:
        used_questions = json.load(fp)

    if jeopardy_round == 1 and question_num == 0:
        # If it's the first round, set all categories to active
        for category in used_questions:
            for tier_info in used_questions[category]:
                tier_info["active"] = True

    if jeopardy_round == 3:
        category = "bois"
        return None # Handle 'Final Jeopardy!' round

    for category in used_questions:
        for tier, info in enumerate(used_questions[category]):
            questions[category]["tiers"][tier]["active"] = (not TRACK_UNUSED or info["active"])

    ordered_categories = [None] * 6
    for category in questions:
        if questions[category]["order"] < 6:
            ordered_categories[questions[category]["order"]] = category

    # Get player names and scores from query parameters
    player_data, player_turns = get_player_data(flask.request.args)

    all_data = {
        "round": jeopardy_round,
        "round_name": ROUND_NAMES[jeopardy_round-1],
        "question_num": question_num,
        "questions": questions,
        "categories": ordered_categories,
        "player_data": player_data,
        "player_turns": player_turns
    }

    return app_util.make_template_context("jeopardy/selection.html", **all_data)
