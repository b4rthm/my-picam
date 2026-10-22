"""Periodic capture daemon.

Takes a picture every ``PICAM_INTERVAL`` seconds (default: one hour) and
publishes it as the current picture.

If the web server runs on the same machine, both processes share the camera
through the lock file in ``camera.py`` - only one of them has the camera
open at any time.
"""
import os
import signal
import sys
import threading
import time

from camera import CameraError, CameraManager, snapshot_name
from config import IMAGE_DIR, LATEST_PATH, RESOLUTION, SLEEP_TIME
from logger import get_logger
from utils import createFolders, prune_images, publish_latest

log = get_logger()

_stop = False


def _handle_signal(signum, _frame):
    global _stop
    log.info("Received signal %s - stopping", signum)
    _stop = True


def _install_signal_handlers():
    """Stop cleanly on SIGTERM/SIGINT.

    Signal handlers can only be installed in the main thread, so this is
    skipped when the daemon is started from a thread (e.g. in tests).
    """
    if threading.current_thread() is not threading.main_thread():
        return
    for signum in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(signum, _handle_signal)
        except (ValueError, OSError):  # pragma: no cover - defensive
            pass


def take_picture(camera):
    """Take one picture, store it and publish it as the latest one."""
    path = os.path.join(IMAGE_DIR, snapshot_name())
    camera.capture(path)
    publish_latest(path, LATEST_PATH)
    prune_images()
    log.info("Saved %s", path)
    return path


def main():
    createFolders()

    _install_signal_handlers()

    # keepalive=0 -> the camera is closed right after each picture so the
    # web server can use it in between.
    camera = CameraManager(resolution=RESOLUTION, keepalive=0)

    log.info("Starting capture daemon, interval %s seconds", SLEEP_TIME)
    try:
        while not _stop:
            try:
                take_picture(camera)
            except CameraError as exc:
                # The web server may be using the camera right now.
                log.warning("Capture failed: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive
                log.error("Unexpected error during capture: %s", exc)

            # Sleep in small steps so a stop signal is handled quickly.
            deadline = time.time() + SLEEP_TIME
            while not _stop and time.time() < deadline:
                time.sleep(min(1.0, max(0.0, deadline - time.time())))
    finally:
        camera.close()
        log.info("Capture daemon stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
