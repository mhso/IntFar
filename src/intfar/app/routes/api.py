import flask
import traceback

from intfar.app import util as app_util

api_page = flask.Blueprint("api", __name__, template_folder="templates")

@api_page.route("/statistics", methods=["GET"])
def get_statistics():
    game = flask.current_app.config["CURRENT_GAME"]
    meta_database = flask.current_app.config["DATABASE"]
    game_database = flask.current_app.config["GAME_DATABASES"][game]

    # Get authorization values from URL parameters and user_id header.
    disc_id = int(flask.request.args.get("disc_id"))
    user_id = flask.request.headers.get("User-Id")

    if disc_id is None or app_util.get_logged_in_user(meta_database, user_id) != disc_id:
        return app_util.make_json_response(
            {"error": "You are not authorized to access this API."},
            http_code=403
        )

    try:
        with game_database:
            # Get active games, if any are ongoing.
            active_games = app_util.get_game_info(game)

            # Get total games played and won.
            games_played, _, _, _, games_won, _ = game_database.get_games_count()
            won_pct = float(f"{(games_won / games_played) * 100:.1f}")

            # Get total count of Int-Fars awarded.
            intfars_total = game_database.get_intfar_count()
            intfars_pct = float(f"{(intfars_total / games_played) * 100:.1f}")

            # Games where doinks were earned and total doinks earned.
            doinks_games, doinks_total = game_database.get_doinks_count()
            doinks_pct = float(f"{(doinks_games / games_played) * 100:.1f}")

            # Get Int-Far of the month leads.
            monthly_intfars = game_database.get_intfars_of_the_month()

        if monthly_intfars != []:
            tied_intfars = [monthly_intfars[0]]
            index = 1
            while index < len(monthly_intfars) and monthly_intfars[index][-1] == tied_intfars[index-1][-1]:
                tied_intfars.append(monthly_intfars[index])
                index += 1

            tied_intfars = [
                (app_util.discord_request("func", "get_discord_nick", disc_id), games, intfars, ratio)
                for (disc_id, games, intfars, ratio) in tied_intfars
            ]
        else:
            tied_intfars = []

        return app_util.make_json_response(
            {
                "games": [games_played, won_pct],
                "intfars": [intfars_total, intfars_pct],
                "doinks": [doinks_total, doinks_pct],
                "ifotm": [
                    {
                        "name": ifotm_name,
                        "games": ifotm_games,
                        "intfars": ifotm_intfars,
                        "percent": ifotm_pct
                    }
                    for ifotm_name, ifotm_games, ifotm_intfars, ifotm_pct in tied_intfars
                ],
                "active_games": [
                    {
                        "duration": info[0],
                        "mode": info[1],
                        "guild": info[2]
                    }
                    for info in active_games
                ]
            }
        )

    except Exception as e:
        traceback.print_exc()
        return app_util.make_json_response(
            {"error": f"Internal error during API call: {e.args[0]}"},
            http_code=500
        )
