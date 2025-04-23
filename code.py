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
DISPLAY.root_group = GROUP  # Updated for CP9+
DISPLAY.refresh()

# --- Utilities ---

def collect(tag=""):
    mem_before = gc.mem_free()
    gc.collect()
    mem_after = gc.mem_free()
    print(f"{tag} GC: {mem_before} > {mem_after}")

def play_next_frame(gif, gif_stream):
    start = time.monotonic()
    delay = gif.read_next_frame(gif_stream)
    TILEGRID.bitmap = gif.frame.bitmap
    TILEGRID.pixel_shader = gif.palette
    overhead = time.monotonic() - start
    time.sleep(max(0, (delay / 1000) - overhead))

def make_requests_session():
    ssl_context = ssl.create_default_context()
    return adafruit_requests.Session(SocketPool(radio), ssl_context=ssl_context)

def chain(first, second):
    for item in first:
        yield item
    for item in second:
        yield item

def reset_wifi():
    print("Resetting WiFi...")
    try:
        radio.stop_station()
    except Exception as e:
        print("stop_station error:", e)
    time.sleep(0.5)
    try:
        radio.start_station()
    except Exception as e:
        print("start_station error:", e)
    gc.collect()

MAX_IN_MEMORY_GIF = 10 * 1024  # 10 KB

def fetch_gif_stream(url, retries=3):
    for attempt in range(retries):
        session = None
        response = None
        try:
            print(f"Fetching: {url} (attempt {attempt + 1})")
            session = make_requests_session()
            response = session.get(url, stream=True)

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
                pass  # End of stream, safe to use in-memory

            if len(data) < max_bytes:
                print(f"Loaded {len(data)} bytes into memory")
                response.close()
                del session
                return io.BytesIO(data), None
            else:
                print("Too big for memory, falling back to streaming")
                full_iter = SafeIterStream(chain([bytes(data)], chunk_iter))
                return IterStream(full_iter), response

        except Exception as e:
            print(f"Fetch error: {e}")
            if "sockets" in str(e).lower():
                reset_wifi()
            time.sleep(1)
            try:
                if response:
                    response.close()
            except:
                pass
            try:
                if session:
                    del session
            except:
                pass
            gc.collect()

    raise RuntimeError("Failed to fetch after retries")

GIF_URL = "http://192.168.88.31:8080/clock.gif"

def fetch_gif_or_fallback():
    try:
        f, response = fetch_gif_stream(GIF_URL)
        return f, response
    except RuntimeError as e:
        print('Failed to get GIF after retries:', str(e))
        print('Using local fallback file')
        f = open("images/clouds.gif", "rb")
        return f, None

def play_gif_stream(f, response):
    try:
        gif = GIFImage(f, bitmap=displayio.Bitmap, palette=displayio.Palette)
        while gif.has_more_frames:
            play_next_frame(gif, f)
    except Exception as e:
        print("Error playing GIF:", e)
    finally:
        try:
            if response:
                response.close()
        except Exception as e:
            print("Error closing stream:", e)
        gc.collect()

# --- Main loop ---

print('RAM ON BOOT:', gc.mem_free())

while True:
    f, response = fetch_gif_or_fallback()
    play_gif_stream(f, response)
    collect("After playback")
