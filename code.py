import board
import displayio
import framebufferio
import rgbmatrix
import time
from bin import BINImage  # Import your new BIN decoder
from lib.safe_iter_stream import SafeIterStream
from lib.iter_stream import IterStream
import io
import gc
from lib.utils import get_url, make_requests_session, check_wifi, collect, cleanup_session
from lib.time import set_rtc

from microcontroller import watchdog as w
from watchdog import WatchDogMode
w.timeout=7.9 # Set a timeout of 2.5 seconds
w.mode = WatchDogMode.RESET
w.feed()


MAX_IN_MEMORY_GIF = 10 * 1024  # 10 KB

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

# Add global variables to keep track of total overhead and frame count
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
        
    actualDelay = max(0.01, (delay / 1000) - overhead)
    
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

def chain(first, second):
    for item in first:
        yield item
    for item in second:
        yield item

def fetch_bin_stream(url, retries=3):

    for attempt in range(retries):
        session = None
        response = None

        try:
            print(f"Fetching: {url} (attempt {attempt + 1})")
            session = make_requests_session()

            response = session.get(url, stream=True)

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

    raise RuntimeError("Failed to fetch after retries")

def fetch_bin():
    url = get_url()
    try:
        f, response, session = fetch_bin_stream(url + "/clock.bin")
        return f, response, session
    except RuntimeError as e:
        print('Failed to get BIN after retries:', str(e))
        print('Using local fallback file')
        f = open("images/clouds.bin", "rb")
        return f, None, None

def play_bin_stream(f, response, session):
    print("RAM before playing BIN:", gc.mem_free())

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

def start_loop():
    print("Starting main loop...")
    while True:
        try:
            check_wifi()
            f, response, session = fetch_bin()
            play_bin_stream(f, response, session)
        except Exception as e:
            print("Error in main loop:", e)
            time.sleep(1)  # Wait before retrying
        finally:
            cleanup_session(response, session)

def main():
    print('RAM ON BOOT:', gc.mem_free())
    print("URL:", get_url())
    set_rtc()
    start_loop()

main()


