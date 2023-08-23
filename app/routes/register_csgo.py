import flask

from api.register import register_for_game
from app.util import make_template_context, get_user_details, make_text_response

register_csgo_page = flask.Blueprint("register_csgo_page", __name__, template_folder="templates")

@register_csgo_page.route('/', methods=["GET", "POST"])
def home():
    disc_id = get_user_details()[0]
    database = flask.current_app.config["DATABASE"]

    if disc_id is None: # Not logged in
        err_msg = "You must be verified with Int-Far to register for CSGO."
        status = 401

        if flask.request.method == "POST":
            return make_text_response(err_msg, status)

        return make_template_context(
            "register_csgo.html",
            status,
            error=err_msg
        )

    existing_accounts_dict = database.users_by_game["csgo"].get(disc_id, {})
    existing_accounts_list = list(
        zip(
            existing_accounts_dict.get("steam_ids", []),
            existing_accounts_dict.get("steam_names", [])
        )
    )

    if flask.request.method == "POST":
        data = flask.request.form
        required_fields = ["steam_id", "match_auth_code"]
        for field in required_fields:
            if data.get(field, "") == "":
                return make_text_response(
                    f"Registration failed: Missing value for field '{field}'.",
                    400
                )

        api_client = flask.current_app.config["GAME_API_CLIENTS"]["csgo"]
        steam_id = data["steam_id"]
        match_auth_code = data["match_auth_code"]

        status_code, status_msg = register_for_game(database, api_client, disc_id, steam_id, match_auth_code)

        status_code = 200 if status_code else 400

        friend_request_sent = status_code == 1

        return make_template_context(
            "register_csgo.html",
            status_code,
            error=status_code == 0,
            register_msg=status_msg,
            friend_request_sent=friend_request_sent
        )

    return make_template_context("register_csgo.html", registered_accounts=existing_accounts_list)

