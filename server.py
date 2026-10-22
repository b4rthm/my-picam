"""Web server for my-picam.

Routes
------
``/``                the latest picture
``/info``            human readable status text
``/info.json``       the same as JSON
``/refresh``         take a new picture and show it
``/timelapse?fps=3`` build and serve a timelapse video
``/health``          simple health check
"""
import os
import threading
import time

from flask import Flask, jsonify, request, send_file

from camera import CameraError, CameraManager, snapshot_name
from config import (
    AUTO_CAPTURE,
    HOST,
    IMAGE_DIR,
    LATEST_PATH,
    MAX_FPS,
    MIN_FPS,
    PORT,
    SLEEP_TIME,
    VIDEO_PATH,
)
from logger import get_logger
from utils import (
    createFolders,
    format_info,
    getInfo,
    getVideo,
    list_images,
    makeVideo,
    prune_images,
    publish_latest,
)

log = get_logger()

createFolders()

app = Flask(__name__)

# One camera manager for the whole process - it serialises access between
# the request threads and the optional background capture thread.
camera = CameraManager(keepalive=5.0)

_capture_lock = threading.Lock()


def take_picture():
    """Take a picture, store it in the image folder and publish it."""
    with _capture_lock:
        path = os.path.join(IMAGE_DIR, snapshot_name())
        camera.capture(path)
        publish_latest(path, LATEST_PATH)
        prune_images()
        return path


def _send_file(path, mimetype, max_age=0):
    """Send a file, using conditional requests if the Flask version supports it."""
    try:
        return send_file(path, mimetype=mimetype, conditional=True, max_age=max_age)
    except TypeError:  # pragma: no cover - Flask < 2.0
        return send_file(path, mimetype=mimetype, max_age=max_age)


def _send_image(path, max_age=0):
    """Send an image file, supporting conditional requests if possible."""
    if not os.path.exists(path):
        return jsonify({"error": "No image available yet"}), 404
    return _send_file(path, "image/jpeg", max_age=max_age)


@app.route("/")
def latest_image():
    """Serve the most recent picture."""
    log.info("Serving latest image to %s", request.remote_addr)
    return _send_image(LATEST_PATH)


@app.route("/refresh")
def refresh():
    """Take a new picture and serve it."""
    log.info("Refresh requested by %s", request.remote_addr)
    try:
        take_picture()
    except CameraError as exc:
        log.error("Refresh failed: %s", exc)
        return jsonify({"error": str(exc)}), 503
    return _send_image(LATEST_PATH)


@app.route("/info")
def info():
    """Human readable status information."""
    log.info("Serving info to %s", request.remote_addr)
    return format_info(getInfo())


@app.route("/info.json")
def info_json():
    """Status information as JSON."""
    return jsonify(getInfo())


@app.route("/health")
def health():
    """Simple health check."""
    return jsonify({"status": "ok", "uptime": round(time.time() - _START_TIME, 1)})


@app.route("/timelapse")
def timelapse():
    """Build (if needed) and serve a timelapse video."""
    fps = request.args.get("fps", default=3, type=int)
    if fps is None or not (MIN_FPS <= fps <= MAX_FPS):
        return jsonify({"error": "fps must be between %s and %s" % (MIN_FPS, MAX_FPS)}), 400

    rebuild = request.args.get("rebuild", default="0", type=int) == 1
    log.info("Timelapse requested with %s fps", fps)
    try:
        getVideo(IMAGE_DIR, VIDEO_PATH, fps=fps, rebuild=rebuild)
    except Exception as exc:
        log.error("Timelapse failed: %s", exc)
        return jsonify({"error": str(exc)}), 500

    return _send_file(VIDEO_PATH, "video/mp4")


@app.route("/images")
def images():
    """List the captured pictures, newest first."""
    files = sorted(list_images(IMAGE_DIR), reverse=True)
    return jsonify({"count": len(files), "images": [os.path.basename(f) for f in files]})


@app.errorhandler(404)
def not_found(_error):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(500)
def server_error(error):
    log.error("Internal error: %s", error)
    return jsonify({"error": "Internal server error"}), 500


_START_TIME = time.time()


def _background_capture():
    """Capture a picture every SLEEP_TIME seconds."""
    while True:
        try:
            take_picture()
        except CameraError as exc:
            # Another process (e.g. makeFoto.py) is using the camera.
            log.warning("Scheduled capture skipped: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive
            log.error("Scheduled capture failed: %s", exc)
        time.sleep(SLEEP_TIME)


def start_background_capture():
    """Start the periodic capture thread (only if enabled)."""
    if not AUTO_CAPTURE:
        log.info("Automatic capture disabled (PICAM_AUTO_CAPTURE=0)")
        return
    thread = threading.Thread(target=_background_capture, name="capture", daemon=True)
    thread.start()
    log.info("Automatic capture every %s seconds", SLEEP_TIME)


def run():
    """Start the web server."""
    log.info("Starting server on %s:%s", HOST, PORT)
    start_background_capture()
    try:
        from waitress import serve

        log.info("Serving with waitress")
        serve(app, host=HOST, port=PORT, threads=4)
    except ImportError:
        log.info("Serving with the Flask development server")
        app.run(host=HOST, port=PORT, threaded=True, debug=False)


if __name__ == "__main__":
    run()
