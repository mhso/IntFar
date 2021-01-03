import flask
from api.util import current_month
from app.util import discord_request
from app.user import get_user_details

user_page = flask.Blueprint("users", __name__, template_folder="templates")

@user_page.route("/")
@user_page.route("/unknown")
def user_unknown():
    return flask.render_template("no_user.html")

def get_relations_data(disc_id, bot_conn, database):
    relations_data = []
    games_relations, intfars_relations = database.get_intfar_relations(disc_id)
    for discord_id, total_games in games_relations.items():
        intfars = intfars_relations.get(discord_id, 0)
        relations_data.append((discord_id, total_games, intfars, int((intfars / total_games) * 100)))

    relations_data.sort(key=lambda x: x[2], reverse=True)

    avatars = discord_request(bot_conn, "func", "get_discord_avatar", [x[0] for x in relations_data])
    avatars = [
        flask.url_for("static", filename=avatar.replace("app/static/", ""))
        for avatar in avatars
    ]
    nicknames = discord_request(bot_conn, "func", "get_discord_nick", [x[0] for x in relations_data])

    return [
        (x,) + y + (z,)
        for (x, y, z) in zip(nicknames, relations_data, avatars)
    ]

def get_intfar_data(disc_id, monthly, database):
    games_played, intfar_reason_ids = database.get_intfar_stats(disc_id, monthly)
    pct_intfar = (0 if games_played == 0
                  else int(len(intfar_reason_ids) / games_played * 100))
    return games_played, len(intfar_reason_ids), pct_intfar

@user_page.route("/<disc_id>")
def user(disc_id):
    if disc_id == "None":
        return flask.render_template("no_user.html")
    database = flask.current_app.config["DATABASE"]
    bot_conn = flask.current_app.config["BOT_CONN"]

    discord_data = discord_request(bot_conn, "func", ["get_discord_nick", "get_discord_avatar"], disc_id)
    nickname = discord_data[0]
    avatar = discord_data[1]
    if avatar is not None:
        avatar = flask.url_for("static", filename=avatar.replace("app/static/", ""))

    curr_month = current_month()
    games_all, intfars_all, pct_all = get_intfar_data(disc_id, False, database)
    games_month, intfars_month, pct_month = get_intfar_data(disc_id, True, database)

    intfar_relation_data = get_relations_data(disc_id, bot_conn, database)

    logged_in_user, logged_in_name, logged_in_avatar = get_user_details()

    return flask.render_template(
        "profile.html", disc_id=disc_id, nickname=nickname, avatar=avatar,
        relations=intfar_relation_data, curr_month=curr_month,
        intfar_data_all=[games_all, intfars_all, pct_all],
        intfar_data_month=[games_month, intfars_month, pct_month],
        logged_in_user=logged_in_user, logged_in_name=logged_in_name,
        logged_in_avatar=logged_in_avatar
    )
