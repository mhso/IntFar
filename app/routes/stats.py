import flask

stats_page = flask.Blueprint("stats", __name__, template_folder="templates")

@stats_page.route('/')
def home():
    return flask.render_template("not_implemented.html")
