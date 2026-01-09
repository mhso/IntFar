import flask
from intfar.app import util as app_util
from intfar.api import util as api_util
from run_discord_bot import initialize_commands
from intfar.discbot.commands import util as commands_util

about_page = flask.Blueprint("about", __name__, template_folder="templates")

@about_page.route('/')
def home():
    database = flask.current_app.config["GAME_DATABASES"]["lol"]

    (
        games, earliest_game, latest_game, game_time, games_won, unique_game_guilds,
        longest_game_duration, longest_game_time, users,
        doinks_games, total_doinks, intfars, games_ratios,
        intfar_ratios, intfar_multi_ratios
    ) = database.get_meta_stats()

    logged_in_user = app_util.get_user_details()[0]

    guilds_for_user = None
    if logged_in_user is not None:
       guilds_for_user = app_util.discord_request("func", "get_guilds_for_user", logged_in_user)

    if commands_util.COMMANDS == []:
        initialize_commands(flask.current_app.config["APP_CONFIG"])

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
