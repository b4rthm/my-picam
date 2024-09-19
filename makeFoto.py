from time import sleep
from utils import *

SLEEP_TIME = 3600

try:
    while True:
        camera = getCamera('max')
        takeImage(camera)
        camera.close()
        sleep(SLEEP_TIME)

except Exception as e:
    myprint('Something went wrong')
    myprint(str(e))

finally:
    camera.close()
