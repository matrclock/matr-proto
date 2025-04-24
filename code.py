import board
import displayio
import framebufferio
import rgbmatrix
import time
from wifi import radio
from socketpool import SocketPool
from gif import GIFImage
from lib.safe_iter_stream import SafeIterStream
from lib.iter_stream import IterStream
import adafruit_requests
import gc
import ssl
import io

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

def play_next_frame(gif, gif_stream):
    start = time.monotonic()
    delay = gif.read_next_frame(gif_stream)
    TILEGRID.bitmap = gif.frame.bitmap
    TILEGRID.pixel_shader = gif.frame.palette
    overhead = time.monotonic() - start
    print("Frame delay:", delay, "Overhead:", overhead)
    time.sleep(max(0, (delay / 1000) - overhead))

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
def fetch_gif_stream(url, retries=3):
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

GIF_URL = "http://192.168.88.31:8080/clock.gif"

def fetch_gif_or_fallback():
    try:
        f, response, session = fetch_gif_stream(GIF_URL)
        return f, response, session
    except RuntimeError as e:
        print('Failed to get GIF after retries:', str(e))
        print('Using local fallback file')
        f = open("images/clouds.gif", "rb")
        return f, None, None

def play_gif_stream(f, response, session):
    try:
        gif = GIFImage(f, displayio.Bitmap, displayio.Palette)
        start_time = time.monotonic()

        # If the GIF has only one frame, show it for 10 seconds
        gif.read_next_frame(f)
        TILEGRID.bitmap = gif.frame.bitmap
        TILEGRID.pixel_shader = gif.frame.palette

        if not gif.has_more_frames:
            print("Single-frame GIF detected. Holding for 10 seconds...")
            time.sleep(10)
            return

        # Otherwise, play all frames in a loop until 10 seconds have passed
        while True:
            while gif.has_more_frames:
                play_next_frame(gif, f)

            elapsed = time.monotonic() - start_time
            print("Elapsed time:", elapsed)
            if elapsed >= 10:
                break

            try:
                f.seek(0)
                gif = GIFImage(f, displayio.Bitmap, displayio.Palette)
            except Exception as e:
                print("Error restarting GIF for loop:", e)
                break

    except Exception as e:
        print("Error playing GIF:", e)
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
        gc.collect()

# --- Main loop ---

print('RAM ON BOOT:', gc.mem_free())
while True:
    f, response, session = fetch_gif_or_fallback()
    play_gif_stream(f, response, session)
