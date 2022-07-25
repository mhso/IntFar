import json
import os
import shutil

import flask
from werkzeug.utils import secure_filename

from api.audio_handler import get_available_sounds, SOUNDS_PATH
import app.util as app_util
from discbot.commands.util import ADMIN_DISC_ID

soundboard_page = flask.Blueprint("soundboard", __name__, template_folder="templates")

VALID_FILE_TYPES = set(["mp3"])
INVALID_FILE_NAMES = set(["remove"])
FILENAME_MAX_LENGTH = 24
UPLOAD_FOLDER = os.path.abspath(SOUNDS_PATH)

def valid_filetype(filename):
    return "." in filename and filename.split(".")[1] in VALID_FILE_TYPES

def valid_filename(filename):
    return filename.replace("\\", "/").split("/")[-1].split(".")[0] not in INVALID_FILE_NAMES

def get_file_owners():
    owner_file_path = os.path.join(UPLOAD_FOLDER, "owners.json")
    with open(owner_file_path, encoding="utf-8") as fp:
        return json.load(fp)

def soundboard_template(success=False, status_msg=None):
    available_sounds = get_available_sounds()

    file_owners = get_file_owners()

    sound_list = [(name, file_owners.get(name, False)) for name in available_sounds]

    return app_util.make_template_context(
        "soundboard.html", upload_success=success,
        status_msg=status_msg, sounds=sound_list
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
        if not valid_filename(secure_name):
            return soundboard_template(
                False, f"Invalid filename '{secure_name}' Name is reserved."
            )

        path = os.path.join(UPLOAD_FOLDER, secure_name)
        if os.path.exists(path):
            return soundboard_template(
                False, f"Sound file with the name '{secure_name}' already exists."
            )

        file.save(path)

        # Normalize sound volumne.
        normalize_sound_volume(path)

        # Add sound/user to owners.json file.
        owner_file_path = os.path.join(UPLOAD_FOLDER, "owners.json")
        with open(owner_file_path, encoding="utf-8") as fp:
            owner_data = json.load(fp)

        base_name = os.path.basename(secure_name).split(".")[0]

        owner_data[base_name] = logged_in_user
        with open(owner_file_path, "w", encoding="utf-8") as fp:        
            json.dump(owner_data, fp, indent=4)

        return soundboard_template(True, f"'{secure_name}' successfully uploaded.")

    return soundboard_template()

@soundboard_page.route('/delete', methods=["POST"])
def delete():
    if "file" in flask.request.files:
        # Redirect to 'upload file' page
        return flask.redirect(flask.url_for("soundboard.home"))

    data = flask.request.form
    if "filename" not in data:
        return soundboard_template(False, "Filename is missing.")

    logged_in_user = app_util.get_user_details()[0]
    if logged_in_user is None:
        return soundboard_template(
            False, "You must be logged in to delete a sound file."
        )

    filename = data["filename"]
    file_owners = get_file_owners()

    if logged_in_user != ADMIN_DISC_ID and file_owners.get(filename) != logged_in_user:
        return soundboard_template(
            False, "You can't delete this sound as you did not upload it."
        )

    path = os.path.join(SOUNDS_PATH, filename + ".mp3")
    try:
        os.remove(path)
    except IOError:
        return soundboard_template(
            False, "File could not be deleted, an error occured."
        )

    # Remove sound/user from owners.json file.
    owner_file_path = os.path.join(UPLOAD_FOLDER, "owners.json")
    with open(owner_file_path, encoding="utf-8") as fp:
        owner_data = json.load(fp)

    del owner_data[filename]

    with open(owner_file_path, "w", encoding="utf-8") as fp:        
        json.dump(owner_data, fp, indent=4)

    return soundboard_template(True, f"'{filename}.mp3' successfully deleted.")

def file_too_large(e):
    return app_util.make_template_context(
        "soundboard.html", status=413, upload_success=False,
        status_msg="File is too large (max is 250 KB)."
    )

soundboard_page.register_error_handler(413, file_too_large)
