from time import sleep
from utils import *
from config import RESOLUTION, SLEEP_TIME

createFolders()

try:
    while True:
        camera = getCamera(RESOLUTION)
        takeImage(camera)
        camera.close()
        sleep(SLEEP_TIME)

except Exception as e:
    myprint('Something went wrong')
    myprint(str(e))

finally:
    camera.close()
