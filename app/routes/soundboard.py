import os

import flask
from werkzeug.utils import secure_filename

from api.audio_handler import get_available_sounds, SOUNDS_PATH
from app.util import make_template_context
import app.util as app_util

soundboard_page = flask.Blueprint("soundboard", __name__, template_folder="templates")

VALID_FILE_TYPES = set(["mp3"])
FILENAME_MAX_LENGTH = 20
UPLOAD_FOLDER = os.path.abspath(SOUNDS_PATH)

def valid_filetype(filename):
    return "." in filename and filename.split(".")[1] in VALID_FILE_TYPES

def soundboard_template(success=False, status_msg=None):
    available_sounds = get_available_sounds()

    return make_template_context(
        "soundboard.html", upload_success=success,
        status_msg=status_msg, sounds=available_sounds
    )

@soundboard_page.route('/', methods=["GET", "POST"])
def home():
    if flask.request.method == "POST":
        if "file" not in flask.request.files:
            return soundboard_template(False, "File is missing.")

        logged_in_user = app_util.get_user_details()[0]
        if logged_in_user is None:
            return soundboard_template(
                False, "You must be logged in to upload a sound file."
            )
        file = flask.request.files["file"]
        if file.filename == "":
            return soundboard_template(
                False, "No file selected."
            )

        if not valid_filetype(file.filename):
            return soundboard_template(False, "Invalid file type (must be .mp3).")

        if len(file.filename) > FILENAME_MAX_LENGTH:
            return soundboard_template(
                False, f"Filename too long (max {FILENAME_MAX_LENGTH} characters)."
            )

        secure_name = secure_filename(file.filename.replace(" ", "_").lower())
        path = os.path.join(UPLOAD_FOLDER, secure_name)
        if os.path.exists(path):
            return soundboard_template(
                False, f"Sound file with the name '{secure_name}' already exists."
            )

        file.save(path)
        return soundboard_template(True, f"'{secure_name}' successfully uploaded.")

    return soundboard_template()

def file_too_large(e):
    return make_template_context(
        "soundboard.html", status=413, upload_success=False,
        status_msg="File is too large (max is 250 KB)."
    )

soundboard_page.register_error_handler(413, file_too_large)
