import flask
import app.util as app_util
import api.util as api_util
import discbot.commands.util as commands_util

about_page = flask.Blueprint("about", __name__, template_folder="templates")

@about_page.route('/')
def home():
    database = flask.current_app.config["DATABASE"]

    (
        games, earliest_game, games_won, unique_game_guilds,
        longest_game_duration, longest_game_time, users,
        doinks_games, total_doinks, intfars, games_ratios,
        intfar_ratios, intfar_multi_ratios
    ) = database.get_meta_stats("lol")

    logged_in_user = app_util.get_user_details()[0]

    guilds_for_user = None
    if logged_in_user is not None:
       guilds_for_user = app_util.discord_request("func", "get_guilds_for_user", logged_in_user)

    commands = []
    for cmd in commands_util.COMMANDS:
        cmd_obj = commands_util.COMMANDS[cmd]
        if (
            (guilds_for_user is None and cmd_obj.guilds == api_util.GUILD_IDS) or
            (guilds_for_user is not None and any(guild in cmd_obj.guilds for guild in guilds_for_user))
        ):
            commands.append((cmd_obj, cmd_obj.desc))

    return app_util.make_template_context(
        "about.html",
        200,
        games=games,
        players=users,
        active_guilds=unique_game_guilds,
        commands=commands
    )
