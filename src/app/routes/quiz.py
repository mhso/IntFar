import json
import random

import flask

import app.util as app_util
from discbot.commands.util import ADMIN_DISC_ID

TRACK_UNUSED = True

quiz_page = flask.Blueprint("quiz", __name__, template_folder="templates")

@quiz_page.route('/')
def home():
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID:
        return flask.abort(404)

    return app_util.make_template_context("quiz.html", 200)

@quiz_page.route("/<quiz_round>/score")
def scoreboard_view(quiz_round):
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID:
        return flask.abort(404)

    team_blue = flask.request.cookies.get("team_blue", "Team Blue")
    team_red = flask.request.cookies.get("team_red", "Team Red")

    score_blue = int(flask.request.cookies.get("score_blue", 0))
    score_red = int(flask.request.cookies.get("score_red", 0))

    return app_util.make_template_context(
        "quiz_score.html", 200, round=int(quiz_round),
        team_blue=team_blue, team_red=team_red,
        score_blue=score_blue, score_red=score_red
    )

@quiz_page.route("/reset_questions", methods=["POST"])
def reset_questions():
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID:
        return flask.abort(404)

    used_questions_file = "app/static/quiz_used.json"

    with open(used_questions_file, encoding="utf-8") as fp:
        used_questions = json.load(fp)

    for cat in used_questions:
        used_questions[cat] = []

    with open(used_questions_file, "w", encoding="utf-8") as fp:
        json.dump(used_questions, fp)

    return app_util.make_text_response("Questions reset", 200)

def get_pretty_category(category):
    if category == "intfar":
        pretty_category = "Int-Far"
    else:
        pretty_category = " ".join([x.capitalize() for x in category.split("_")])
    return pretty_category

@quiz_page.route("/<quiz_round>/<question>")
def active_quiz(quiz_round, question):
    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user != ADMIN_DISC_ID:
        return flask.abort(404)

    question_order_file = "app/static/quiz_order.json"
    with open(question_order_file, encoding="utf-8") as fp:
        category_orders = json.load(fp)

    question = int(question)
    used_quiz_categories = flask.current_app.config["QUIZ_CATEGORIES"]
    category = quiz_round
    round_from_category = category in category_orders

    selection_round = False
    if quiz_round == "selection":
        selection_round = True
        quiz_round = 3
    elif round_from_category:
        quiz_round = 3
    else:
        quiz_round = int(quiz_round)

    total_questions = 10 if quiz_round < 3 else 4
    if question > total_questions: # A round is over, show scores.
        return scoreboard_view(quiz_round)

    if quiz_round == 3: # We are doing round 3.
        used_quiz_categories.add(category)
        if question == 1: # Determine who gets to select a category first.
            score_blue = int(flask.request.cookies.get("score_blue"))
            score_red = int(flask.request.cookies.get("score_red"))
            if score_blue == score_red: # Both teams have equal points, select a team at random.
                blue_team = random.random() > 0.5
            else: # The team with fewest points get to start.
                blue_team = score_blue < score_red
        else: # The team that didn't play previously plays now.
            blue_team = not flask.current_app.config["QUIZ_TEAM_BLUE"]

        if round_from_category:
            flask.current_app.config["QUIZ_TEAM_BLUE"] = blue_team # Remember current team.
    else:
        category = category_orders[(question - 1) // 2]
        blue_team = question % 2 == 1

    questions_file = "app/static/quiz_questions.json"
    used_questions_file = "app/static/quiz_used.json"

    all_data = {
        "round": quiz_round, "question_num": question,
        "total_questions": total_questions, "blue_team": blue_team
    }

    if selection_round:
        all_data["categories"] = [
            (get_pretty_category(cat), cat, cat in used_quiz_categories) for cat in category_orders
        ]
        return app_util.make_template_context("quiz.html", 200, **all_data)

    first_round = quiz_round == 1 and question == 1

    with open(questions_file, encoding="utf-8") as fp:
        questions = json.load(fp)[category]

    with open(used_questions_file, encoding="utf-8") as fp:
        used_questions = json.load(fp)

    if len(questions) == len(used_questions[category]):
        all_data["out_of_questions"] = True
        return app_util.make_template_context("quiz.html", 200, **all_data)

    usable_indices = [x for x in range(len(questions)) if x not in used_questions[category]]
    question_index = usable_indices[random.randint(0, len(usable_indices)-1)]
    question_data = questions[question_index]

    if TRACK_UNUSED:
        used_questions[category].append(question_index)

        with open(used_questions_file, "w", encoding="utf-8") as fp:
            json.dump(used_questions, fp)

    pretty_category = get_pretty_category(category)

    all_data["category"] = pretty_category
    all_data.update(question_data)

    # Sounds for answering questions correctly/wrong.
    all_data["sounds"] = [
        ["easy_money", "how_lovely", "outta_my_face", "yeah"],
        ["mmnonono", "what", "whatemagonodo", "yoda"]
    ]

    resp = flask.make_response(
        app_util.make_template_context("quiz.html", 200, **all_data)
    )

    if first_round:
        # Reset scores for both teams.
        resp.set_cookie("score_blue", "0", path="/intfar/quiz", max_age=60*60*6, samesite="strict")
        resp.set_cookie("score_red", "0", path="/intfar/quiz", max_age=60*60*6, samesite="strict")
        used_quiz_categories.clear()

    return resp
