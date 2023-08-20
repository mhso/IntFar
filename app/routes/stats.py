import flask

from app.util import make_template_context, discord_request
import api.util as api_util
from api.game_data import get_stat_quantity_descriptions

stats_page = flask.Blueprint("stats", __name__, template_folder="templates")

def get_stats(game, database):
    all_stats = []
    stat_descs = get_stat_quantity_descriptions(game)
    for best in (True, False):
        stat_data = []
        for stat in stat_descs:
            maximize = not ((stat != "deaths") ^ best)

            (
                best_or_worst_ever_id,
                best_or_worst_ever,
                _
            ) = database.get_most_extreme_stat(game, stat, maximize)

            user_data = discord_request(
                "func", ["get_discord_nick", "get_discord_avatar"],
                best_or_worst_ever_id
            )

            pretty_stat = stat.replace("_", " ").capitalize() if len(stat) > 3 else stat.upper()
            quantity_type = 0 if best else 1
            pretty_quantity = stat_descs[stat][quantity_type]
            if stat == "first_blood":
                pretty_quantity = "most" if best else "least"
                pretty_stat += "s"
            pretty_desc = f"{pretty_quantity.capitalize()} {pretty_stat}"

            stat_data.append(
                (
                    best_or_worst_ever_id,
                    pretty_desc,
                    api_util.round_digits(best_or_worst_ever),
                    user_data[0],
                    flask.url_for("static", filename=user_data[1].replace("app/static/", ""))
                )
            )
        all_stats.append(stat_data)

    return all_stats

@stats_page.route('/')
def home():
    game = flask.current_app.config["CURRENT_GAME"]
    database = flask.current_app.config["DATABASE"]
    stats_data = get_stats(game, database)
    return make_template_context("stats.html", stats_data=stats_data)
