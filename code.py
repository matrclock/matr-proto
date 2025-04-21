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
DISPLAY.show(GROUP)
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
    TILEGRID.pixel_shader = gif.palette

    collect()
    overhead = time.monotonic() - start
    time.sleep(max(0, (delay / 1000) - overhead))

def make_requests_session():
    ssl_context = ssl.create_default_context()
    return adafruit_requests.Session(SocketPool(radio), ssl_context=ssl_context)

MAX_IN_MEMORY_GIF = 10 * 1024  # 10 KB

def fetch_gif_stream(url, retries=3):
    for attempt in range(retries):
        try:
            print(f"Fetching: {url} (attempt {attempt + 1})")
            session = make_requests_session()
            response = session.get(url, stream=True)

            # Read just enough to decide whether to load in-memory
            chunk_iter = response.iter_content(512)
            data = bytearray()
            max_bytes = MAX_IN_MEMORY_GIF

            try:
                while len(data) < max_bytes:
                    chunk = next(chunk_iter)
                    if not chunk:
                        break
                    data.extend(chunk)
            except StopIteration:
                pass  # End of stream, it's safe to use in-memory

            if len(data) < max_bytes:
                print(f"Loaded {len(data)} bytes into memory")
                response.close()
                return io.BytesIO(data), None
            else:
                print("Too big for memory, falling back to streaming")
                # Put initial data back into the stream (prepend)
                full_iter = SafeIterStream(iter([bytes(data)]) + list(chunk_iter))
                return IterStream(full_iter), response

        except Exception as e:
            print(f"Fetch error: {e}")
            time.sleep(1)

    raise RuntimeError("Failed to fetch after retries")


def play_gif_stream(stream):
    gif = GIFImage(stream, bitmap=displayio.Bitmap, palette=displayio.Palette)
    while gif.has_more_frames:
        play_next_frame(gif, stream)

GIF_URL = "http://192.168.88.31:8080/clock.gif"

def get_and_play():
    try:
        f, response = fetch_gif_stream(GIF_URL)
    except RuntimeError as e:
        print('Failed to get GIF after retries:', str(e))
        print('Using local fallback file')
        f = open("images/clouds.gif", "rb")
        response = f

    try:
        GIF = GIFImage(f, bitmap=displayio.Bitmap, palette=displayio.Palette)
        while GIF.has_more_frames:
            play_next_frame(GIF, f)
    except Exception as e:
        print("Error playing GIF:", e)
    finally:
        try:
            response.close()
        except Exception as e:
            print("Error closing stream:", e)

# --- Main loop ---

print('RAM ON BOOT:', gc.mem_free())
while True:
    get_and_play()





