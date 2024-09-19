from flask import Flask, send_file, request
from datetime import datetime
from time import sleep
from datetime import datetime
import os
from utils import *

PORT = 80
IMAGE_DIR = '/home/pi/fotos'
IMAGE_PATH = '/home/pi/latest.jpg'
VIDEO_PATH = '/home/pi/zeitraffer.mp4'

app = Flask(__name__)

def sendFile():
    try:
        myprint('Serving File to {}'.format(request.remote_addr))
        return send_file(IMAGE_PATH)
    except Exception as e:
        myprint(str(e))

@app.route('/')
def latest_image():
    return sendFile()

@app.route('/info')
def info():
    myprint('Serving Info to {}'.format(request.remote_addr))
    info = getInfo()
    myprint(info)
    return info

@app.route('/refresh')
def refresh():
    myprint('Refresh from {}'.format(request.remote_addr))
    camera = getCamera('max')
    takeImage(camera)
    camera.close()
    return sendFile()

@app.route('/myvideo')
def myvideo():
    fps = request.args.get('fps', default=5, type=int)
    makeVideo(IMAGE_DIR, VIDEO_PATH, fps)
    return send_file(VIDEO_PATH, mimetype='video/x-msvideo')

if __name__ == '__main__':
    myprint('Starting Server on Port {}'.format(PORT))
    app.run(host='0.0.0.0', port=PORT)
