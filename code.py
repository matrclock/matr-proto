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
import os
from lib.utils import get_url, make_requests_session, check_wifi, collect, cleanup_session, is_dev
from lib.time import set_rtc, get_rtc, get_server_time
import microcontroller

from microcontroller import watchdog as w
from watchdog import WatchDogMode

if not is_dev():
    w.timeout=7.9 # Set a timeout of 2.5 seconds
    w.mode = WatchDogMode.RESET
    w.feed()
else:
    print("DEV MODE, not setting watchdog")


# Overclock
microcontroller.cpus[0].frequency = 200000000
microcontroller.cpus[1].frequency = 200000000

MAX_IN_MEMORY_GIF = 10 * 1024  # 30 KB
FORCE_STREAMING = True  # Force streaming even for images that fit in memory

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

total_overhead = 0
frame_count = 0

def play_next_frame(bin_image):
    w.feed()
    global total_overhead, frame_count

    start = time.monotonic()

    result = bin_image.read_next_frame()

    if result is None:
        return False

    frame, delay = result

    overhead = time.monotonic() - start
    total_overhead += overhead
    frame_count += 1

    if frame_count % 20 == 0 or delay > 1000:
        if delay > 500:
            print("Collect garbage during long delay")
            collect()
        average_overhead = total_overhead / frame_count
        print("DelayMS:", delay,
              "AverageOverheadMS:", average_overhead * 1000)

    actualDelay = (delay / 1000) - overhead

    if actualDelay <= 0:
        # Decode took longer than the frame's display time — skip showing it
        return True

    TILEGRID.bitmap = frame.bitmap
    TILEGRID.pixel_shader = bin_image.palette

    # Prefetch next frame's data from the network during idle sleep time
    if hasattr(bin_image.f, 'prefetch'):
        bin_image.f.prefetch(2050)

    while actualDelay > 0:
        w.feed()

        if actualDelay > 5:
            print("Long delay, feeding watchdog every 5 seconds")
            time.sleep(5)
            actualDelay = actualDelay - 5
        else:
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

            headers = {
                "matr-time": str(time.mktime(get_rtc())),
                "matr-id": os.getenv("ID"),
                "matr-location": os.getenv("LOCATION"),
            }

            response = session.request(
                method="GET",
                headers=headers,
                url=url,
                stream=True)

            if response.status_code != 200:
                raise ValueError(f"Bad status: {response.status_code}")

            chunk_iter = response.iter_content(2050)  # 2-byte delay + 64*32 pixels = one frame per chunk

            if FORCE_STREAMING:
                # Skip buffering entirely — save up to MAX_IN_MEMORY_GIF bytes of RAM
                collect()
                return IterStream(SafeIterStream(chunk_iter)), response, session

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
                buf = io.BytesIO(data)
                del data
                collect()
                return buf, response, session
            else:
                print("Too big for memory, streaming. Bytes:", len(data))
                # Pass data directly (not bytes(data)) to avoid a redundant copy
                full_iter = SafeIterStream(chain([data], chunk_iter))
                collect()
                return IterStream(full_iter), response, session

        except Exception as e:
            print(f"Fetch error: {e}")
            cleanup_session(response, session)

    raise RuntimeError("Failed to fetch after retries")

def fetch_bin():
    url = get_url()
    try:
        f, response, session = fetch_bin_stream(url + "/next")
        return f, response, session
    except RuntimeError as e:
        print('Failed to get BIN after retries:', str(e))
        print('Using local fallback file')
        f = open("images/clouds.bin", "rb")
        return f, None, None

def play_bin_stream(f, response, session):
    print("RAM before playing BIN:", gc.mem_free())

    try:
        bin_image = BINImage(f, displayio.Bitmap, displayio.Palette, loop=False)
        start_time = time.monotonic()
        dwell = float(response.headers.get("matr-dwell"))

        deadline = start_time + dwell

        while True:
            ok = play_next_frame(bin_image)
            now = time.monotonic()
            remaining_time = deadline - now
            if not ok:
                if remaining_time > 0:
                    # Reset without reallocating bitmap/palette
                    bin_image.reset()
                    continue

                print("Finished playing all frames.")
                break

    except Exception as e:
        print("Error playing BIN:", e)
    finally:
        gc.collect()

def start_loop():
    print("Starting main loop...")
    while True:
        # FIX 3: declare response and session before try block so finally can always see them
        response = None
        session = None
        try:
            # FIX 7: check wifi on every iteration so dropped connections are recovered
            try:
                check_wifi()
            except Exception as e:
                print("WiFi check failed:", e)

            start = time.monotonic()
            f, response, session = fetch_bin()
            print("Fetched BIN in", time.monotonic() - start, "seconds")
            play_bin_stream(f, response, session)
        except Exception as e:
            print("Error in main loop:", e)
            time.sleep(1)
        finally:
            cleanup_session(response, session)

def main():
    print('RAM ON BOOT:', gc.mem_free())
    print("URL:", get_url())

    #try:
    #    serverTime = get_server_time()
    #    set_rtc(serverTime)
    #except Exception as e:
    #    print("Error setting RTC:", e)

    start_loop()

main()
