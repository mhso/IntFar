from flask import Blueprint, render_template, current_app
from datetime import datetime
from api.util import MONTH_NAMES

start_page = Blueprint("index", __name__, template_folder="templates")

@start_page.route('/')
@start_page.route('/index')
def index():
    database = current_app.config["DATABASE"]
    bot_conn = current_app.config["BOT_CONN"]
    curr_month = MONTH_NAMES[datetime.now().month-1]

    intfar_all_data = []
    intfar_month_data = []
    for disc_id, _, _ in database.summoners:
        games_played, intfar_reason_ids = database.get_intfar_stats(disc_id)
        games_played_monthly, intfar_reason_ids_monthly = database.get_intfar_stats(disc_id, True)
        pct_intfar = (0 if games_played == 0
                      else int(len(intfar_reason_ids) / games_played * 100))
        pct_intfar_monthly = (0 if games_played == 0
                              else int(len(intfar_reason_ids) / games_played * 100))

        bot_conn.send(("func", "get_discord_avatar", disc_id))
        avatar = bot_conn.recv()

        intfar_all_data.append((games_played, len(intfar_reason_ids), pct_intfar))
        intfar_month_data.append(
            (games_played_monthly, len(intfar_reason_ids_monthly), pct_intfar_monthly)
        )

    return render_template(
        "index.html", curr_month=curr_month,
        intfar_all=intfar_all_data, intfar_month=intfar_month_data
    )
