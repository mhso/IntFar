from flask import render_template, make_response

def handle_internal_error(e):
    return make_response(render_template("error.html", error_code=500), 500)

def handle_invalid_game_error(e):
    return make_response(render_template("error.html", error_code=400), 400)

def handle_missing_page_error(e):
    return make_response(render_template("error.html", error_code=404), 404)
