from flask import Blueprint, render_template

start_page = Blueprint("index", __name__, template_folder="templates")

@start_page.route('/')
@start_page.route('/index')
def index():
    return render_template("index.html")
