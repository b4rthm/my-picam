import os

PORT = 5000
RESOLUTION = 'max'
SLEEP_TIME = 3600

LOG_DIR = '/home/pi/my-picam/logs'
IMAGE_DIR = '/home/pi/my-picam/images'
TMP_DIR = '/home/pi/my-picam/tmp'

TEMP_LOG_PATH = os.path.join(LOG_DIR, 'temp.log')
LOG_PATH = os.path.join(LOG_DIR, 'my.log')
LATEST_PATH = os.path.join(TMP_DIR, 'latest.jpg')
VIDEO_PATH = os.path.join(TMP_DIR, 'video.mp4')

