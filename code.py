import board
import displayio
import framebufferio
import rgbmatrix
import time
from wifi import radio
from socketpool import SocketPool
from gif import GIFImage
from lib.iter_stream import IterStream
import adafruit_requests
import gc
import ssl  # Import the ssl module

print('RAM ON BOOT:', gc.mem_free())

# Create an SSL context
ssl_context = ssl.create_default_context()

# Pass the SSL context to the adafruit_requests.Session
requests = adafruit_requests.Session(SocketPool(radio), ssl_context=ssl_context)

bit_depth_value = 6  # 6 bits is the max
width_value = 64
height_value = 32

displayio.release_displays()  # Release current display, we'll create our own

MATRIX = rgbmatrix.RGBMatrix(
    width=width_value, height=height_value, bit_depth=bit_depth_value,
    rgb_pins=[board.GP2, board.GP3, board.GP4, board.GP5, board.GP8, board.GP9],
    addr_pins=[board.GP10, board.GP16, board.GP18, board.GP20],
    clock_pin=board.GP11, latch_pin=board.GP12, output_enable_pin=board.GP13,
    doublebuffer=True)

DISPLAY = framebufferio.FramebufferDisplay(MATRIX, auto_refresh=True)

GROUP = displayio.Group()
TILEGRID = displayio.TileGrid(
    displayio.Bitmap(64, 32, 1), pixel_shader=displayio.Palette(1),
    width=1,
    height=1,
)

GROUP.append(TILEGRID)
DISPLAY.show(GROUP)
DISPLAY.refresh()

def collect():
    mem_before = gc.mem_free()
    gc.collect()
    # print(mem_before, '>', gc.mem_free())

def play_next_frame(gif, gif_stream):
    start = time.monotonic()

    delay = 0
    delay = gif.read_next_frame(gif_stream)
    TILEGRID.bitmap = gif.frame.bitmap
    TILEGRID.pixel_shader = gif.palette

    collect()
    end = time.monotonic()
    overhead = end - start

    print(delay)
    time.sleep(max(0, (delay / 1000) - overhead))

def get_and_play():
    GIF_URL = "https://funkadelic.net/clock.gif"

    try:
        r = requests.request("GET", GIF_URL)
        f = IterStream(r.iter_content(256))
    except RuntimeError as e:
        print('Failed to get GIF', str(e))
        print('Error getting GIF, using local file')

        f = open("images/clouds.gif", "rb")
        r = f

    GIF = GIFImage(f, bitmap=displayio.Bitmap, palette=displayio.Palette)
    while GIF.has_more_frames:
        play_next_frame(GIF, f)
    r.close()

while True:
    get_and_play()




