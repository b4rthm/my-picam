# my-picam

A small Raspberry Pi application that takes pictures and builds timelapse
videos from them, with a small web server to view the results.

## What it does

* `makeFoto.py` – capture daemon, takes a picture every `PICAM_INTERVAL`
  seconds (default 3600 = hourly) into `images/`.
* `server.py` – web server that serves the latest picture, status
  information and builds timelapse videos.
* `temp-logger.sh` – logs the CPU temperature once a minute to
  `logs/temp.log`.

Both Python programs access the camera through `camera.py`, which uses a
lock file (`tmp/camera.lock`) so that **only one process at a time talks to
the camera**. The Pi camera cannot be opened by two processes at once, so
without this the server and the capture daemon would fight over it
("Camera is busy").

## Installation

    sudo apt install python3-picamera2 python3-flask python3-pil python3-numpy ffmpeg
    pip3 install imageio imageio-ffmpeg          # optional, for the timelapse

`picamera2` (Bookworm) and the legacy `picamera` (older images) are both
supported – whichever is installed is used.

## systemd services

Copy the unit files and enable them:

    sudo cp start_server.service start_makeFoto.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable start_server.service start_makeFoto.service
    sudo systemctl start start_server.service start_makeFoto.service

Check on them with:

    systemctl status start_server.service start_makeFoto.service
    journalctl -u start_server.service -f

## startup for temp logger

    chmod +x /home/pi/my-picam/temp-logger.sh

    sudo nano /etc/rc.local

Add this line:

    sudo /home/pi/my-picam/temp-logger.sh &

## useful aliases

    alias enableServices="sudo systemctl enable start_server.service && sudo systemctl enable start_makeFoto.service"
    alias disableServices="sudo systemctl disable start_server.service && sudo systemctl disable start_makeFoto.service"
    alias startServices="sudo systemctl start start_server.service && sudo systemctl start start_makeFoto.service"
    alias stopServices="sudo systemctl stop start_server.service && sudo systemctl stop start_makeFoto.service"

## check ip

    hostname -I

## routes

| Route                | Description                                    |
| -------------------- | ---------------------------------------------- |
| `/`                  | the latest picture                             |
| `/refresh`           | take a new picture and show it                 |
| `/info`              | status as text (temperature, photo count)       |
| `/info.json`         | status as JSON                                 |
| `/images`            | list of the captured pictures (newest first)   |
| `/timelapse?fps=3`   | build and download a timelapse video (mp4)      |
| `/timelapse?fps=3&rebuild=1` | force a rebuild of the video          |
| `/health`            | health check                                   |

## Configuration

Everything is configured through environment variables, so you rarely need
to touch the code. Set them in the systemd unit (`Environment=...`) or
export them before starting.

| Variable              | Default            | Description                                  |
| --------------------- | ------------------ | -------------------------------------------- |
| `PICAM_HOME`          | project directory  | where `images/`, `tmp/` and `logs/` live     |
| `PICAM_PORT`          | `80`               | web server port                              |
| `PICAM_HOST`          | `0.0.0.0`          | web server bind address                      |
| `PICAM_RESOLUTION`    | `max`              | `max`, `halbmax`, `viertelmax`, `fhd`, `hd`, `good`, `low`, `vlow` |
| `PICAM_INTERVAL`      | `3600`             | seconds between captures                     |
| `PICAM_AUTO_CAPTURE`  | `0`                | let the server capture on its own            |
| `PICAM_MAX_IMAGES`   | `0`                | max images to keep, `0` = unlimited          |
| `PICAM_VIDEO_FPS`     | `3`                | default fps of the timelapse                 |
| `PICAM_CAMERA_WARMUP` | `2`                | seconds to wait for auto exposure to settle  |
| `PICAM_LOG_LEVEL`     | `INFO`             | log level                                    |

## Notes

* The capture daemon (`makeFoto.py`) takes the periodic pictures, the web
  server only serves them and takes extra pictures on `/refresh`. If you
  prefer the server to do the scheduled captures as well, set
  `PICAM_AUTO_CAPTURE=1` **and** disable `start_makeFoto.service` –
  otherwise you get two pictures per interval.
* `PICAM_MAX_IMAGES=500` keeps the disk usage in check by deleting the
  oldest pictures (`0` = keep everything).
* The timelapse is cached; it is only rebuilt when the pictures or the
  requested fps changed. Use `&rebuild=1` to force it.

## Running the tests

    python3 -m unittest test_picam.py -v

There is also a multi-process test that proves the camera lock works:

    python3 test_camera_lock.py
