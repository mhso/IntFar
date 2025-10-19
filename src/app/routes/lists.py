import flask

from api import lists
from app.util import make_template_context, get_user_details, discord_request, make_text_response

lists_page = flask.Blueprint("lists", __name__, template_folder="templates")

@lists_page.route('/')
def home(error_msg=None, status=200):
    database = flask.current_app.config["GAME_DATABASES"]["lol"]
    lists = database.get_lists()

    list_data = []
    for list_id, owner_id, list_name, list_count in lists:
        user_data = discord_request("func", ["get_discord_nick", "get_discord_avatar"],  owner_id)
        avatar = flask.url_for("static", _external=True, filename=user_data[1].replace("app/static/", ""))
        count_fmt = str(list_count) + (" champion" if list_count == 1 else " champions")
        list_data.append((list_id, list_name, owner_id, user_data[0], avatar, count_fmt))

    return make_template_context("lists.html", status, lists=list_data, error=error_msg)

@lists_page.route("/create", methods=["POST"])
def create():
    database = flask.current_app.config["GAME_DATABASES"]["lol"]
    data = flask.request.form

    logged_in_user = get_user_details()[0]
    if logged_in_user is None: # Not logged in.
        error_msg = "You must be logged in to create a list."
        return home(error_msg, 401)

    success, response = lists.create_list(logged_in_user, data.get("name"), database)

    if not success:
        return home(f"List could not be created: {response}.", 400)

    return flask.redirect(flask.url_for("lists.home", _external=True))

def order_list_items(items): # Sort items alphabetically.
    items.sort(key=lambda x: x[1])

@lists_page.route("/<list_id>")
def list_view(list_id, error_msg=None, status=200):
    database = flask.current_app.config["GAME_DATABASES"]["lol"]
    riot_api = flask.current_app.config["GAME_API_CLIENTS"]["lol"]

    list_id = int(list_id)

    logged_in_user = get_user_details()[0]

    list_data = database.get_list_data(list_id)

    if list_data is None:
        # List does not exist, or list is not owned by user.
        error = "List with that ID does not exist."
        return home(error, 404)

    list_name = list_data[0]
    list_owner = int(list_data[1])
    list_items = database.get_list_items(list_id)
    list_items = [
        (
            item_id, riot_api.get_champ_name(champ_id),
            flask.url_for(
                "static",
                _external=True,
                filename=riot_api.get_champ_portrait_path(champ_id).replace("app/static/", "")
            )
        ) for item_id, champ_id in list_items
    ]
    user_owns_list = logged_in_user == list_owner

    order_list_items(list_items)

    # Load champions that can be added to the list.
    all_champions = list(riot_api.champ_names.items())
    all_champions.sort(key= lambda x: x[1])

    return make_template_context(
        "list_view.html", status, list_items=list_items, list_id=list_id,
        list_name=list_name, user_owns_list=user_owns_list,
        champions=all_champions, error=error_msg
    )

@lists_page.route("/<list_id>/rename", methods=["POST"])
def rename(list_id):
    database = flask.current_app.config["GAME_DATABASES"]["lol"]
    data = flask.request.form

    list_id = int(list_id)

    logged_in_user = get_user_details()[0]
    if logged_in_user is None: # Not logged in.
        error_msg = "You must be logged in to rename a list."
        return make_text_response(error_msg, 401)

    success, response = lists.rename_list(logged_in_user, list_id, data.get("name"), database)

    if not success:
        return make_text_response(f"List could not be renamed: {response}.", 400)

    return make_text_response("success", 200)

@lists_page.route("/<list_id>/delete_list", methods=["POST"])
def delete_list(list_id):
    database = flask.current_app.config["GAME_DATABASES"]["lol"]

    list_id = int(list_id)

    logged_in_user = get_user_details()[0]
    if logged_in_user is None: # Not logged in.
        error_msg = "You must be logged in to delete a list."
        return home(error_msg, 401)

    success, response = lists.delete_list(logged_in_user, list_id, database)

    if not success:
        return home(f"List could not be deleted: {response}.", 401)

    return make_text_response("success", 200)

@lists_page.route("/<list_id>/add", methods=["POST"])
def add_item(list_id):
    database = flask.current_app.config["GAME_DATABASES"]["lol"]
    riot_api = flask.current_app.config["GAME_API_CLIENTS"]["lol"]
    data = flask.request.form

    list_id = int(list_id)

    logged_in_user = get_user_details()[0]
    if logged_in_user is None: # Not logged in.
        error_msg = "You must be logged in to add champions to a list."
        return home(error_msg, 401)

    success, response = lists.add_champ_to_list(
        logged_in_user, list_id, data.get("champion"), riot_api, database
    )

    if not success:
        return list_view(list_id, f"Could not add champion to list: {response}", 400)

    return flask.redirect(flask.url_for("lists.list_view", _external=True, list_id=list_id))

@lists_page.route("/<item_id>/delete_item", methods=["POST"])
def delete_item(item_id):
    database = flask.current_app.config["GAME_DATABASES"]["lol"]

    item_id = int(item_id)

    logged_in_user = get_user_details()[0]
    if logged_in_user is None: # Not logged in.
        error_msg = "You must be logged in to delete a list."
        return make_text_response(error_msg, 401)

    success, response = lists.delete_champ_from_list(logged_in_user, item_id, database)

    # No list exists that contains the given item id.
    if not success:
        return make_text_response(f"Can't delete champion: {response}.", 400)

    return make_text_response("success", 200)
