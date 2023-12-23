import json
import random

import flask

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

jeopardy_page = flask.Blueprint("jeopardy", __name__, template_folder="templates")

@jeopardy_page.route('/')
def home():
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID:
        return flask.abort(404)

    player_data = [
        {"id": str(disc_id), "name": PLAYER_NAMES[disc_id]}
        for disc_id in PLAYER_NAMES
    ]

    return app_util.make_template_context("jeopardy/menu.html", 200, player_data=player_data)


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
            {"active": True, "used": [], "double": False}
            for _ in range(5)
        ]

    with open(used_questions_file, "w", encoding="utf-8") as fp:
        json.dump(used_questions, fp, indent=4)

    return app_util.make_text_response("Questions reset", 200)

def get_player_data(request_args):
    player_data = []

    for index in range(1, len(PLAYER_NAMES) + 1):
        id_key = f"i{index}"
        score_key = f"s{index}"
        color_key = f"c{index}"

        if id_key in request_args:
            disc_id =  int(request_args[id_key])
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
    player_data, player_turn, question_num = get_player_data(flask.request.args)

    all_data = {
        "round": jeopardy_round,
        "round_name": ROUND_NAMES[jeopardy_round-1],
        "question_num": question_num,
        "category_name": questions[category]["name"],
        "bg_image": questions[category]["background"],
        "question": question,
        "player_data": player_data,
        "player_turn": player_turn,
        "question_value": questions[category]["tiers"][tier]["value"] * jeopardy_round,
        "daily_double": is_daily_double,
        "sounds": ANSWER_SOUNDS
    }

    return app_util.make_template_context("jeopardy/question.html", **all_data)

@jeopardy_page.route("/<jeopardy_round>")
def active_jeopardy(jeopardy_round):
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID:
        return flask.abort(404)

    jeopardy_round = int(jeopardy_round)

    # Get player names and scores from query parameters
    player_data, player_turn, question_num = get_player_data(flask.request.args)        

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

    all_data = {
        "round": jeopardy_round,
        "round_name": ROUND_NAMES[jeopardy_round-1],
        "question_num": question_num,
        "questions": questions,
        "categories": ordered_categories,
        "player_data": player_data,
        "player_turn": player_turn
    }

    return app_util.make_template_context("jeopardy/selection.html", **all_data)

@jeopardy_page.route("/finale/<question_id>")
def final_jeopardy(question_id):
    question_id = int(question_id)

    questions_file = "app/static/jeopardy_questions.json"

    with open(questions_file, encoding="utf-8") as fp:
        questions = json.load(fp)

    question = questions[FINALE_CATEGORY]["tiers"][-1]["questions"][question_id]
    category_name = questions[FINALE_CATEGORY]["name"]

    player_data = get_player_data(flask.request.args)[0]

    all_data = {
        "round": 3,
        "question": question,
        "category_name": category_name,
        "player_data": player_data
    }

    return app_util.make_template_context("jeopardy/finale.html", **all_data)

@jeopardy_page.route("/endscreen")
def jeopardy_endscreen():
    player_data = get_player_data(flask.request.args)[0]

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

    all_data = {
        "player_data": player_data,
        "winner_desc": winner_desc,
        "winner_avatars": avatars
    }

    return app_util.make_template_context("jeopardy/endscreen.html", **all_data)

@jeopardy_page.route("/cheatsheet")
def answers():
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

    for category in questions:
        for tier_info in category[category]["tiers"]:
            for question in tier_info["questions"]:
                if "choices" in question:
                    question["choice_index"] = question["choices"].index(question["answer"])

    return app_util.make_template_context("jeopardy/cheat_sheet.html", questions=questions)
