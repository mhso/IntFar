from app.routes.users import user
import flask
from app.util import make_template_context, discord_request
import api.util as api_util

stats_page = flask.Blueprint("stats", __name__, template_folder="templates")

def get_stats(database):
    all_stats = []
    for best in (True, False):
        stat_data = []
        for stat in api_util.STAT_COMMANDS:
            maximize = not ((stat != "deaths") ^ best)

            (best_or_worst_ever_id,
             best_or_worst_ever,
             _) = database.get_most_extreme_stat(stat, best, maximize)

            user_data = discord_request(
                "func", ["get_discord_nick", "get_discord_avatar"],
                best_or_worst_ever_id
            )

            pretty_stat = stat.replace("_", " ").capitalize() if len(stat) > 3 else stat.upper()
            stat_index = api_util.STAT_COMMANDS.index(stat)
            quantity_type = 0 if best else 1
            pretty_quantity = api_util.STAT_QUANTITY_DESC[stat_index][quantity_type].capitalize()
            pretty_desc = f"{pretty_quantity} {pretty_stat}"

            stat_data.append(
                (
                    pretty_desc, api_util.round_digits(best_or_worst_ever), user_data[0],
                    flask.url_for("static", filename=user_data[1].replace("app/static/", ""))
                )
            )
        all_stats.append(stat_data)
    return all_stats

@stats_page.route('/')
def home():
    database = flask.current_app.config["DATABASE"]
    stats_data = get_stats(database)
    return make_template_context("stats.html", stats_data=stats_data)
