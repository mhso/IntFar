from datetime import datetime
from time import time

import flask

import app.util as app_util
import api.util as api_util
import api.lan as lan_api

lan_page = flask.Blueprint("lan", __name__, template_folder="templates")

def get_champ_faces(users_in_game, face_images):
    portrait_width = 308
    portrait_height = 560

    with open("app/static/img/champions/face_boxes.txt") as fp:
        all_coords = fp.readlines()
        coords_map = {}
        for line in all_coords:
            stripped = line.strip()
            if stripped == "":
                continue
            split_1 = stripped.split(":")
            champ_id = int(split_1[0].strip())
            coords = [int(c) for c in split_1[1].strip().split(",")]
            coords_map[champ_id] = coords

        image_data = []
        for user_data in users_in_game:
            disc_id = user_data[0]
            champ_id = user_data[-1]

            face_img = face_images[disc_id]
            coords = coords_map[champ_id]

            x, y = coords[0], coords[1]
            width = coords[2] - x
            x_pct = int((coords[0] / portrait_width) * 100)
            width_pct = int((width / portrait_width) * 100)
            height = coords[3] - y
            y_pct = int((coords[1] / portrait_height) * 100)
            height_pct = int((height / portrait_height) * 100)

            image_data.append((face_img, x_pct, y_pct, width_pct, height_pct))

        return image_data

def get_test_active_data():
    # Use dummy file to control whether a game is active.
    with open("dummy.txt", "r") as fp:
        if fp.readline().strip() in ("0", "2"):
            return {"active_game": None}

    active_game = "CLASSIC"
    enemy_champs = [15, 421, 45, 10, 432]
    users_in_game = [
        (172757468814770176, 223),
        (235831136733888512, 35),
        (267401734513491969, 517),
        (115142485579137029, 221),
        (331082926475182081, 888)
    ]
    game_prediction = 53
    blue_side = True

    return {
        "users_in_game": users_in_game, "enemy_champs": enemy_champs,
        "chance_to_win": game_prediction, "blue_side": blue_side,
        "active_game": active_game
    }

def get_real_active_data(lan_info):
    curr_time = time()
    if not lan_api.is_lan_ongoing(curr_time):
        return {"active_game": None}

    game_data = app_util.discord_request(
        "func", ["get_users_in_game", "get_active_game", "get_ai_prediction"], lan_info.guild_id
    )

    if game_data[0] is None:
        return {"active_game": None}

    users_in_game = game_data[0]
    active_game_data = game_data[1]
    game_prediction = game_data[2]
    enemy_champs = active_game_data["enemy_champ_ids"]

    active_game = active_game_data["game_mode"]
    blue_side = active_game_data["team_id"] == 100

    return {
        "users_in_game": users_in_game, "enemy_champs": enemy_champs,
        "chance_to_win": game_prediction, "blue_side": blue_side,
        "active_game": active_game
    }

def get_active_game_data(face_images, lan_info):
    riot_api = flask.current_app.config["RIOT_API"]

    if lan_api.TESTING:
        game_data = get_test_active_data()
    else:
        game_data = get_real_active_data(lan_info)

    if game_data["active_game"] is None:
        return game_data

    champ_faces = get_champ_faces(game_data["users_in_game"], face_images)

    our_champs_imgs = [
        (flask.url_for("static", filename=riot_api.get_champ_splash_path(user_data[-1]).replace("app/static/", "")),) + face_data
        for user_data, face_data in zip(game_data["users_in_game"], champ_faces)
    ]
    enemy_champs_imgs = [
        (flask.url_for("static", filename=riot_api.get_champ_splash_path(champ_id).replace("app/static/", "")),) + face_data
        for champ_id, face_data in zip(game_data["enemy_champs"], champ_faces)
    ]

    champ_splashes = [(our_champs_imgs, True), (enemy_champs_imgs, False)]
    if not game_data["blue_side"]:
        champ_splashes.reverse()

    game_data["champ_splashes"] = champ_splashes

    return game_data

def get_data(lan_info):
    database = flask.current_app.config["DATABASE"]
    riot_api = flask.current_app.config["RIOT_API"]

    games_stats = database.get_games_results(
        time_after=lan_info.start_time,
        time_before=lan_info.end_time,
        guild_id=lan_info.guild_id
    )
    if lan_api.TESTING:
        with open("dummy.txt", "r") as fp:
            if fp.readline().strip() in ("0", "1"):
                games_stats = None

    names = ["david", "martin", "mikkel", "mads", "anton"]

    face_images = {
        disc_id: flask.url_for("static", filename=f"img/lan_{name}.png")
        for disc_id, name in zip(lan_info.participants, names)
    }

    data = get_active_game_data(face_images, lan_info)
    lan_over = False

    if games_stats != [] and games_stats[0][1] is not None:
        # Games played and won.
        game_results = [win for win, _ in games_stats]
        games_played = len(games_stats)
        games_won = len(list(filter(None, game_results)))
        first_game_timestamp = games_stats[0][1]
        games_lost = games_played - games_won
        pct_won = (games_won / games_played) * 100

        champs_played = database.get_champs_played(
            time_after=lan_info.start_time,
            time_before=lan_info.end_time,
            guild_id=lan_info.guild_id
        )

        dt_start = datetime.fromtimestamp(first_game_timestamp)
        dt_now = datetime.now()
        if dt_now.timestamp() > lan_info.end_time:
            dt_now = datetime.fromtimestamp(lan_info.end_time)
            if not lan_api.TESTING:
                lan_over = True

        duration_since_start = api_util.format_duration(dt_start, dt_now)

        longest_game_duration, longest_game_time = database.get_longest_game(
            time_after=lan_info.start_time,
            time_before=lan_info.end_time,
            guild_id=lan_info.guild_id
        )
        longest_game_start = datetime.fromtimestamp(longest_game_time)
        longest_game_end = datetime.fromtimestamp(longest_game_time + longest_game_duration)
        longest_game = api_util.format_duration(longest_game_start, longest_game_end)

        # Latest game.
        latest_game_data, latest_doinks_data = database.get_latest_game(
            time_after=lan_info.start_time,
            time_before=lan_info.end_time,
            guild_id=lan_info.guild_id
        )
        latest_timestamp, latest_win, latest_intfar_id, latest_intfar_reason = latest_game_data

        dt_start = datetime.fromtimestamp(latest_timestamp)
        dt_now = datetime.now()
        duration_since_game = api_util.format_duration(dt_start, dt_now)

        # Int-Far from latest game.
        latest_intfar_name = None
        if latest_intfar_id is not None:
            latest_intfar_name = app_util.discord_request("func", "get_discord_nick", latest_intfar_id)
            latest_intfar_reason = api_util.INTFAR_REASONS[latest_intfar_reason.index("1")]

        # Doinks from latest game.
        latest_doinks = []
        if latest_doinks_data is not None:
            doinks_names = app_util.discord_request("func", "get_discord_nick", [x[1] for x in latest_doinks_data])
            for doinks_name, doinks_data in zip(doinks_names, latest_doinks_data):
                doinks_reason = ""
                any_doinks = False
                for index, reason in enumerate(api_util.DOINKS_REASONS):
                    if doinks_data[2][index] == "1":
                        if any_doinks:
                            doinks_reason += " and "
                        doinks_reason += reason

                latest_doinks.append((doinks_name, doinks_reason))

        # Int-Far and Doinks in total.
        intfars = database.get_intfar_count(
            time_after=lan_info.start_time,
            time_before=lan_info.end_time,
            guild_id=lan_info.guild_id
        )
        doinks = database.get_doinks_count(
            time_after=lan_info.start_time,
            time_before=lan_info.end_time,
            guild_id=lan_info.guild_id
        )[1]

        # Performance of all players.
        all_avg_stats, all_ranks = lan_api.get_average_stats(database, lan_info)

        # Get average stat value for each player.
        all_player_stats = {}
        for stat in all_avg_stats:
            for disc_id, avg_value in all_avg_stats[stat]:
                if disc_id not in all_player_stats:
                    all_player_stats[disc_id] = []

                fmt_value = str(int(avg_value)) if stat in ("Damage to champs", "Gold earned") else f"{avg_value:.2f}"
                if stat == "KP":
                    fmt_value += "%"

                all_player_stats[disc_id].append(fmt_value)

        # Get total rank for each player.
        all_player_ranks = {}
        for disc_id in lan_info.participants:
            player_rank = 0
            for index, rank_info in enumerate(all_ranks):
                if rank_info[0] == disc_id:
                    player_rank = index
                    break
            all_player_ranks[disc_id] = player_rank

        # Organize and sort stats by total rank.
        all_player_stats = [
            (
                all_player_ranks[disc_id], face_images[disc_id], all_player_stats[disc_id]
            ) for disc_id in all_player_stats
        ]
        all_player_stats.sort(key=lambda x: x[0])
        all_player_stats = [x[1:] for x in all_player_stats]
        stat_names = [stat for stat in all_avg_stats]

        # TILT VALUE!!
        recent_games = database.get_recent_game_results(
            time_after=lan_info.start_time,
            time_before=lan_info.end_time,
            guild_id=lan_info.guild_id
        )
        tilt_value, tilt_color = lan_api.get_tilt_value(recent_games)

        # Team Comp ideas
        with open("resources/team_comps.txt") as fp:
            team_comps = []
            for line in fp.readlines():
                split_1 = line.strip().split(":")
                name = split_1[0].strip()
                portraits = []
                for champ_name in split_1[1].split(","):
                    stripped = champ_name.strip()
                    if stripped == "_":
                        img_name = "img/any_champ.png"
                    else:
                        champ_id = riot_api.try_find_champ(stripped)
                        img_name = riot_api.get_champ_portrait_path(champ_id).replace("app/static/", "")

                    portraits.append(flask.url_for("static", filename=img_name))

                team_comps.append((name, portraits))

        game_data = {
            "games_played": games_played, "games_won": games_won, "games_lost": games_lost,
            "game_results": game_results, "pct_won": f"{pct_won:.2f}", "intfars": intfars,
            "champs_played": champs_played, "doinks": doinks, "duration_since_start": duration_since_start,
            "lan_over": lan_over, "all_player_stats": all_player_stats, "stat_names": stat_names,
            "duration_since_game": duration_since_game, "latest_win": latest_win,
            "latest_intfar_name": latest_intfar_name, "longest_game": longest_game,
            "latest_intfar_reason": latest_intfar_reason, "latest_doinks": latest_doinks,
            "tilt_value": tilt_value, "tilt_color": tilt_color, "team_comps": team_comps
        }
        data.update(game_data)
    else:
        data["games_played"] = None
        data["lan_over"] = False

    return data

@lan_page.route('/')
def lan_view():
    # Display view for latest LAN party.
    latest_lan_date = max(
        lan_api.LAN_PARTIES,
        key=lambda date: lan_api.LAN_PARTIES[date].end_time,
    )

    return flask.redirect(
        flask.url_for("lan.lan_view_for_date", date=latest_lan_date)
    )

@lan_page.route('/<date>')
def lan_view_for_date(date):
    lan_info = lan_api.LAN_PARTIES.get(date)
    logged_in_user = app_util.get_user_details()[0]

    if lan_info is None or logged_in_user is None or logged_in_user not in lan_info.participants:
        return flask.abort(404) # User not logged in or not a part of the LAN.

    data = get_data(lan_info)

    lan_dt = datetime.fromtimestamp(lan_info.start_time)

    data["lan_year"] = lan_dt.year
    month = api_util.MONTH_NAMES[lan_dt.month-1]
    data["lan_month"] = month
    data["lan_date"] = f"{month.lower()}_{str(lan_dt.year)[-2:]}"

    return app_util.make_template_context("lan.html", 200, **data)

@lan_page.route("/live_data/<date>", methods=["GET"])
def live_data(date):
    lan_info = lan_api.LAN_PARTIES.get(date)
    logged_in_user = app_util.get_user_details()[0]

    if lan_info is None or logged_in_user is None or logged_in_user not in lan_info.participants:
        return flask.abort(404) # User not logged in or not a part of the LAN.

    data = get_data(lan_info)

    return app_util.make_json_response(data, 200)