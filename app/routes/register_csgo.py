import flask

from app.util import make_template_context, get_user_details, discord_request, make_text_response

register_csgo_page = flask.Blueprint("register_csgo", __name__, template_folder="templates")

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

    existing_accounts_dict = database.users["csgo"].get(disc_id, {})
    existing_accounts_list = list(
        zip(
            existing_accounts_dict.get("steam_ids", []),
            existing_accounts_dict.get("steam_names", [])
        )
    )

    if flask.request.method == "POST":
        data = flask.request.form
        required_fields = ["steam_name", "steam_id", "match_auth_code"]
        for field in required_fields:
            if data.get(field, "") == "":
                return make_text_response(
                    f"Registration failed: Missing value for field '{field}'.",
                    400
                )
            
        

    return make_template_context("register_csgo.html", registered_accounts=existing_accounts_list)

