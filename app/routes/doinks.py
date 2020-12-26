import flask

doinks_page = flask.Blueprint("doinks", __name__, template_folder="templates")

@doinks_page.route('/')
def home():
    return flask.render_template("not_implemented.html")
