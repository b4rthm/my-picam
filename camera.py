"""Camera handling for my-picam.

The Raspberry Pi camera can only be opened by **one process at a time**.
The original project had `server.py` and `makeFoto.py` both opening a
`PiCamera`, which makes one of them fail with "Camera is busy" as soon as
both services are running.

To fix that, all camera access goes through :class:`CameraManager`, which
combines

* an in-process lock (thread safety inside the web server), and
* an inter-process lock (``fcntl.flock`` on ``tmp/camera.lock``).

The camera is opened lazily, kept open for a short while (so bursts of
captures are fast) and closed again afterwards so the other process can
take over.

Both the legacy ``picamera`` stack and the modern ``picamera2`` stack are
supported; whichever is importable is used.
"""
import errno
import fcntl
import os
import threading
import time
from datetime import datetime

from config import (
    CAMERA_FLIP_H,
    CAMERA_FLIP_V,
    CAMERA_LOCK_PATH,
    CAMERA_WARMUP,
    RESOLUTIONS,
    RESOLUTION,
)
from logger import get_logger

log = get_logger()


class CameraError(RuntimeError):
    """Raised when the camera could not be opened or used."""


class CameraBusy(CameraError):
    """Raised when the camera is used by another process."""


def _import_backend():
    """Return (name, factory) for the best available camera stack."""
    try:
        from picamera2 import Picamera2  # noqa: F401  (import check only)

        return "picamera2"
    except ImportError:
        pass

    try:
        from picamera import PiCamera  # noqa: F401  (import check only)

        return "picamera"
    except ImportError:
        pass

    return None


class _Picamera2Backend:
    """Adapter around the modern picamera2 stack."""

    name = "picamera2"

    def __init__(self, resolution):
        from picamera2 import Picamera2

        self._cam = Picamera2()
        config = self._cam.create_still_configuration(main={"size": resolution})
        self._cam.configure(config)
        self._cam.start()
        # Let auto-exposure settle, otherwise the first frames are too dark.
        if CAMERA_WARMUP > 0:
            time.sleep(CAMERA_WARMUP)

    def capture(self, path):
        self._cam.capture_file(path)

    def close(self):
        try:
            self._cam.stop()
        except Exception:  # pragma: no cover - defensive
            pass
        self._cam.close()


class _PicameraBackend:
    """Adapter around the legacy picamera stack."""

    name = "picamera"

    def __init__(self, resolution):
        from picamera import PiCamera

        self._cam = PiCamera()
        self._cam.resolution = resolution
        self._cam.vflip = CAMERA_FLIP_V
        self._cam.hflip = CAMERA_FLIP_H
        if CAMERA_WARMUP > 0:
            time.sleep(CAMERA_WARMUP)

    def capture(self, path):
        self._cam.capture(path)

    def close(self):
        self._cam.close()


class CameraManager:
    """Owns the physical camera and serialises access to it.

    Usage::

        with CameraManager() as cam:
            cam.capture("/tmp/shot.jpg")
    """

    def __init__(
        self,
        resolution=RESOLUTION,
        lock_path=CAMERA_LOCK_PATH,
        keepalive=20.0,
        lock_timeout=30.0,
    ):
        if resolution not in RESOLUTIONS:
            raise CameraError(
                "Unknown resolution %r, known: %s" % (resolution, ", ".join(sorted(RESOLUTIONS)))
            )
        self.resolution = resolution
        self.lock_path = lock_path
        self.keepalive = keepalive
        self.lock_timeout = lock_timeout
        self._backend = None
        self._lock = threading.RLock()
        self._last_used = 0.0
        self._lock_file = None
        self._reaper = None

    # -- locking ------------------------------------------------------------
    def _acquire(self, timeout=None):
        """Acquire the inter-process lock, raising CameraBusy on timeout.

        Re-entrant: if this process already holds the lock it is kept.
        """
        if timeout is None:
            timeout = self.lock_timeout
        if self._lock_file is not None:
            return
        lock_dir = os.path.dirname(self.lock_path)
        if lock_dir:
            os.makedirs(lock_dir, exist_ok=True)
        lock_file = open(self.lock_path, "w")
        deadline = time.time() + timeout
        while True:
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._lock_file = lock_file
                return
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN):
                    lock_file.close()
                    raise
                if time.time() >= deadline:
                    lock_file.close()
                    raise CameraBusy(
                        "Camera is busy (another process holds %s)" % self.lock_path
                    )
                time.sleep(0.1)

    def _release(self):
        if self._lock_file is not None:
            try:
                fcntl.flock(self._lock_file, fcntl.LOCK_UN)
            finally:
                self._lock_file.close()
                self._lock_file = None

    # -- camera lifecycle ---------------------------------------------------
    def _open(self):
        backend = _import_backend()
        if backend is None:
            raise CameraError(
                "Neither picamera2 nor picamera is installed - "
                "install with: sudo apt install python3-picamera2"
            )
        if backend == "picamera2":
            self._backend = _Picamera2Backend(RESOLUTIONS[self.resolution])
        else:
            self._backend = _PicameraBackend(RESOLUTIONS[self.resolution])
        log.info("Camera opened (%s backend, %s)", self._backend.name, self.resolution)

    def _close(self):
        if self._backend is not None:
            try:
                self._backend.close()
            except Exception as exc:  # pragma: no cover - defensive
                log.warning("Error while closing camera: %s", exc)
            self._backend = None
            log.info("Camera closed")

    def close(self):
        with self._lock:
            self._close()
            self._release()

    # -- public API ---------------------------------------------------------
    def capture(self, path):
        """Take a picture and store it at ``path``.

        The file is written atomically (temp file + rename), so a client
        downloading it can never read a half written image.
        """
        with self._lock:
            self._acquire()
            try:
                if self._backend is None:
                    self._open()

                # The extension must stay ".jpg" - the camera picks its
                # output format from the file extension.
                root, ext = os.path.splitext(path)
                tmp_path = "%s.tmp%s" % (root, ext or ".jpg")
                try:
                    self._backend.capture(tmp_path)
                    if not os.path.exists(tmp_path):
                        raise CameraError("Camera did not produce an image")
                    os.replace(tmp_path, path)
                finally:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                self._last_used = time.time()
            except CameraError:
                self._close()
                raise
            except Exception as exc:
                self._close()
                raise CameraError("Could not take picture: %s" % exc)
            finally:
                self._maybe_release()

    def _maybe_release(self):
        """Give the camera back to the other process when it is idle.

        The camera is kept open for a short while so that a burst of
        requests does not have to reopen it every time. A background
        thread releases it once it has been idle for that long.
        """
        if self.keepalive > 0:
            self._ensure_reaper()
            return
        self._close()
        self._release()

    def _ensure_reaper(self):
        """Start the thread that releases an idle camera."""
        if self._reaper is not None and self._reaper.is_alive():
            return
        self._reaper = threading.Thread(
            target=self._reap, name="camera-reaper", daemon=True
        )
        self._reaper.start()

    def _reap(self):
        """Close the camera once it has been idle for `keepalive` seconds."""
        while True:
            time.sleep(1.0)
            with self._lock:
                if self._backend is None:
                    # Nothing to release, stop the reaper.
                    return
                if (time.time() - self._last_used) >= self.keepalive:
                    log.info("Camera idle, releasing it")
                    self._close()
                    self._release()
                    return

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def snapshot_name(when=None):
    """Return a filename that sorts chronologically as plain text."""
    when = when or datetime.now()
    return "snapshot_%s.jpg" % when.strftime("%Y-%m-%d_%H-%M-%S")
