import re
import os
import shutil
import imageio
from PIL import Image
from picamera import PiCamera
from datetime import datetime
import numpy as np

log_path = '/home/pi/makeFotoAndServeLatest.log'

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
    currentFilePath = '/home/pi/fotos/snapshot_' + date + '.jpg'
    latestFilePath = '/home/pi/latest.jpg'
    camera.capture(currentFilePath)
    deleteFile(latestFilePath)
    shutil.copy(currentFilePath, latestFilePath)

def myprint(*ts, new_line=False):
    global log_path
    date = str(datetime.today())
    text = ''
    for t in ts:
        text += str(t) + ' '
    date_prefix = '{}: \t'.format(date)
    with open(log_path, 'at') as log_file:
        log_file.write(date_prefix + text+ '\n')
    print(*ts)

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
    file_path = '/home/pi/temperature.log'
    last_line = read_last_line(file_path)
    temp, max_temp = extract_temps(last_line)
    folder_path = '/home/pi/fotos/'
    count = count_files_in_folder(folder_path) - 1 # minus latest
    info = f'Temp: {temp}°C, Max Temp: {max_temp}°C, Foto Count: {count}'
    return info

def deleteFile(path):
    try:
        os.remove(video_path)
    except:
        pass

def makeVideo(image_dir, video_path, fps):
    deleteFile(video_path)
    images = []
    for filename in sorted(os.listdir(image_dir)):
        if filename.endswith('.jpg') or filename.endswith('.png'):
            with Image.open(os.path.join(image_dir, filename)) as img:
                img = img.resize((640, 480))
                images.append(np.array(img))
    imageio.mimsave(video_path, images, fps=fps, codec='libx264')
