"""Tests for my-picam.

Run with:  python3 -m pytest test_picam.py -v
(or simply: python3 test_picam.py)
"""
import os
import shutil
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Use a temporary data directory so the tests never touch real pictures.
_TMP_HOME = tempfile.mkdtemp(prefix="picam-test-")
os.environ["PICAM_HOME"] = _TMP_HOME
os.environ["PICAM_AUTO_CAPTURE"] = "0"

import camera as camera_module  # noqa: E402
import utils  # noqa: E402
from config import IMAGE_DIR, LATEST_PATH, LOG_DIR, TMP_DIR  # noqa: E402


def tearDownModule():
    shutil.rmtree(_TMP_HOME, ignore_errors=True)


class TestTempParsing(unittest.TestCase):
    def test_extract_temps_new_format(self):
        temp, max_temp = utils.extract_temps("temp=45.3 max_temp=48.1")
        self.assertEqual(temp, "45.3")
        self.assertEqual(max_temp, "48.1")

    def test_extract_temps_old_format(self):
        temp, max_temp = utils.extract_temps("temp=45'C max_temp=48'C")
        self.assertEqual(temp, "45")
        self.assertEqual(max_temp, "48")

    def test_extract_temps_does_not_confuse_max_with_current(self):
        # "max_temp=48" must not be reported as the current temperature.
        temp, max_temp = utils.extract_temps("max_temp=48.1 temp=45.3")
        self.assertEqual(temp, "45.3")
        self.assertEqual(max_temp, "48.1")

    def test_extract_temps_empty(self):
        self.assertEqual(utils.extract_temps(""), (None, None))
        self.assertEqual(utils.extract_temps("nothing useful"), (None, None))


class TestReadLastLine(unittest.TestCase):
    def test_missing_file(self):
        # The old implementation raised OSError here.
        self.assertEqual(utils.read_last_line("/nonexistent/file.log"), "")

    def test_empty_file(self):
        path = os.path.join(_TMP_HOME, "empty.log")
        open(path, "w").close()
        self.assertEqual(utils.read_last_line(path), "")

    def test_no_trailing_newline(self):
        path = os.path.join(_TMP_HOME, "nonl.log")
        with open(path, "w") as f:
            f.write("first\nlast line without newline")
        self.assertEqual(utils.read_last_line(path), "last line without newline")

    def test_reads_last_line(self):
        path = os.path.join(_TMP_HOME, "multi.log")
        with open(path, "w") as f:
            f.write("a\nb\nc\n")
        self.assertEqual(utils.read_last_line(path), "c")


class TestFileHelpers(unittest.TestCase):
    def test_create_folders_is_idempotent(self):
        utils.createFolders()
        utils.createFolders()  # must not raise
        for folder in (LOG_DIR, IMAGE_DIR, TMP_DIR):
            self.assertTrue(os.path.isdir(folder))

    def test_delete_file_missing_is_safe(self):
        utils.deleteFile("/nonexistent/file.jpg")  # must not raise

    def test_copy_file_replaces_destination(self):
        src = os.path.join(_TMP_HOME, "src.txt")
        dst = os.path.join(_TMP_HOME, "dst.txt")
        with open(src, "w") as f:
            f.write("hello")
        utils.copyFile(src, dst)
        with open(dst) as f:
            self.assertEqual(f.read(), "hello")

    def test_count_files(self):
        folder = os.path.join(_TMP_HOME, "countme")
        os.makedirs(folder, exist_ok=True)
        for name in ("a.jpg", "b.jpg", "c.txt"):
            open(os.path.join(folder, name), "w").close()
        self.assertEqual(utils.count_files_in_folder(folder), 2)
        self.assertEqual(utils.count_files_in_folder("/nonexistent"), 0)

    def test_prune_keeps_newest(self):
        folder = os.path.join(_TMP_HOME, "prune")
        os.makedirs(folder, exist_ok=True)
        for i in range(5):
            open(os.path.join(folder, "img_%d.jpg" % i), "w").close()
        removed = utils.prune_images(folder, max_images=2)
        self.assertEqual(removed, 3)
        self.assertEqual(len(os.listdir(folder)), 2)

    def test_prune_disabled(self):
        folder = os.path.join(_TMP_HOME, "noprune")
        os.makedirs(folder, exist_ok=True)
        for i in range(5):
            open(os.path.join(folder, "img_%d.jpg" % i), "w").close()
        self.assertEqual(utils.prune_images(folder, max_images=0), 0)
        self.assertEqual(len(os.listdir(folder)), 5)

    def test_list_images_sorted(self):
        folder = os.path.join(_TMP_HOME, "sorted")
        os.makedirs(folder, exist_ok=True)
        for name in ("b.jpg", "a.jpg", "c.png", "d.txt"):
            open(os.path.join(folder, name), "w").close()
        names = [os.path.basename(p) for p in utils.list_images(folder)]
        self.assertEqual(names, ["a.jpg", "b.jpg", "c.png"])


class TestGetInfo(unittest.TestCase):
    def setUp(self):
        self.temp_log = os.path.join(LOG_DIR, "temp.log")
        if os.path.exists(self.temp_log):
            os.remove(self.temp_log)

    def tearDown(self):
        if os.path.exists(self.temp_log):
            os.remove(self.temp_log)

    def test_info_without_temperature_log(self):
        # Must not raise even though the temp log does not exist.
        info = utils.getInfo()
        self.assertIn("photo_count", info)
        self.assertIsNone(info["temp"])

    def test_info_with_temperature_log(self):
        utils.createFolders()
        with open(self.temp_log, "w") as f:
            f.write("temp=42.5 max_temp=44.0\n")
        info = utils.getInfo()
        self.assertEqual(info["temp"], "42.5")
        self.assertEqual(info["max_temp"], "44.0")
        self.assertIn("42.5", utils.format_info(info))


class TestSnapshotNames(unittest.TestCase):
    def test_name_is_sortable(self):
        from datetime import datetime

        early = camera_module.snapshot_name(datetime(2024, 1, 2, 3, 4, 5))
        late = camera_module.snapshot_name(datetime(2024, 1, 2, 3, 4, 6))
        self.assertLess(early, late)

    def test_name_has_no_colons(self):
        # Colons break on some filesystems and in URLs.
        from datetime import datetime

        name = camera_module.snapshot_name(datetime(2024, 1, 2, 3, 4, 5))
        self.assertNotIn(":", name)
        self.assertTrue(name.endswith(".jpg"))


class FakeBackend(object):
    """Stand-in for the real camera backend."""

    name = "fake"

    def __init__(self, resolution):
        self.resolution = resolution
        self.closed = False

    def capture(self, path):
        with open(path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0fakejpegdata")

    def close(self):
        self.closed = True


class TestCameraManager(unittest.TestCase):
    """The camera may only be used by one process at a time."""

    def setUp(self):
        self.opened = []
        self._real_import = camera_module._import_backend
        camera_module._import_backend = lambda: "fake"
        self._real_backend = camera_module._PicameraBackend
        camera_module._PicameraBackend = FakeBackend

    def tearDown(self):
        camera_module._import_backend = self._real_import
        camera_module._PicameraBackend = self._real_backend

    def test_capture_writes_file(self):
        target = os.path.join(_TMP_HOME, "shot.jpg")
        with camera_module.CameraManager() as cam:
            cam.capture(target)
        self.assertTrue(os.path.exists(target))
        with open(target, "rb") as f:
            self.assertTrue(f.read().startswith(b"\xff\xd8"))

    def test_capture_leaves_no_temp_file(self):
        target = os.path.join(_TMP_HOME, "shot2.jpg")
        with camera_module.CameraManager() as cam:
            cam.capture(target)
        leftovers = [f for f in os.listdir(_TMP_HOME) if ".tmp" in f]
        self.assertEqual(leftovers, [])

    def test_temp_file_keeps_jpg_extension(self):
        # picamera picks the format from the extension.
        target = os.path.join(_TMP_HOME, "shot3.jpg")
        seen = {}

        class RecordingBackend(FakeBackend):
            def capture(self, path):
                seen["path"] = path
                FakeBackend.capture(self, path)

        camera_module._PicameraBackend = RecordingBackend
        with camera_module.CameraManager() as cam:
            cam.capture(target)
        self.assertTrue(seen["path"].endswith(".jpg"))
        self.assertIn(".tmp", seen["path"])

    def test_second_manager_waits_for_the_lock(self):
        # Simulate another process holding the lock file.
        import fcntl

        lock_path = os.path.join(_TMP_HOME, "busy.lock")
        holder = open(lock_path, "w")
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            cam = camera_module.CameraManager(lock_path=lock_path, lock_timeout=0.2)
            with self.assertRaises(camera_module.CameraBusy):
                cam.capture(os.path.join(_TMP_HOME, "x.jpg"))
        finally:
            fcntl.flock(holder, fcntl.LOCK_UN)
            holder.close()

    def test_unknown_resolution_raises(self):
        with self.assertRaises(camera_module.CameraError):
            camera_module.CameraManager(resolution="does-not-exist")

    def test_failed_capture_closes_the_camera(self):
        class FailingBackend(FakeBackend):
            def capture(self, path):
                raise IOError("sensor error")

        camera_module._PicameraBackend = FailingBackend
        cam = camera_module.CameraManager()
        with self.assertRaises(camera_module.CameraError):
            cam.capture(os.path.join(_TMP_HOME, "fail.jpg"))
        self.assertIsNone(cam._backend)

    def test_idle_camera_is_released(self):
        # An idle camera must not stay locked forever, otherwise the other
        # process could never take a picture.
        cam = camera_module.CameraManager(keepalive=0.3)
        try:
            cam.capture(os.path.join(_TMP_HOME, "idle.jpg"))
            self.assertIsNotNone(cam._backend)
            deadline = time.time() + 5
            while cam._backend is not None and time.time() < deadline:
                time.sleep(0.1)
            self.assertIsNone(cam._backend, "idle camera was not released")
            self.assertIsNone(cam._lock_file, "lock was not released")
        finally:
            cam.close()

    def test_keepalive_zero_closes_immediately(self):
        cam = camera_module.CameraManager(keepalive=0)
        try:
            cam.capture(os.path.join(_TMP_HOME, "nokeep.jpg"))
            self.assertIsNone(cam._backend)
            self.assertIsNone(cam._lock_file)
        finally:
            cam.close()


class TestVideo(unittest.TestCase):
    def test_make_video_creates_file(self):
        from PIL import Image

        folder = os.path.join(_TMP_HOME, "video_src")
        os.makedirs(folder, exist_ok=True)
        for i in range(3):
            Image.new("RGB", (64, 48), (i * 40, 100, 150)).save(
                os.path.join(folder, "frame_%02d.jpg" % i)
            )

        out = os.path.join(_TMP_HOME, "out.mp4")
        try:
            utils.makeVideo(folder, out, fps=2, size=(64, 48))
        except RuntimeError as exc:
            self.skipTest("no encoder available: %s" % exc)
        self.assertTrue(os.path.exists(out))
        self.assertGreater(os.path.getsize(out), 0)
        leftovers = [f for f in os.listdir(_TMP_HOME) if f.startswith("out.tmp")]
        self.assertEqual(leftovers, [])

    def test_make_video_without_images_raises(self):
        empty = os.path.join(_TMP_HOME, "empty_src")
        os.makedirs(empty, exist_ok=True)
        with self.assertRaises(RuntimeError):
            utils.makeVideo(empty, os.path.join(_TMP_HOME, "empty.mp4"), fps=2)

    def test_video_is_reused_when_unchanged(self):
        from PIL import Image

        folder = os.path.join(_TMP_HOME, "cache_src")
        os.makedirs(folder, exist_ok=True)
        for i in range(2):
            Image.new("RGB", (64, 48), (i * 60, 100, 150)).save(
                os.path.join(folder, "frame_%02d.jpg" % i)
            )

        out = os.path.join(_TMP_HOME, "cached.mp4")
        meta = os.path.join(_TMP_HOME, "cached.json")
        try:
            utils.getVideo(folder, out, fps=2, size=(64, 48))
        except RuntimeError as exc:
            self.skipTest("no encoder available: %s" % exc)

        first_mtime = os.path.getmtime(out)
        time.sleep(0.01)

        # Second call must reuse the file instead of rebuilding it.
        utils.getVideo(folder, out, fps=2, size=(64, 48))
        self.assertEqual(os.path.getmtime(out), first_mtime)

        # A different fps forces a rebuild.
        utils.getVideo(folder, out, fps=5, size=(64, 48))
        self.assertNotEqual(os.path.getmtime(out), first_mtime)


class TestServer(unittest.TestCase):
    def setUp(self):
        import server

        self.server = server
        server.app.config["TESTING"] = True
        self.client = server.app.test_client()
        if os.path.exists(LATEST_PATH):
            os.remove(LATEST_PATH)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_info_json(self):
        response = self.client.get("/info.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("photo_count", response.get_json())

    def test_info_text(self):
        response = self.client.get("/info")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Temp", response.get_data(as_text=True))

    def test_root_without_image_returns_404(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 404)

    def test_timelapse_rejects_bad_fps(self):
        response = self.client.get("/timelapse?fps=0")
        self.assertEqual(response.status_code, 400)
        response = self.client.get("/timelapse?fps=999")
        self.assertEqual(response.status_code, 400)

    def test_unknown_route_returns_json_404(self):
        response = self.client.get("/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.get_json())

    def test_root_serves_image(self):
        from PIL import Image

        utils.createFolders()
        Image.new("RGB", (32, 24), (10, 20, 30)).save(LATEST_PATH)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "image/jpeg")


if __name__ == "__main__":
    unittest.main(verbosity=2)
