import re
import os
import shutil
import imageio
from PIL import Image
from picamera import PiCamera
from datetime import datetime
import numpy as np
from config import *

def createFolders():
    createFolder(LOG_DIR)
    createFolder(IMAGE_DIR)
    createFolder(TMP_DIR)

def createFolder(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

def myprint(*ts):
    global LOG_PATH
    date = str(datetime.today())
    text = ''
    for t in ts:
        text += str(t) + ' '
    date_prefix = '{}: \t'.format(date)
    with open(LOG_PATH, 'at') as log_file:
        log_file.write(date_prefix + text+ '\n')
    print(*ts)

def getCamera(resolution):
    camera = PiCamera()
    resolutions = {'max': (2592, 1944),
                   'halbmax': (1296, 972),
                   'viertelmax': (648, 486),
                   'fhd': (2340, 1080),
                   'hd': (1507, 720),
                   'good': (1004, 480),
                   'low': (670, 320),
                   'vlow': (335, 160)}
    camera.resolution = resolutions[resolution]
    camera.vflip = False
    camera.hflip = False
    return camera

def takeImage(camera):
    myprint('Making image')
    date = str(datetime.today())
    CURRENT_PATH = f'{IMAGE_DIR}/snapshot_{date}.jpg'
    camera.capture(CURRENT_PATH)
    deleteFile(LATEST_PATH)
    shutil.copy(CURRENT_PATH, LATEST_PATH)

def read_last_line(file_path):
    with open(file_path, 'rb') as file:
        file.seek(-2, 2)  # Move the cursor to the second last byte.
        while file.read(1) != b'\n':  # Move the cursor back until a newline is found.
            file.seek(-2, 1)
        last_line = file.readline().decode()
    return last_line

def extract_temps(line):
    temp_match = re.search(r'temp=(\d+)', line)
    max_temp_match = re.search(r'max_temp=(\d+)', line)
    temp = temp_match.group(1) if temp_match else None
    max_temp = max_temp_match.group(1) if max_temp_match else None
    return temp, max_temp


def count_files_in_folder(folder_path):
    items = os.listdir(folder_path)
    files = [item for item in items if os.path.isfile(os.path.join(folder_path, item))]
    return len(files)

def getInfo():
    last_line = read_last_line(TEMP_LOG_PATH)
    temp, max_temp = extract_temps(last_line)
    count = count_files_in_folder(IMAGE_DIR) - 1 # minus latest
    info = f'Temp: {temp}°C, Max Temp: {max_temp}°C, Foto Count: {count}'
    return info

def deleteFile(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)

def makeVideo(image_dir, video_path, fps):
    deleteFile(video_path)
    images = []
    for filename in sorted(os.listdir(image_dir)):
        if filename.endswith('.jpg') or filename.endswith('.png'):
            with Image.open(os.path.join(image_dir, filename)) as img:
                img = img.resize((640, 480))
                images.append(np.array(img))
    imageio.mimsave(video_path, images, fps=fps, codec='libx264')
