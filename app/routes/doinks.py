import flask
from app.util import make_template_context
from api.util import DOINKS_REASONS

doinks_page = flask.Blueprint("doinks", __name__, template_folder="templates")

def get_doinks_awards(database):
    doinks = database.get_doinks_stats()
    doinks_reason_counts = [0 for _ in DOINKS_REASONS]
    doinks_counts = [0 for _ in DOINKS_REASONS]
    for doinks_str in doinks:
        doinks_indices = list(
            filter(
                lambda z: z is not None, map(
                    lambda y: y[0] if y[1] == "1" else None, enumerate(doinks_str[0])
                )
            )
        )
        for index in doinks_indices:
            doinks_reason_counts[index] += 1
        doinks_counts[len(doinks_indices)-1] += 1

    doinks_data = []
    for index, doinks_reason in enumerate(DOINKS_REASONS):
        doinks_data.append((doinks_reason, doinks_reason_counts[index]))

    return doinks_data, doinks_counts

@doinks_page.route('/')
def home():
    database = flask.current_app.config["DATABASE"]
    doinks_data, doinks_counts = get_doinks_awards(database)
    return make_template_context(
        "doinks.html", doinks_data=doinks_data, doinks_counts=doinks_counts
    )
