import flask
from app.util import make_template_context
from api.util import DOINKS_REASONS

doinks_page = flask.Blueprint("doinks", __name__, template_folder="templates")

def get_doinks_awards(database):
    doinks = database.get_doinks_stats()
    doinks_counts = [0 for _ in DOINKS_REASONS]
    doinks_data = []
    for doinks_str in doinks:
        for i, c in enumerate(doinks_str[0]):
            if c == "1":
                doinks_counts[i] += 1

    for index, doinks_reason in enumerate(DOINKS_REASONS):
        doinks_data.append((doinks_reason, doinks_counts[index]))

    return doinks_data

@doinks_page.route('/')
def home():
    database = flask.current_app.config["DATABASE"]
    doinks_data = get_doinks_awards(database)
    return make_template_context("doinks.html", doinks_data=doinks_data)
