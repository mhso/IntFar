from flask import Blueprint, render_template
from app.util import get_discord_data

user_page = Blueprint("users", __name__, template_folder="templates")

@user_page.route("/unknown")
def user_unknown():
    return render_template("no_user.html")

@user_page.route("/<disc_id>")
def user(disc_id):
    return render_template("not_implemented.html", disc_id=disc_id)
