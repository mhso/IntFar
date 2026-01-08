from datetime import datetime
import random
from time import sleep, time

import flask
import numpy as np

from intfar.app import util as app_util
from intfar.api import util as api_util
from intfar.api import lan as lan_api
from intfar.api.game_apis.lol import RiotAPIClient
from intfar.api.game_databases.lol import LoLGameDatabase
from intfar.api.game_data import get_formatted_stat_names, get_formatted_stat_value
from intfar.api.awards import get_doinks_reasons, get_intfar_reasons
from intfar.api.user import User

lan_page = flask.Blueprint("lan", __name__, template_folder="templates")

_GAME = "lol"

def get_champ_faces(users_in_game, face_images, config):
    portrait_width = 308
    portrait_height = 560

    with open(f"{config.static_folder}/img/champions/face_boxes.txt") as fp:
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
        for disc_id in users_in_game:
            champ_id = users_in_game[disc_id]

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
    users_in_game = {
        115142485579137029: User(115142485579137029, champ_id=223),
        172757468814770176: User(172757468814770176, champ_id=35),
        267401734513491969: User(267401734513491969, champ_id=517),
        331082926475182081: User(331082926475182081, champ_id=221),
        347489125877809155: User(347489125877809155, champ_id=888),
    }
    blue_side = True

    return {
        "users_in_game": users_in_game,
        "enemy_champs": enemy_champs,
        "blue_side": blue_side,
        "active_game": active_game
    }

def get_real_active_data(riot_api: RiotAPIClient, lan_info: lan_api.LANInfo):
    curr_time = time()
    if not lan_api.is_lan_ongoing(curr_time, lan_info.guild_id):
        return {"active_game": None}

    game_start = flask.current_app.config["LEAGUE_GAME_START"]
    if game_start is None:
        return {"active_game": None}

    users_in_game = {
        int(disc_id): riot_api.try_find_playable_id(champ_name)
        for disc_id, champ_name in game_start["AllyTeamInfo"].items()
    }
    enemy_champs = [
        riot_api.try_find_playable_id(champ_name)
        for champ_name in game_start["EnemyTeamInfo"]
    ]

    active_game = game_start["GameMode"]
    blue_side = game_start["Team"] == "blue"

    return {
        "users_in_game": users_in_game,
        "enemy_champs": enemy_champs,
        "blue_side": blue_side,
        "active_game": active_game
    }

def get_active_game_data(face_images, lan_info):
    config = flask.current_app.config["APP_CONFIG"]
    riot_api = flask.current_app.config["GAME_API_CLIENTS"]["lol"]

    if lan_api.TESTING:
        game_data = get_test_active_data()
    else:
        game_data = get_real_active_data(riot_api, lan_info)

    if game_data["active_game"] is None:
        return game_data

    champ_faces = get_champ_faces(game_data["users_in_game"], face_images, config)

    our_champs_imgs = [
        (flask.url_for("static", _external=True, filename=app_util.get_relative_static_folder(riot_api.get_champ_splash_path(game_data["users_in_game"][disc_id]), config)),) + face_data
        for disc_id, face_data in zip(game_data["users_in_game"], champ_faces)
    ]
    enemy_champs_imgs = [
        (flask.url_for("static", _external=True, filename=app_util.get_relative_static_folder(riot_api.get_champ_splash_path(champ_id), config)),) + face_data
        for champ_id, face_data in zip(game_data["enemy_champs"], champ_faces)
    ]

    champ_splashes = [(our_champs_imgs, True), (enemy_champs_imgs, False)]
    if not game_data["blue_side"]:
        champ_splashes.reverse()

    game_data["champ_splashes"] = champ_splashes

    return game_data

def get_bingo_data(database, lan_date, face_images={}):
    bingo_challenges = lan_api.get_current_bingo_challenges(database, lan_date)

    if bingo_challenges == []:
        return []

    bingo_data = []
    curr_row = []
    for data in bingo_challenges:
        if data["completed_by"]:
            data["completed_by"] = face_images.get(data["completed_by"])

        if data["id"] == "bounty_gold":
            data["progress"] = int(data["progress"])

        curr_row.append(data)

        if len(curr_row) == lan_api.BINGO_WIDTH:
            bingo_data.append(curr_row)
            curr_row = []

    if lan_api.TESTING:
        bingo_data[0][0].update(progress=1, new_progress=True, completed=True) # Big lead
        bingo_data[0][3].update(progress=623_042) # Damage dealt
        bingo_data[0][4].update(progress=5, completed=True) # Dive kills
        bingo_data[1][0].update(progress=2, new_progress=True) # Big doinks
        bingo_data[1][1].update(progress=1, new_progress=True) # Dragon souls
        bingo_data[1][2].update(progress=1, completed=True) # Twenty min win
        bingo_data[2][0].update(progress=1, completed=True) # Flawless ace
        bingo_data[2][1].update(progress=1, completed=True, completed_by=face_images.get(331082926475182081)) # Fountain kill
        bingo_data[2][2].update(progress=5, completed=True) # Invade kills
        bingo_data[2][3].update(progress=1, completed=True, completed_by=face_images.get(115142485579137029)) # Jungle doinks
        bingo_data[2][4].update(progress=10, new_progress=True, completed=True) # Killing sprees
        bingo_data[3][0].update(progress=69, new_progress=True) # Kills
        bingo_data[3][3].update(progress=10, completed=True) # Solo kills
        bingo_data[4][3].update(progress=1, new_progress=True, completed=True) # Two barons
        bingo_data[4][4].update(progress=1, completed=True) # Won games

    completed_mask = np.zeros((lan_api.BINGO_WIDTH, lan_api.BINGO_WIDTH), np.uint8)
    for y in range(len(bingo_data)):
        for x in range(len(bingo_data[y])):
            if bingo_data[y][x]["completed"]:
                completed_mask[y, x] = 1

    # Check if there is bingo on descending diagonal
    diag_1 = np.identity(lan_api.BINGO_WIDTH)
    if np.count_nonzero(diag_1 * completed_mask) == lan_api.BINGO_WIDTH:
        for x, y in zip(*np.nonzero(diag_1)):
            bingo_data[y][x]["bingo"] = True

    # Check if there is bingo on ascending diagonal
    diag_2 = np.fliplr(diag_1)
    if np.count_nonzero(diag_2 * completed_mask) == lan_api.BINGO_WIDTH:
        for x, y in zip(*np.nonzero(diag_2)):
            bingo_data[y][x]["bingo"] = True

    # Check if there is bingo on a row
    for y in range(lan_api.BINGO_WIDTH):
        if all(completed_mask[y, :]):
            for data in bingo_data[y]:
                data["bingo"] = True

    # Check if there is bingo on a column
    for x in range(lan_api.BINGO_WIDTH):
        if all(completed_mask[:, x]):
            for row in bingo_data:
                row[x]["bingo"] = True

    return bingo_data

def get_data(lan_info, database, lan_date):
    config = flask.current_app.config["APP_CONFIG"]
    riot_api = flask.current_app.config["GAME_API_CLIENTS"]["lol"]

    try:
        games_stats = database.get_games_results(
            time_after=lan_info.start_time,
            time_before=lan_info.end_time,
            guild_id=lan_info.guild_id
        )
    except Exception:
        sleep(1)
        games_stats = database.get_games_results(
            time_after=lan_info.start_time,
            time_before=lan_info.end_time,
            guild_id=lan_info.guild_id
        )

    if lan_api.TESTING:
        with open("dummy.txt", "r") as fp:
            if fp.readline().strip() in ("0", "1"):
                games_stats = []

    face_images = {
        disc_id: flask.url_for("static", _external=True, filename=f"img/lan_{lan_info.participants[disc_id].lower()}.png")
        for disc_id in lan_info.participants
    }

    data = get_active_game_data(face_images, lan_info)
    lan_over = False

    if games_stats != [] and games_stats[0][1] is not None:
        # Games played and won.
        game_results = [win for win, _ in games_stats]
        games_played = len(games_stats)
        games_won = len(list(filter(lambda x: x == 1, game_results)))
        first_game_timestamp = games_stats[0][1]
        games_lost = games_played - games_won
        pct_won = (games_won / games_played) * 100

        champs_played = len(
            database.get_played_ids(
                time_after=lan_info.start_time,
                time_before=lan_info.end_time,
                guild_id=lan_info.guild_id
            )
        )

        dt_start = datetime.fromtimestamp(first_game_timestamp)
        dt_now = datetime.now()
        if dt_now.timestamp() > lan_info.end_time and not lan_api.TESTING:
            dt_now = datetime.fromtimestamp(lan_info.end_time)
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
        _, latest_timestamp, _, latest_win, latest_intfar_id, latest_intfar_reason = latest_game_data

        dt_start = datetime.fromtimestamp(latest_timestamp)
        duration_since_game = api_util.format_duration(dt_start, dt_now)

        # Int-Far from latest game.
        intfar_reasons = get_intfar_reasons(_GAME)
        latest_intfar_name = None
        if latest_intfar_id is not None:
            latest_intfar_name = app_util.discord_request("func", "get_discord_nick", latest_intfar_id)
            latest_intfar_reason = list(intfar_reasons.values())[latest_intfar_reason.index("1")]

        # Doinks from latest game.
        doinks_reasons = get_doinks_reasons(_GAME)
        latest_doinks = []
        if latest_doinks_data is not None:
            doinks_names = app_util.discord_request("func", "get_discord_nick", [x[1] for x in latest_doinks_data])
            for doinks_name, doinks_data in zip(doinks_names, latest_doinks_data):
                doinks_reason = ""
                any_doinks = False
                for index, reason in enumerate(doinks_reasons.values()):
                    if doinks_data[2][index] == "1":
                        if any_doinks:
                            doinks_reason += " and "
                        doinks_reason += reason
                        any_doinks = True

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
        all_avg_stats = lan_api.get_average_stats(database, lan_info)

        # Get average stat value for each player.
        all_player_stats = {}
        for stat in all_avg_stats:
            for disc_id, avg_value in all_avg_stats[stat]:
                if disc_id not in all_player_stats:
                    all_player_stats[disc_id] = []

                fmt_value = get_formatted_stat_value(_GAME, stat, avg_value)

                all_player_stats[disc_id].append(fmt_value)

        # Get total rank for each player
        performance_scores = database.get_performance_score(time_after=lan_info.start_time, time_before=lan_info.end_time, minimum_games=1)()
        all_player_ranks = {}
        for disc_id in lan_info.participants:
            player_score = 5
            for score_id, score in performance_scores:
                if score_id == disc_id:
                    player_score = score
                    break

            all_player_ranks[disc_id] = float(f"{player_score:.2f}")

        # Organize and sort stats by total rank.
        all_player_stats = [
            (
                all_player_ranks[disc_id],
                face_images[disc_id],
                all_player_stats[disc_id]
            ) for disc_id in all_player_stats
        ]
        all_player_stats.sort(key=lambda x: x[0], reverse=True)
        formatted_stat_names_dict = get_formatted_stat_names(_GAME)
        stat_names = ["Score"] + [
            formatted_stat_names_dict[stat]
            for stat in all_avg_stats
        ]

        # TILT VALUE!!
        recent_games = database.get_games_results(
            False,
            time_after=lan_info.start_time,
            time_before=lan_info.end_time,
            guild_id=lan_info.guild_id
        )
        tilt_value, tilt_color = lan_api.get_tilt_value([x[0] for x in recent_games])

        # Team Comp ideas
        with open(f"{config.resources_folder}/team_comps.txt") as fp:
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
                        champ_id = riot_api.try_find_playable_id(stripped)
                        img_name = app_util.get_relative_static_folder(riot_api.get_champ_portrait_path(champ_id), config)

                    portraits.append(flask.url_for("static", _external=True, filename=img_name))

                team_comps.append((name, portraits))

        game_data = {
            "games_played": games_played,
            "games_won": games_won,
            "games_lost": games_lost,
            "game_results": game_results,
            "pct_won": f"{pct_won:.2f}",
            "intfars": intfars,
            "champs_played": champs_played,
            "doinks": doinks,
            "duration_since_start": duration_since_start,
            "lan_over": lan_over,
            "all_player_stats": all_player_stats,
            "stat_names": stat_names,
            "duration_since_game": duration_since_game,
            "latest_win": latest_win,
            "latest_intfar_name": latest_intfar_name,
            "longest_game": longest_game,
            "latest_intfar_reason": latest_intfar_reason,
            "latest_doinks": latest_doinks,
            "tilt_value": tilt_value,
            "tilt_color": tilt_color,
            "team_comps": team_comps,
        }
        data.update(game_data)
    else:
        data["games_played"] = None
        data["lan_over"] = False

    data["bingo_challenges"] = get_bingo_data(database, lan_date, face_images)

    return data

def _allowed_access(lan_info, user_id):
    return lan_api.TESTING or (lan_info is not None and user_id is not None and user_id in lan_info.participants)

@lan_page.route('/')
def lan_view():
    # Display view for latest LAN party.
    return flask.redirect(
        flask.url_for("lan.lan_view_for_date", _external=True, date=lan_api.LATEST_LAN_PARTY)
    )

@lan_page.route('/<date>')
def lan_view_for_date(date):
    lan_info = lan_api.LAN_PARTIES.get(date)
    logged_in_user = app_util.get_user_details()[0]

    if not _allowed_access(lan_info, logged_in_user):
        return flask.abort(404) # User not logged in or not a part of the LAN.

    database: LoLGameDatabase = flask.current_app.config["GAME_DATABASES"]["lol"]
    with database:
        data = get_data(lan_info, database, date)

    # LAN Bingo!
    for bingo_row in data["bingo_challenges"]:
        for bingo_challenge in bingo_row:
            if bingo_challenge["new_progress"]:
                database.reset_bingo_new_progress(bingo_challenge["id"])

    # Check if bingo is completed
    bingo_completed = True
    for bingo_row in data["bingo_challenges"]:
        all_bingo = True
        for row_data in bingo_row:
            if not row_data["bingo"]:
                all_bingo = False
                break

        if not all_bingo:
            bingo_completed = False
            break

    data["bingo_completed"] = bingo_completed

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

    if not _allowed_access(lan_info, logged_in_user):
        return flask.abort(404) # User not logged in or not a part of the LAN.

    database: LoLGameDatabase = flask.current_app.config["GAME_DATABASES"]["lol"]
    with database:
        all_data = get_data(lan_info, database, date)

    data_filter = flask.request.args.get("filter")
    if data_filter is not None:
        keys_to_get = data_filter.split(",")

    if data_filter is None or ("bingo_challenges" in keys_to_get and "bingo_status" in keys_to_get):
        bingo_status = 0
        all_bingo = True
        with database:
            for bingo_row in all_data["bingo_challenges"]:
                for bingo_data in bingo_row:
                    if not bingo_data["bingo"]:
                        all_bingo = False
                        continue

                    if bingo_data["completed"] and not bingo_data["notification_sent"]:
                        database.set_bingo_challenge_seen(bingo_data["id"])
                        bingo_status = 1

        if all_bingo and bingo_status == 1:
            bingo_status = 2 # Full board cleared!

        all_data["bingo_status"] = bingo_status

    if data_filter is not None:
        data = {k: all_data[k] for k in keys_to_get} if data_filter is not None else data

    return app_util.make_json_response(
        {k: all_data[k] for k in keys_to_get} if data_filter is not None else data,
        200
    )

@lan_page.route("/jeopardy_winner", methods=["POST"])
def announce_jeopardy_winner():
    meta_database = flask.current_app.config["DATABASE"]
    disc_id = flask.request.json.get("disc_id")
    token = flask.request.json.get("token")

    if disc_id is None or token is None or app_util.get_logged_in_user(meta_database, token) != int(disc_id):
        return app_util.make_text_response("You are not authorized to access this API.", 403)

    guild_id = lan_api.get_latest_lan_info().guild_id

    player_data = flask.request.json["player_data"]

    if flask.current_app.config["APP_ENV"] == "production" and lan_api.is_lan_ongoing(time(), guild_id):
        app_util.discord_request("func", "announce_jeopardy_winner", (player_data, guild_id))

    return app_util.make_text_response("Successfully announced jeopardy winner for this LAN!", 200)

_EVENTS_KILLED_SYNONYMS = [
    "whacked",
    "murdered",
    "clapped",
    "killed",
    "bonked",
    "annihilated",
    "smacked",
    "blasted",
    "slaughtered",
]
_EVENTS_MULTIKILLS = ["sweet double kill", "spicy triple kill", "nasty quadrakill", "insane pentakill"]
_EVENTS_STREAKS = ["on a killing spree", "on a rampage", "unstoppable", "dominating", "godlike", "legendary"]
_EVENTS_DRAGON_NAMES = {
    "Earth": "Mountain",
    "Water": "Ocean",
    "Air": "Cloud",
    "Fire": "Infernal",
    "Chemtech": "Chemtech",
    "Hextech": "Hextech",
}

def _get_lol_event_description(event):
    desc = None
    icon = None

    if event["EventName"] == "GameEnd":
        category = "win" if event["Result"] == "Win" else "enemy"
    elif "Ally" in event:
        category = "ally" if event["Ally"] else "enemy"
    else:
        category = "neutral"

    if event["EventName"] == "GameStart":
        desc = "Let the games begin!"
        icon = "game_start.png"

    elif event["EventName"] == "GameEnd":
        desc = "Game over! "
        if event["Result"] == "Win":
            desc += "The bois claw home another victory!"
        else:
            desc += "We kinda inted that one :("

    elif event["EventName"] == "ChampionKill":
        killed = random.choice(_EVENTS_KILLED_SYNONYMS)
        desc = f"{event['KillerName']} {killed} {event['VictimName']}"

        if event.get("CurrentStreak", 1) > 2:
            streak = _EVENTS_STREAKS[min(event["CurrentStreak"], 8) - 3]
            desc += f" and is {streak}!"
            icon = "game_feed_spree.png"
        else:
            icon = "game_feed_kill.png"

    elif event["EventName"] == "Multikill":
        streak = _EVENTS_MULTIKILLS[event["KillStreak"] - 2]
        desc = f"{event['KillerName']} got a {streak}!"
        icon = "game_feed_multikill.png"

    elif event["EventName"] == "Shutdown":
        desc = f"{event['KillerName']} shut down {event['VictimName']}!"
        icon = "game_feed_kill.png"

    elif event["EventName"] == "Execute":
        desc = f"{event['VictimName']} just got executed, yikes"
        icon = "game_feed_execute.png"

    elif event["EventName"] == "Ace":
        if category == "ally":
            desc = "We aced the enemy team!"
        else:
            desc = "We got aced by the enemy team :("

        icon = "game_feed_kill.png"

    elif event["EventName"] == "FirstBlood":
        desc = f"{event['Recipient']} got first blood!"
        icon = "game_feed_kill.png"

    elif event["EventName"] == "FirstBrick":
        killer = "We" if category == "ally" else "Enemy team"
        desc = f"{killer} destroyed the first tower!"
        icon = "game_feed_turret.png"

    elif event["EventName"] in ("TurretKilled", "InhibKilled"):
        structure_name = "a turret" if event["EventName"] == "TurretKilled" else "an inhibitor!"

        if category == "ally":
            desc = f"We destroyed {structure_name}"
        else:
            desc = f"Enemy team destroyed {structure_name}"

        icon = "game_feed_turret.png"

    elif event["EventName"] in ("BaronKill", "HeraldKill", "AtakhanKill", "DragonKill"):
        if event["Stolen"] == "True":
            killed = "stole"
        else:
            killed = random.choice(_EVENTS_KILLED_SYNONYMS)

        if event["EventName"] == "DragonKill":
            monster_name = _EVENTS_DRAGON_NAMES.get(event["DragonType"], event["DragonType"])
            if "Soul" in event:
                monster_name += " Soul"
                if killed != "stole":
                    killed = "got"
            else:
                monster_name = f"the {monster_name} Dragon"

            if monster_name == "Elder":
                icon = "game_feed_elder.png"
            else:
                icon = "game_feed_dragon.png"

        elif event["EventName"] == "BaronKill":
            monster_name = "The Big Purple Worm"
            icon = "game_feed_baron.png"

        elif event["EventName"] == "HeraldKill":
            monster_name = "Shelly"
            icon = "game_feed_herald.png"

        elif event["EventName"] == "AtakhanKill":
            monster_name = "Akshan's Creepy Uncle"
            icon = "game_feed_atakhan.png"

        killer = "The brois" if category == "ally" else "Enemy team"

        desc = f"{killer} {killed} {monster_name}!"

    if icon is not None:
        icon = flask.url_for("static", filename=f"img/{icon}", _external=True)

    return {"description": desc, "category": category, "icon": icon}

@lan_page.route("/live_league_data", methods=["GET"])
def live_league_data():
    with flask.current_app.config["LEAGUE_EVENTS_LOCK"]:
        events = []
        for event in flask.current_app.config["LEAGUE_EVENTS"]:
            formatted = _get_lol_event_description(event)
            if formatted["description"] is None:
                continue

            events.append(formatted)

        flask.current_app.config["LEAGUE_EVENTS"] = []
        data = {"events": events}

    return app_util.make_json_response(data, 200)

@lan_page.route("/now_playing/<date>", methods=["GET", "POST"])
def now_playing(date):
    if flask.request.method == "POST":
        # Update the currently playing song
        data = flask.request.json
        conf = flask.current_app.config["APP_CONFIG"]

        secret = data.get("secret")
        lan_info = lan_api.LAN_PARTIES.get(date)

        if lan_info is None:
            return flask.abort(404) # LAN info not found

        if secret != conf.discord_token:
            return flask.abort(401) # User is not authorized

        song = data["song"]

        if song == "nothing":
            flask.current_app.config["NOW_PLAYING"] = None

        else:
            artist = data["artist"]
            flask.current_app.config["NOW_PLAYING"] = (song, artist)

        # Set live league data
        if data["lol_events"] != []:
            with flask.current_app.config["LEAGUE_EVENTS_LOCK"]:
                for event in data["lol_events"]:
                    if event["EventName"] == "GameStart":
                        flask.current_app.config["LEAGUE_GAME_START"] = event
                    elif event["EventName"] == "GameEnd":
                        flask.current_app.config["LEAGUE_GAME_START"] = None

                    flask.current_app.config["LEAGUE_EVENTS"].append(event)

        return flask.make_response(("Success! Song playing updated.", 200))

    # Return the currently playing song and artist (if any)
    data = flask.current_app.config["NOW_PLAYING"]
    if data is None:
        response_data = {"song": "Nada", "artist": "nothing"}
        return app_util.make_json_response(response_data, 200)

    song, artist = data
    response_data = {"song": song, "artist": artist}

    return app_util.make_json_response(response_data, 200)
