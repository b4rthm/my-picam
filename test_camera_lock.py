"""Verify that several separate processes can use the camera without a conflict.

This is the bug that made the original project fail: `server.py` and
`makeFoto.py` both opened a `PiCamera`, so the second one got
"Camera is busy".

Run with:  python3 test_camera_lock.py
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

WORKER_SOURCE = '''
import os, sys, time
sys.path.insert(0, %r)
from PIL import Image
import camera as camera_module

class FakeBackend:
    name = "fake"
    def __init__(self, resolution):
        self.resolution = resolution
    def capture(self, path):
        # Simulate a real exposure taking a moment.
        time.sleep(0.4)
        Image.new("RGB", self.resolution, (10, 20, 30)).save(path)
    def close(self):
        pass

camera_module._import_backend = lambda: "fake"
camera_module._PicameraBackend = FakeBackend

from camera import CameraManager

worker_id, count, outdir = sys.argv[1], int(sys.argv[2]), sys.argv[3]

cam = CameraManager(keepalive=0, lock_timeout=60)
ok = 0
for i in range(count):
    try:
        path = os.path.join(outdir, "w%%s_%%02d.jpg" %% (worker_id, i))
        cam.capture(path)
        assert os.path.exists(path), "file missing"
        ok += 1
    except Exception as exc:
        print("WORKER %%s ERROR: %%s" %% (worker_id, exc))
        sys.exit(1)
cam.close()
print("WORKER %%s OK: %%d captures" %% (worker_id, ok))
''' % (HERE,)


def main():
    home = tempfile.mkdtemp(prefix="picam-lock-")
    env = dict(os.environ, PICAM_HOME=home, PICAM_LOG_LEVEL="WARNING")

    worker_path = os.path.join(home, "worker.py")
    with open(worker_path, "w") as f:
        f.write(WORKER_SOURCE)

    outdir = os.path.join(home, "out")
    os.makedirs(outdir)

    print("Starting 3 processes that all want to use the camera...\n")
    procs = [
        subprocess.Popen(
            [sys.executable, worker_path, str(i), "4", outdir],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for i in range(3)
    ]

    failed = False
    for proc in procs:
        out, _ = proc.communicate(timeout=180)
        print(out.strip())
        if proc.returncode != 0:
            failed = True

    files = sorted(os.listdir(outdir))
    print("\nFiles created: %d" % len(files))
    for name in files:
        print("  ", name)

    assert not failed, "a worker failed - the camera lock is not working"
    assert len(files) == 12, "expected 12 images, got %d" % len(files)
    print("\nSUCCESS: all 3 processes used the camera without a conflict")
    return 0


if __name__ == "__main__":
    sys.exit(main())
