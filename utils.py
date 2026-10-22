"""Helper functions for my-picam."""
import fnmatch
import json
import os
import re
import shutil
import subprocess
import tempfile

from config import (
    IMAGE_DIR,
    LATEST_PATH,
    LOG_DIR,
    MAX_IMAGES,
    TEMP_LOG_PATH,
    TMP_DIR,
    VIDEO_META_PATH,
    VIDEO_PATH,
    VIDEO_SIZE,
)
from logger import get_logger

log = get_logger()


# --- filesystem ------------------------------------------------------------
def createFolder(folder_path):
    """Create a directory if it does not exist yet."""
    os.makedirs(folder_path, exist_ok=True)
    return folder_path


def createFolders():
    """Create all directories used by the application."""
    for folder in (LOG_DIR, IMAGE_DIR, TMP_DIR):
        createFolder(folder)


def deleteFile(file_path):
    """Delete a file, ignoring it if it does not exist."""
    try:
        os.remove(file_path)
    except FileNotFoundError:
        pass
    except OSError as exc:
        log.warning("Could not delete %s: %s", file_path, exc)


def copyFile(src, dst):
    """Copy a file, replacing the destination atomically."""
    directory = os.path.dirname(dst) or "."
    createFolder(directory)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-")
    os.close(fd)
    try:
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def count_files_in_folder(folder_path, pattern="*.jpg"):
    """Count files matching ``pattern`` (a glob) in a folder."""
    if not os.path.isdir(folder_path):
        return 0
    return len([f for f in os.listdir(folder_path) if fnmatch.fnmatch(f, pattern)])


def list_images(folder_path=IMAGE_DIR, extensions=(".jpg", ".jpeg", ".png")):
    """Return the image files of a folder, sorted oldest first."""
    if not os.path.isdir(folder_path):
        return []
    names = [f for f in os.listdir(folder_path) if f.lower().endswith(extensions)]
    return [os.path.join(folder_path, n) for n in sorted(names)]


def prune_images(folder_path=IMAGE_DIR, max_images=MAX_IMAGES):
    """Delete the oldest images so at most ``max_images`` remain.

    ``max_images <= 0`` disables pruning.
    """
    if not max_images or max_images <= 0:
        return 0
    images = list_images(folder_path)
    if len(images) <= max_images:
        return 0
    removed = 0
    for path in images[: len(images) - max_images]:
        deleteFile(path)
        removed += 1
    if removed:
        log.info("Pruned %s old images", removed)
    return removed


# --- temperature log -------------------------------------------------------
def read_last_line(file_path):
    """Return the last non-empty line of a file.

    The original implementation used ``seek(-2, 2)`` which raises an
    ``OSError`` on an empty or missing file - exactly what happens right
    after the temperature logger has been restarted.
    """
    if not os.path.exists(file_path):
        return ""
    try:
        with open(file_path, "rb") as file:
            file.seek(0, os.SEEK_END)
            size = file.tell()
            if size == 0:
                return ""
            # Read the tail of the file, growing the window until a newline
            # is found.
            block = 512
            pos = size
            data = b""
            while pos > 0:
                read_size = min(block, pos)
                pos -= read_size
                file.seek(pos)
                data = file.read(read_size) + data
                if b"\n" in data:
                    break
    except OSError as exc:
        log.warning("Could not read %s: %s", file_path, exc)
        return ""

    lines = [line.strip() for line in data.split(b"\n") if line.strip()]
    if not lines:
        return ""
    return lines[-1].decode("utf-8", errors="replace")


def extract_temps(line):
    """Extract current and maximum temperature from a log line.

    Handles both the old format (``temp=42'C ... max_temp=48'C``) and the
    new one (``temp=42.3 max_temp=48.1``).
    """
    if not line:
        return None, None

    temp = None
    max_temp = None

    match = re.search(r"max_temp\s*=\s*([0-9]+(?:\.[0-9]+)?)", line)
    if match:
        max_temp = match.group(1)

    # Skip the "max_temp" match so we do not report it as the current temp.
    match = re.search(r"(?<!max_)\btemp\s*=\s*([0-9]+(?:\.[0-9]+)?)", line)
    if match:
        temp = match.group(1)

    return temp, max_temp


def getInfo():
    """Return a dict with the current state of the camera."""
    last_line = read_last_line(TEMP_LOG_PATH)
    temp, max_temp = extract_temps(last_line)
    count = count_files_in_folder(IMAGE_DIR)
    return {
        "temp": temp,
        "max_temp": max_temp,
        "photo_count": count,
        "disk_free": shutil.disk_usage(IMAGE_DIR if os.path.isdir(IMAGE_DIR) else "/").free,
    }


def format_info(info):
    """Format the info dict as a human readable line."""
    temp = info.get("temp")
    max_temp = info.get("max_temp")
    temp_str = "%s°C" % temp if temp is not None else "n/a"
    max_str = "%s°C" % max_temp if max_temp is not None else "n/a"
    return "Temp: %s, Max Temp: %s, Foto Count: %s" % (
        temp_str,
        max_str,
        info.get("photo_count", 0),
    )


# --- timelapse -------------------------------------------------------------
def _ffmpeg_available():
    try:
        subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def _video_is_current(video_path, fps, images):
    """Check whether the existing video matches the requested fps and images."""
    if not os.path.exists(video_path):
        return False
    try:
        with open(VIDEO_META_PATH) as f:
            meta = json.load(f)
    except (OSError, ValueError):
        return False

    if meta.get("fps") != fps:
        return False
    if meta.get("count") != len(images):
        return False
    if meta.get("newest") != _newest_mtime(images):
        return False
    # The video must be newer than the newest picture.
    try:
        return os.path.getmtime(video_path) >= _newest_mtime(images)
    except OSError:
        return False


def _newest_mtime(images):
    newest = 0.0
    for path in images:
        try:
            newest = max(newest, os.path.getmtime(path))
        except OSError:
            continue
    return newest


def makeVideo(image_dir=IMAGE_DIR, video_path=VIDEO_PATH, fps=3, size=VIDEO_SIZE):
    """Create a timelapse video from the captured images.

    The images are streamed into ffmpeg one by one instead of being loaded
    into memory all at once - the old implementation collected every frame
    as a numpy array and ran out of RAM on a Pi after a few hundred images.

    The video is written to a temporary file and moved into place
    afterwards, so clients never get a partially written video.
    """
    from PIL import Image, ImageOps

    images = list_images(image_dir)
    if not images:
        raise RuntimeError("No images found in %s" % image_dir)

    os.makedirs(os.path.dirname(video_path) or ".", exist_ok=True)
    tmp_path = "%s.tmp.mp4" % os.path.splitext(video_path)[0]

    if _ffmpeg_available():
        _make_video_ffmpeg(images, tmp_path, fps, size, Image, ImageOps)
    else:
        log.warning("ffmpeg not found - falling back to a GIF timelapse")
        tmp_path = "%s.tmp.gif" % os.path.splitext(video_path)[0]
        _make_video_gif(images, tmp_path, fps, Image, ImageOps)

    os.replace(tmp_path, video_path)

    # Remember what the video contains so it can be reused.
    try:
        with open(VIDEO_META_PATH, "w") as f:
            json.dump(
                {"fps": fps, "count": len(images), "newest": _newest_mtime(images)},
                f,
            )
    except OSError as exc:
        log.warning("Could not write video metadata: %s", exc)

    log.info("Timelapse written to %s (%s images, %s fps)", video_path, len(images), fps)
    return video_path


def getVideo(image_dir=IMAGE_DIR, video_path=VIDEO_PATH, fps=3, size=VIDEO_SIZE, rebuild=False):
    """Return the timelapse video, rebuilding it only when necessary."""
    images = list_images(image_dir)
    if not images:
        raise RuntimeError("No images found in %s" % image_dir)

    if not rebuild and _video_is_current(video_path, fps, images):
        log.info("Reusing existing timelapse %s", video_path)
        return video_path

    return makeVideo(image_dir, video_path, fps=fps, size=size)


def _fit_frame(img, size, Image, ImageOps):
    """Resize an image to ``size`` keeping its aspect ratio."""
    img = img.convert("RGB")
    return ImageOps.fit(img, size, method=Image.LANCZOS, centering=(0.5, 0.5))


def _make_video_ffmpeg(images, tmp_path, fps, size, Image, ImageOps):
    """Stream the images through ffmpeg via imageio's pipe interface."""
    import imageio
    import numpy as np

    # imageio >= 2.9 moved the v2 API into imageio.v2; the old location
    # still works but prints a deprecation warning.
    get_writer = getattr(getattr(imageio, "v2", None), "get_writer", None)
    if get_writer is None:
        get_writer = imageio.get_writer

    writer = get_writer(
        tmp_path,
        fps=fps,
        codec="libx264",
        quality=8,
        macro_block_size=16,
        ffmpeg_log_level="error",
    )
    try:
        for path in images:
            with Image.open(path) as img:
                frame = _fit_frame(img, size, Image, ImageOps)
                writer.append_data(np.asarray(frame))
    finally:
        writer.close()


def _make_video_gif(images, tmp_path, fps, Image, ImageOps):
    """Fallback that writes an animated GIF using Pillow only."""
    frames = []
    for path in images:
        with Image.open(path) as img:
            frames.append(_fit_frame(img, (size[0] // 2, size[1] // 2), Image, ImageOps))
    duration = max(1, int(round(1000.0 / max(fps, 1))))
    frames[0].save(
        tmp_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
    )


def publish_latest(source_path, latest_path=LATEST_PATH):
    """Publish an image as the current 'latest' picture."""
    copyFile(source_path, latest_path)
    return latest_path
