import flask
from app.util import make_template_context, discord_request
from api.util import DOINKS_REASONS

doinks_page = flask.Blueprint("doinks", __name__, template_folder="templates")

def get_doinks_awards(database):
    doinks_reason_counts = [0 for _ in DOINKS_REASONS]
    doinks_counts = [0 for _ in DOINKS_REASONS]
    doinks_for_person = []

    avatars = discord_request(
        "func", "get_discord_avatar", None
    )
    avatars = [
        flask.url_for("static", filename=avatar.replace("app/static/", ""))
        for avatar in avatars
    ]
    nicknames = discord_request(
        "func", "get_discord_nick", None
    )

    for i, user_details in enumerate(database.summoners):
        doinks = database.get_doinks_stats(user_details[0])
        unique_doinks = set()
        for doinks_str in doinks:
            doinks_indices = list(
                filter(
                    lambda z: z is not None, map(
                        lambda y: y[0] if y[1] == "1" else None, enumerate(doinks_str[0])
                    )
                )
            )
            for index in doinks_indices:
                unique_doinks.add(index)
                doinks_reason_counts[index] += 1
            doinks_counts[len(doinks_indices)-1] += 1

        doinks_for_person.append((
            user_details[0], nicknames[i], avatars[i], len(doinks), len(unique_doinks)
        ))

    doinks_for_person.sort(key=lambda x: x[3], reverse=True)

    doinks_data = []
    for index, doinks_reason in enumerate(DOINKS_REASONS):
        doinks_data.append((doinks_reason, doinks_reason_counts[index]))

    return doinks_data, doinks_counts, doinks_for_person

@doinks_page.route('/')
def home():
    database = flask.current_app.config["DATABASE"]
    doinks_data, doinks_counts, doinks_for_person = get_doinks_awards(database)
    return make_template_context(
        "doinks.html", doinks_data=doinks_data, doinks_counts=doinks_counts,
        doinks_persons=doinks_for_person
    )
