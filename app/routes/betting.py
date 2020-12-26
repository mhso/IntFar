import flask

betting_page = flask.Blueprint("betting", __name__, template_folder="templates")

@betting_page.route('/')
def home():
    return flask.render_template("not_implemented.html")
