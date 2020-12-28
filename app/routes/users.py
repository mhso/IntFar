import flask
from app.util import get_discord_data
from app.user import get_user_details

user_page = flask.Blueprint("users", __name__, template_folder="templates")

@user_page.route("/")
@user_page.route("/unknown")
def user_unknown():
    return flask.render_template("no_user.html")

@user_page.route("/<disc_id>")
def user(disc_id):
    if disc_id == "None":
        return flask.render_template("no_user.html")
    database = flask.current_app.config["DATABASE"]
    bot_conn = flask.current_app.config["BOT_CONN"]

    discord_data = get_discord_data(bot_conn, "func", ["get_discord_nick", "get_discord_avatar"], disc_id)
    nickname = discord_data[0]
    avatar = discord_data[1]
    if avatar is not None:
        avatar = flask.url_for("static", filename=avatar.replace("app/static/", ""))

    relations_data = []
    games_relations, intfars_relations = database.get_intfar_relations(disc_id)
    for discord_id, total_games in games_relations.items():
        intfars = intfars_relations.get(discord_id, 0)
        relations_data.append((discord_id, total_games, intfars, int((intfars / total_games) * 100)))
    relations_data.sort(key=lambda x: x[2], reverse=True)

    logged_in_user, logged_in_name, logged_in_avatar = get_user_details()

    return flask.render_template(
        "profile.html", disc_id=disc_id, nickname=nickname, avatar=avatar,
        relations=relations_data, logged_in_user=logged_in_user,
        logged_in_name=logged_in_name, logged_in_avatar=logged_in_avatar
    )
