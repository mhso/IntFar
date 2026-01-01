import flask

from intfar.app import util as app_util

PLAYER_NAMES = {
    115142485579137029: "Dave",
    172757468814770176: "Murt",
    219497453374668815: "Tommy",
    331082926475182081: "Muds",
    347489125877809155: "Nønø",
}

PLAYER_INDEXES = list(PLAYER_NAMES.keys())

PLAYER_BACKGROUNDS = {
    115142485579137029: "coven_nami.png",
    172757468814770176: "pentakill_olaf.png", 
    331082926475182081: "crime_city_tf.png",
    219497453374668815: "bard_splash.png",
    347489125877809155: "gladiator_draven.png",
}

# Sounds played when a specific player buzzes in first
BUZZ_IN_SOUNDS = {
    115142485579137029: "buzz_dave.mp3",
    172757468814770176: "buzz_murt.mp3",
    219497453374668815: "buzz_thommy.mp3",
    331082926475182081: "buzz_muds.mp3",
    347489125877809155: "buzz_no.mp3",
}

jeopardy_contestant_page = flask.Blueprint("jeopardy_contestant", __name__, template_folder="templates")

@jeopardy_contestant_page.route("/<client_secret>")
def lobby(client_secret):
    config = flask.current_app.config["APP_CONFIG"]
    database = flask.current_app.config["DATABASE"]

    if client_secret is None or client_secret == "None":
        return flask.abort(404)

    disc_id = database.get_user_from_secret(client_secret)

    if disc_id is None or int(disc_id) not in PLAYER_NAMES:
        return flask.abort(404)

    base_url = "https://mhooge.com:5006" if config.env == "production" else "http://localhost:5006"
    join_url = f"{base_url}/jeoparty/join"

    join_code = "lan_jeopardy_v6"
    password = "lan_jeoparty_wohooo"

    avatar = app_util.discord_request("func", "get_discord_avatar", disc_id)
    if avatar:
        avatar = flask.url_for("static", _external=True, filename=app_util.get_relative_static_folder(avatar, config))

    bg_image = PLAYER_BACKGROUNDS[disc_id]
    buzz_sound = BUZZ_IN_SOUNDS[disc_id]

    return app_util.make_template_context(
        "jeopardy/contestant_lobby.html",
        join_url=join_url,
        join_code=join_code,
        password=password,
        user_id=str(disc_id),
        player_name=PLAYER_NAMES[disc_id],
        avatar=avatar,
        bg_image=bg_image,
        buzz_sound=buzz_sound,
    )
