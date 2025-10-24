import flask
from intfar.app.util import get_hashed_secret, make_template_context

verify_page = flask.Blueprint("verify", __name__, template_folder="templates")

@verify_page.route("/<client_secret>")
def verify(client_secret):
    database = flask.current_app.config["DATABASE"]
    disc_id = database.get_user_from_secret(client_secret)

    resp = flask.make_response(make_template_context("verify.html", 200, disc_id=disc_id))
    hashed_secret = get_hashed_secret(client_secret)
    resp.set_cookie("user_id", hashed_secret, max_age=60*60*24*365*2)
    return resp
