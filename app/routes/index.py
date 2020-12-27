from datetime import datetime
import flask
from api.util import MONTH_NAMES
from app.util import get_discord_data
from app.user import get_user_details

start_page = flask.Blueprint("index", __name__, template_folder="templates")

@start_page.route('/')
@start_page.route('/index')
def index():
    database = flask.current_app.config["DATABASE"]
    bot_conn = flask.current_app.config["BOT_CONN"]
    curr_month = MONTH_NAMES[datetime.now().month-1]

    intfar_all_data = []
    intfar_month_data = []
    for disc_id, _, _ in database.summoners:
        games_played, intfar_reason_ids = database.get_intfar_stats(disc_id)
        games_played_monthly, intfar_reason_ids_monthly = database.get_intfar_stats(disc_id, True)
        pct_intfar = (0 if games_played == 0
                      else int(len(intfar_reason_ids) / games_played * 100))
        pct_intfar_monthly = (0 if games_played_monthly == 0
                              else int(len(intfar_reason_ids_monthly) / games_played_monthly * 100))

        intfar_all_data.append(
            (games_played, len(intfar_reason_ids), pct_intfar)
        )
        intfar_month_data.append(
            (games_played_monthly, len(intfar_reason_ids_monthly), pct_intfar_monthly)
        )

    avatars = get_discord_data(bot_conn, "func", "get_discord_avatar", None)
    if avatars is not None:
        avatars = [
            flask.url_for("static", filename=avatar.replace("app/static/", ""))
            for avatar in avatars
        ]
    nicknames = get_discord_data(bot_conn, "func", "get_discord_nick", None)

    intfar_all_data = [
        (x,) + y + (z,)
        for (x, y, z) in zip(nicknames, intfar_all_data, avatars)
    ]
    intfar_month_data = [
        (x,) + y + (z,)
        for (x, y, z) in zip(nicknames, intfar_month_data, avatars)
    ]

    intfar_all_data.sort(key=lambda x: (x[2], x[3]), reverse=True)
    intfar_month_data.sort(key=lambda x: (x[2], x[3]), reverse=True)

    logged_in_user, logged_in_name, logged_in_avatar = get_user_details()

    return flask.render_template(
        "index.html", curr_month=curr_month,
        intfar_all=intfar_all_data, intfar_month=intfar_month_data,
        logged_in_user=logged_in_user, logged_in_name=logged_in_name,
        logged_in_avatar=logged_in_avatar
    )
