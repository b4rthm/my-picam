"""Configuration for my-picam.

Every setting can be overridden with an environment variable, so the same
code can be started from a checkout, from a systemd unit or by hand.

    PICAM_PORT=8080 PICAM_INTERVAL=60 python3 server.py
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _env_str(name, default):
    value = os.environ.get(name)
    return default if value in (None, "") else value


def _env_int(name, default):
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _env_float(name, default):
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _env_bool(name, default):
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


# --- directories -----------------------------------------------------------
# Everything lives below PICAM_HOME (the project directory by default) so the
# app works no matter where it is checked out.
PICAM_HOME = os.path.abspath(_env_str("PICAM_HOME", BASE_DIR))
LOG_DIR = os.path.join(PICAM_HOME, "logs")
IMAGE_DIR = os.path.join(PICAM_HOME, "images")
TMP_DIR = os.path.join(PICAM_HOME, "tmp")

TEMP_LOG_PATH = os.path.join(LOG_DIR, "temp.log")
LOG_PATH = os.path.join(LOG_DIR, "my.log")
LATEST_PATH = os.path.join(TMP_DIR, "latest.jpg")
VIDEO_PATH = os.path.join(TMP_DIR, "video.mp4")
VIDEO_META_PATH = os.path.join(TMP_DIR, "video.json")
# Lock file used to make sure only one process at a time talks to the camera.
CAMERA_LOCK_PATH = os.path.join(TMP_DIR, "camera.lock")

# --- web server ------------------------------------------------------------
HOST = _env_str("PICAM_HOST", "0.0.0.0")
PORT = _env_int("PICAM_PORT", 80)

# --- camera ----------------------------------------------------------------
RESOLUTION = _env_str("PICAM_RESOLUTION", "max")
RESOLUTIONS = {
    "max": (2592, 1944),
    "halbmax": (1296, 972),
    "viertelmax": (648, 486),
    "fhd": (2340, 1080),
    "hd": (1507, 720),
    "good": (1004, 480),
    "low": (670, 320),
    "vlow": (335, 160),
}
CAMERA_FLIP_H = _env_bool("PICAM_FLIP_H", False)
CAMERA_FLIP_V = _env_bool("PICAM_FLIP_V", False)
# Seconds to wait after opening the camera so auto exposure can settle.
# Without this the first frames of a timelapse are noticeably too dark.
CAMERA_WARMUP = _env_float("PICAM_CAMERA_WARMUP", 2.0)

# --- capture schedule ------------------------------------------------------
# Seconds between two automatic captures. 0 disables the automatic capture.
SLEEP_TIME = _env_int("PICAM_INTERVAL", 3600)
# The capture daemon (makeFoto.py) is normally the one taking the periodic
# pictures, so the web server only captures on demand (/refresh).
# Set PICAM_AUTO_CAPTURE=1 to let the server do it as well - but then do
# not run start_makeFoto.service, otherwise you get two pictures per interval.
AUTO_CAPTURE = _env_bool("PICAM_AUTO_CAPTURE", False) and SLEEP_TIME > 0
# Maximum number of images kept on disk, 0 = keep everything.
MAX_IMAGES = _env_int("PICAM_MAX_IMAGES", 0)

# --- timelapse video -------------------------------------------------------
VIDEO_FPS = _env_int("PICAM_VIDEO_FPS", 3)
VIDEO_SIZE = (_env_int("PICAM_VIDEO_WIDTH", 640), _env_int("PICAM_VIDEO_HEIGHT", 480))
MIN_FPS = 1
MAX_FPS = 60

# --- logging ---------------------------------------------------------------
LOG_MAX_BYTES = _env_int("PICAM_LOG_MAX_BYTES", 1024 * 1024)
LOG_BACKUP_COUNT = _env_int("PICAM_LOG_BACKUPS", 3)
LOG_LEVEL = _env_str("PICAM_LOG_LEVEL", "INFO").upper()
