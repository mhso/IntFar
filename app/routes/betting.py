import flask
from app.util import get_discord_data
from api.bets import get_dynamic_bet_desc
from app.user import get_user_details

betting_page = flask.Blueprint("betting", __name__, template_folder="templates")

def get_bets(bot_conn, database, only_active):
    all_bets = database.get_active_bets() if only_active else database.get_all_bets()
    names = get_discord_data(bot_conn, "func", "get_discord_nick", None)
    avatars = get_discord_data(bot_conn, "func", "get_discord_avatar", None)
    avatars = [
        flask.url_for("static", filename=avatar.replace("app/static/", ""))
        for avatar in avatars
    ]
    names_dict = dict(zip((x[0] for x in database.summoners), names))
    avatar_dict = dict(zip((x[0] for x in database.summoners), avatars))
    presentable_data = []
    for disc_id in all_bets:
        bets = all_bets[disc_id]
        reformatted = [x + (None,) for x in bets] if only_active else bets
        for bet_id, amounts, events, targets, _, result_or_ticket, payout in reformatted:
            event_descs = [(get_dynamic_bet_desc(e, names_dict.get(t)), a) for (e, t, a) in zip(events, targets, amounts)]
            presentable_data.append(
                (bet_id, names_dict[disc_id], event_descs, result_or_ticket, payout, avatar_dict[disc_id])
            )
    presentable_data.sort(key=lambda x: x[0], reverse=True)
    return presentable_data

@betting_page.route('/')
def home():
    database = flask.current_app.config["DATABASE"]
    bot_conn = flask.current_app.config["BOT_CONN"]
    resolved_bets = get_bets(bot_conn, database, False)
    active_bets = get_bets(bot_conn, database, True)
    logged_in_user, logged_in_name, logged_in_avatar = get_user_details()

    return flask.render_template(
        "betting.html", resolved_bets=resolved_bets,
        active_bets=active_bets, logged_in_user=logged_in_user,
        logged_in_name=logged_in_name, logged_in_avatar=logged_in_avatar
    )
