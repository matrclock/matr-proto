import board
import displayio
import framebufferio
import rgbmatrix
import time
from wifi import radio
from socketpool import SocketPool
from bin import BINImage  # Import your new BIN decoder
from lib.safe_iter_stream import SafeIterStream
from lib.iter_stream import IterStream
import adafruit_requests
import gc
import ssl
import io
import os
import wifi
import supervisor

from microcontroller import watchdog as w
from watchdog import WatchDogMode
w.timeout=7.9 # Set a timeout of 2.5 seconds
w.mode = WatchDogMode.RESET
w.feed()

WIFI_SSID = os.getenv("CIRCUITPY_WIFI_SSID")
WIFI_PASSWORD = os.getenv("CIRCUITPY_WIFI_PASSWORD")
BIN_URL_DEV = os.getenv("BIN_URL_DEV")
BIN_URL_PROD = os.getenv("BIN_URL_PROD")
print(WIFI_PASSWORD)

# --- Display setup ---

bit_depth_value = 6  # Max for RGBMatrix
width_value = 64
height_value = 32

displayio.release_displays()

MATRIX = rgbmatrix.RGBMatrix(
    width=width_value, height=height_value, bit_depth=bit_depth_value,
    rgb_pins=[board.GP2, board.GP3, board.GP4, board.GP5, board.GP8, board.GP9],
    addr_pins=[board.GP10, board.GP16, board.GP18, board.GP20],
    clock_pin=board.GP11, latch_pin=board.GP12, output_enable_pin=board.GP13,
    doublebuffer=True
)

DISPLAY = framebufferio.FramebufferDisplay(MATRIX, auto_refresh=True)

GROUP = displayio.Group()
TILEGRID = displayio.TileGrid(
    displayio.Bitmap(width_value, height_value, 1), pixel_shader=displayio.Palette(1)
)
GROUP.append(TILEGRID)
DISPLAY.root_group = GROUP
DISPLAY.refresh()

# --- Utilities ---

def collect():
    mem_before = gc.mem_free()
    gc.collect()
    print(mem_before, '>', gc.mem_free())

# Add global variables to keep track of total overhead and frame count
total_overhead = 0
frame_count = 0

total_overhead = 0
frame_count = 0

def play_next_frame(bin_image):
    w.feed()  # Feed the watchdog
    global total_overhead, frame_count

    start = time.monotonic()

    # Read next frame and handle the case where it's None
    result = bin_image.read_next_frame()

    if result is None:
        print("End of stream or no frame available.")
        return False  # Signal to stop

    # Unpack the frame and delay
    frame, delay = result

    TILEGRID.bitmap = frame.bitmap  # or copy pixels
    TILEGRID.pixel_shader = bin_image.palette

    overhead = time.monotonic() - start
    total_overhead += overhead  # Accumulate the total overhead
    frame_count += 1  # Increment frame count

    # Calculate average overhead and print debug info
    if frame_count % 20 == 0 or delay > 1000:
        average_overhead = total_overhead / frame_count  # Calculate average overhead in seconds
        print("DelayMS:", delay, 
              "AverageOverheadMS:", average_overhead * 1000)
        
    actualDelay = max(0, (delay / 1000) - overhead)
    
    while actualDelay > 0:
        if actualDelay > 5:
            print("Long delay, feeding watchdog every 5 seconds")
            w.feed()  # Feed the watchdog
            time.sleep(5)
            actualDelay = actualDelay - 5
        else:
            w.feed()  # Feed the watchdog
            time.sleep(actualDelay)
            actualDelay = 0

    return True

SOCKET_POOL = SocketPool(radio)

def socket_debug():
    try:
        print(f"[DEBUG] Open sockets: {len(SOCKET_POOL._sockets)}")
    except Exception as e:
        print("[DEBUG] Socket count error:", e)

def make_requests_session():
    ssl_context = ssl.create_default_context()
    return adafruit_requests.Session(SOCKET_POOL, ssl_context=ssl_context)

def chain(first, second):
    for item in first:
        yield item
    for item in second:
        yield item

MAX_IN_MEMORY_GIF = 10 * 1024  # 10 KB

session_open_count = 0
response_open_count = 0
response_close_count = 0

def fetch_bin_stream(url, retries=3):

    global session_open_count, response_open_count, response_close_count
    for attempt in range(retries):
        session = None
        response = None
        print(f"[DEBUG] Opened Sessions: {session_open_count}, Responses Opened: {response_open_count}, Closed: {response_close_count}")

        try:
            print(f"Fetching: {url} (attempt {attempt + 1})")
            session = make_requests_session()
            session_open_count += 1

            response = session.get(url, stream=True)
            response_open_count += 1

            chunk_iter = response.iter_content(512)
            data = bytearray()

            while len(data) < MAX_IN_MEMORY_GIF:
                try:
                    chunk = next(chunk_iter)
                    if not chunk:
                        break
                    data.extend(chunk)
                except StopIteration:
                    break

            if len(data) < MAX_IN_MEMORY_GIF:
                print(f"Loaded {len(data)} bytes into memory")
                response.close()
                response_close_count += 1
                del session
                gc.collect()
                return io.BytesIO(data), None, None
            else:
                print("Too big for memory, falling back to streaming")
                collect()
                full_iter = SafeIterStream(chain([bytes(data)], chunk_iter))
                return IterStream(full_iter), response, session

        except Exception as e:
            print(f"Fetch error: {e}")
            try:
                if response:
                    response.close()
                    response_close_count += 1
            except Exception as close_err:
                print("Error closing response:", close_err)
            try:
                if session:
                    del session
            except:
                pass
            gc.collect()
            time.sleep(1)

    raise RuntimeError("Failed to fetch after retries")

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

def fetch_bin_or_fallback():
    check_wifi()

    if supervisor.runtime.usb_connected is False:
        ENV="production"
    else: 
        ENV="development"

    if ENV == "production":
        # Production URL
        BIN_URL = BIN_URL_PROD
    else:
        # Development URL
        BIN_URL = BIN_URL_DEV

    try:
        f, response, session = fetch_bin_stream(BIN_URL)
        return f, response, session
    except RuntimeError as e:
        print('Failed to get BIN after retries:', str(e))
        print('Using local fallback file')
        f = open("images/clouds.bin", "rb")
        return f, None, None

def play_bin_stream(f, response, session):
    print("Playing BIN stream...")
    print("RAM before playing:", gc.mem_free())

    try:
        collect()

        bin_image = BINImage(f, displayio.Bitmap, displayio.Palette, loop=False)
        start_time = time.monotonic()
        while True:
            ok = play_next_frame(bin_image)
            if not ok:
                print("Finished streaming all frames.")
                break

    except Exception as e:
        print("Error playing BIN:", e)
    finally:
        if response:
            try:
                response.close()
                global response_close_count
                response_close_count += 1
            except Exception as e:
                print("Error closing stream:", e)
        if session:
            try:
                del session
            except Exception as e:
                print("Error deleting session:", e)
        collect()

# --- Main loop ---

print('RAM ON BOOT:', gc.mem_free())
while True:
    f, response, session = fetch_bin_or_fallback()
    play_bin_stream(f, response, session)
