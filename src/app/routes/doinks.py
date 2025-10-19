import flask
from app.util import make_template_context, discord_request
from api.awards import get_doinks_reasons

doinks_page = flask.Blueprint("doinks", __name__, template_folder="templates")

def get_doinks_awards(game, database):
    doinks_reasons_dict = get_doinks_reasons(game)
    doinks_reason_counts = [0 for _ in doinks_reasons_dict]
    doinks_counts = [0 for _ in doinks_reasons_dict]
    doinks_for_person = []

    avatars = discord_request(
        "func", "get_discord_avatar", None
    )
    avatars = {
        disc_id: flask.url_for("static", _external=True, filename=avatars[disc_id].replace("app/static/", ""))
        for disc_id in avatars
    }
    nicknames = discord_request(
        "func", "get_discord_nick", None
    )

    for disc_id in database.game_users.keys():
        doinks_reasons = database.get_doinks_stats(disc_id)
        total_doinks = database.get_doinks_count(disc_id)[1]
        unique_doinks = set()
        for doinks_str in doinks_reasons:
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

        doinks_for_person.append(
            (disc_id, nicknames[disc_id], avatars[disc_id], total_doinks, len(unique_doinks))
        )

    doinks_for_person.sort(key=lambda x: x[3], reverse=True)

    doinks_data = []
    for index, doinks_reason in enumerate(doinks_reasons_dict):
        doinks_data.append((doinks_reasons_dict[doinks_reason], doinks_reason_counts[index]))

    return doinks_data, doinks_counts, doinks_for_person

@doinks_page.route('/')
def home():
    game = flask.current_app.config["CURRENT_GAME"]
    database = flask.current_app.config["GAME_DATABASES"][game]

    doinks_data, doinks_counts, doinks_for_person = get_doinks_awards(game, database)
    return make_template_context(
        "doinks.html",
        doinks_data=doinks_data,
        doinks_counts=doinks_counts,
        doinks_persons=doinks_for_person
    )
