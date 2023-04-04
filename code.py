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

GIF_URL = "http://192.168.1.10:8000"
r = requests.request("GET", GIF_URL)
IN_MEM_GIF = IterStream(r.iter_content(256))
#IN_MEM_GIF = io.BytesIO(r.content)
#r.close()

GIF = GIFImage(IN_MEM_GIF, bitmap=displayio.Bitmap, palette=displayio.Palette)

DISPLAY = framebufferio.FramebufferDisplay(MATRIX, auto_refresh=True)

GROUP = displayio.Group()
TILEGRID = displayio.TileGrid(
    displayio.Bitmap(64,32,1), pixel_shader=GIF.palette,
    width=1,
    height=1,
)

GROUP.append(TILEGRID)
DISPLAY.show(GROUP)
DISPLAY.refresh()



while True:
    while GIF.has_more_frames:

        start = time.monotonic()

        delay = GIF.read_next_frame(IN_MEM_GIF)
        TILEGRID.bitmap = GIF.frame.bitmap
        mem_before = gc.mem_free()
        gc.collect()
        print(mem_before, '>', gc.mem_free())

        end = time.monotonic()
        overhead = end - start
        print("overhead", overhead)

        time.sleep(max(0, (delay / 1000) - overhead))

       


        """
        r = requests.get(GIF_URL)
        print('fetching a rug')
        GIF = GIFImage(io.BytesIO(r.content), bitmap=displayio.Bitmap, palette=displayio.Palette)
        r.close()
        """





