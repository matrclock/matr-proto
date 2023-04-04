import board
import displayio
import framebufferio
import rgbmatrix
import time
import struct
from wifi import radio
from socketpool import SocketPool
from gif import GIFImage
from lib.iter_stream import IterStream
import adafruit_requests 
import gc
print('RAM ON BOOT:', gc.mem_free())

requests = adafruit_requests.Session(SocketPool(radio))

bit_depth_value = 6 # 6 bits is the max
width_value = 64
height_value = 32

displayio.release_displays() # Release current display, we'll create our own

MATRIX = rgbmatrix.RGBMatrix(
    width=width_value, height=height_value, bit_depth=bit_depth_value,
    rgb_pins=[board.GP2, board.GP3, board.GP4, board.GP5, board.GP8, board.GP9],
    addr_pins=[board.GP10, board.GP16, board.GP18, board.GP20],
    clock_pin=board.GP11, latch_pin=board.GP12, output_enable_pin=board.GP13,
    doublebuffer=True)

# Associate matrix with a Display to use displayio features


#IN_MEM_GIF = io.BytesIO(r.content)
#r.close()


DISPLAY = framebufferio.FramebufferDisplay(MATRIX, auto_refresh=True)

GROUP = displayio.Group()
TILEGRID = displayio.TileGrid(
    displayio.Bitmap(64,32,1), pixel_shader=displayio.Palette(1),
    width=1,
    height=1,
)

GROUP.append(TILEGRID)
DISPLAY.show(GROUP)
DISPLAY.refresh()

def play_next_frame(gif, gif_stream):
    start = time.monotonic()

    delay = gif.read_next_frame(gif_stream)
    TILEGRID.bitmap = gif.frame.bitmap
    TILEGRID.pixel_shader = gif.palette
    mem_before = gc.mem_free()
    gc.collect()
    print(mem_before, '>', gc.mem_free())

    end = time.monotonic()
    overhead = end - start
    print("overhead", overhead)

    time.sleep(max(0, (delay / 1000) - overhead))

def get_and_play():
    GIF_URL = "http://192.168.1.10:8000"
    r = requests.request("GET", GIF_URL)
    GIF_STREAM = IterStream(r.iter_content(256))
    GIF = GIFImage(GIF_STREAM, bitmap=displayio.Bitmap, palette=displayio.Palette)
    while GIF.has_more_frames:
        play_next_frame(GIF, GIF_STREAM)
    r.close()

while True:
    get_and_play()




