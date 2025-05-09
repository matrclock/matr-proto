import os
import supervisor
import adafruit_requests
import ssl
from socketpool import SocketPool
from wifi import radio
import wifi
import gc
import time

SOCKET_POOL = SocketPool(radio)
URL_DEV = os.getenv("URL_DEV") 
URL_PROD = os.getenv("URL_PROD")
WIFI_SSID = os.getenv("CIRCUITPY_WIFI_SSID")
WIFI_PASSWORD = os.getenv("CIRCUITPY_WIFI_PASSWORD")

def make_requests_session():
    ssl_context = ssl.create_default_context()
    return adafruit_requests.Session(SOCKET_POOL, ssl_context=ssl_context)

def cleanup_session(response, session):
    if response:
        try:
            response.close()
        except Exception as e:
            print("Error closing stream:", e)
    if session:
        try:
            del session
        except Exception as e:
            print("Error deleting session:", e)
    collect()
    time.sleep(0.01)

def check_wifi():
    print("Checking WiFi connection...")
    gateway = wifi.radio.ipv4_gateway
    rtt = wifi.radio.ping(gateway, timeout=1)
    if rtt > 1:
        print("WiFi connection poor, trying to reconnect...")
        wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
        print("Reconnected to WiFi")
    else:
        print("WiFi connection is good")
        print("RTT:", rtt, "s")

def get_url():
    if supervisor.runtime.usb_connected:
        return URL_DEV
    else:
        return URL_PROD
    
def collect():
    mem_before = gc.mem_free()
    gc.collect()
    print(mem_before, '>', gc.mem_free())