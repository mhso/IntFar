import flask

from app.util import make_template_context, get_user_details
lists_page = flask.Blueprint("lists", __name__, template_folder="templates")

@lists_page.route('/')
def home(error_msg=None, status=200):
    return make_template_context("lists.html", status, error=error_msg)

@lists_page.route("/create", methods=["POST"])
def create():
    database = flask.current_app.config["DATABASE"]
    data = flask.request.form

    logged_in_user = get_user_details()[0]
    if logged_in_user is None: # Not logged in.
        error_msg = "You must be logged in to create a list."
        return home(error_msg, 401)

    max_list_len = 32
    error = None
    if "name" not in data or not data["name"]:
        error = "List name is empty"
    if len(data["name"]) > max_list_len:
        error = f"List name is too long (max {max_list_len} characters)"

    if error is not None:
        return home(f"List could not be created: {error}.", 400)

    list_id = database.create_list(logged_in_user, data["name"])

    return flask.redirect(flask.url_for("list.list_view", list_id=list_id))

def order_list_items(items): # Sort items alphabetically.
    items.sort(key=lambda x: x[1])

@lists_page.route("/<list_id>")
def list_view(list_id, error_msg=None):
    database = flask.current_app.config["DATABASE"]

    list_id = int(list_id)

    logged_in_user = get_user_details(database)[0]

    if logged_in_user is None: # Return template with no user_id (unauthorized).
        return make_template_context("list_view.html", 401, error="You are not logged in.")

    list_data = database.get_list_data(list_id)

    if list_data is None:
        # List does not exist, or list is not owned by user.
        return make_template_context("list_view.html", 400, error="List with that ID does not exist.")

    list_name = list_data[0]
    list_items = database.get_list_items(list_id)

    order_list_items(list_items)

    return make_template_context(
        "list_view.html", list_items=list_items, list_id=list_id,
        list_name=list_name, error=error_msg
    )
