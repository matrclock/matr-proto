# It's important not to load this until we absolutely need it
# as it uses a lot of memory and slows down animations

import sys
import busio
import board
import adafruit_ds3231
import time
i2c = busio.I2C(board.GP7, board.GP6)
rtc = adafruit_ds3231.DS3231(i2c)
from lib.utils import get_url, make_requests_session, cleanup_session

def get_server_time():
    session = make_requests_session()
    # Endpoint is invalid, but that's ok. We only need the header
    response = session.get(get_url() + "/") 
    data = int(response.headers["matr-time"])
    cleanup_session(response, session)
    return data

# Function to grab clock.json, parse JSON, and set the RTC using the ISO8601 timestamp in the time field
def set_rtc(timestamp):
    try:
        newTime = time.localtime(timestamp)
        print("Setting RTC to:", newTime)
        rtc.datetime = newTime
    except Exception as e:
        print("Error setting RTC:", e)
    

def get_rtc():
    return rtc.datetime

