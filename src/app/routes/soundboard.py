import os
import shutil
from time import time

import flask
from werkzeug.utils import secure_filename

from mhooge_flask.logging import logger

from api.audio_handler import AudioHandler, SOUNDS_PATH
import app.util as app_util
from discbot.commands.util import ADMIN_DISC_ID

soundboard_page = flask.Blueprint("soundboard", __name__, template_folder="templates")

VALID_FILE_TYPES = set(["mp3"])
INVALID_FILE_NAMES = set(["remove"])
FILENAME_MAX_LENGTH = 24
UPLOAD_FOLDER = os.path.abspath(SOUNDS_PATH)

def valid_filetype(filename):
    split = filename.split(".")
    return len(split) == 2 and split[1] in VALID_FILE_TYPES

def valid_filename(filename):
    return filename.replace("\\", "/").split("/")[-1].split(".")[0] not in INVALID_FILE_NAMES

def soundboard_template(sounds, success=False, status_msg=None):
    return app_util.make_template_context(
        "soundboard.html",
        upload_success=success,
        status_msg=status_msg,
        sounds=sounds
    )

def normalize_sound_volume(filename):
    filename_no_ext = ".".join(filename.split(".")[:-1])

    new_filename = f"{filename_no_ext}_normed.mp3"

    command = f"ffmpeg -i {filename} -filter:a loudnorm {new_filename}"

    os.system(command)

    os.remove(filename)
    shutil.move(new_filename, filename)

@soundboard_page.route('/', methods=["GET", "POST"])
def home():
    config = flask.current_app.config["APP_CONFIG"]
    database = flask.current_app.config["DATABASE"]
    audio_handler = AudioHandler(config, database, None)
    sounds = audio_handler.get_sounds()

    if flask.request.method == "POST":
        if "file" not in flask.request.files:
            return soundboard_template(sounds, False, "File is missing.")

        logged_in_user = app_util.get_user_details()[0]
        if logged_in_user is None:
            return soundboard_template(
                sounds, False, "You must be logged in to upload a sound file."
            )

        file = flask.request.files["file"]
        if file.filename == "":
            return soundboard_template(
                sounds, False, "No file selected."
            )

        if not valid_filetype(file.filename):
            return soundboard_template(sounds, False, "Invalid file type (must be .mp3).")

        if len(file.filename) > FILENAME_MAX_LENGTH:
            return soundboard_template(
                sounds, False, f"Filename too long (max {FILENAME_MAX_LENGTH} characters)."
            )

        secure_name = secure_filename(file.filename.replace(" ", "_").lower())
        if not valid_filename(secure_name):
            return soundboard_template(
                sounds, False, f"Invalid filename '{secure_name}' Name is reserved."
            )

        path = os.path.join(UPLOAD_FOLDER, secure_name)
        if os.path.exists(path):
            return soundboard_template(
                sounds, False, f"Sound file with the name '{secure_name}' already exists."
            )

        file.save(path)

        # Normalize sound volumne
        normalize_sound_volume(path)

        # Add sound to database
        base_name = os.path.basename(secure_name).split(".")[0]    
        database.add_sound(base_name, logged_in_user, int(time()))

        sounds = audio_handler.get_sounds()

        return soundboard_template(sounds, True, f"'{secure_name}' successfully uploaded.")

    return soundboard_template(sounds)

@soundboard_page.route('/delete', methods=["POST"])
def delete():
    if "file" in flask.request.files:
        # Redirect to 'upload file' page
        return flask.redirect(flask.url_for("soundboard.home"))

    config = flask.current_app.config["APP_CONFIG"]
    database = flask.current_app.config["DATABASE"]
    audio_handler = AudioHandler(config, database, None)
    sounds = audio_handler.get_sounds()

    data = flask.request.form
    if "filename" not in data:
        return soundboard_template(sounds, False, "Filename is missing.")

    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user is None:
        return soundboard_template(
            sounds, False, "You must be logged in to delete a sound file."
        )

    filename = data["filename"]
    permission_to_delete = False
    for sound, owner_id, _, _ in sounds:
        if sound == filename:
            permission_to_delete = logged_in_user == ADMIN_DISC_ID or owner_id == logged_in_user
            break

    if not permission_to_delete:
        return soundboard_template(
            sounds, False, "You can't delete this sound as you did not upload it."
        )

    path = os.path.join(SOUNDS_PATH, filename + ".mp3")
    try:
        database.remove_sound(filename)
        os.remove(path)
    except Exception:
        logger.bind(filename=filename, user_id=logged_in_user).exception("Could not delete sound file on website!")
        return soundboard_template(
            sounds, False, "File could not be deleted, an error occured."
        )

    sounds = audio_handler.get_sounds()

    return soundboard_template(sounds, True, f"'{filename}.mp3' successfully deleted.")

def file_too_large(e):
    return app_util.make_template_context(
        "soundboard.html", status=413, upload_success=False,
        status_msg="File is too large (max is 250 KB)."
    )

soundboard_page.register_error_handler(413, file_too_large)
