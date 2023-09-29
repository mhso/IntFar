import flask

from api.register import register_for_game
from app.util import make_template_context, get_user_details, make_text_response

register_cs2_page = flask.Blueprint("register_cs2_page", __name__, template_folder="templates")

@register_cs2_page.route('/', methods=["GET", "POST"])
def home():
    disc_id = get_user_details()[0]
    database = flask.current_app.config["DATABASE"]

    if disc_id is None: # Not logged in
        err_msg = "You must be verified with Int-Far to register for CS2."
        status = 401

        if flask.request.method == "POST":
            return make_text_response(err_msg, status)

        return make_template_context(
            "register_cs2.html",
            status,
            error=err_msg
        )

    existing_accounts_dict = database.users_by_game["cs2"].get(disc_id, {})
    existing_accounts_list = list(
        zip(
            existing_accounts_dict.get("steam_ids", []),
            existing_accounts_dict.get("steam_names", [])
        )
    )

    if flask.request.method == "POST":
        data = flask.request.form
        required_fields = ["steam_id", "match_token", "match_auth_code"]
        for field in required_fields:
            if data.get(field, "") == "":
                return make_text_response(
                    f"Registration failed: Missing value for field '{field}'.",
                    400
                )

        api_client = flask.current_app.config["GAME_API_CLIENTS"]["cs2"]
        steam_id = int(data["steam_id"])
        match_token = data["match_token"]
        match_auth_code = data["match_auth_code"]

        status_code, status_msg = register_for_game(database, api_client, disc_id, steam_id, match_auth_code, match_token)

        return make_template_context(
            "register_cs2.html",
            200 if status_code else 400,
            register_status=status_code,
            register_msg=status_msg,
        )

    return make_template_context("register_cs2.html", registered_accounts=existing_accounts_list)
