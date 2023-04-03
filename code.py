# Minimal example displaying an image tiled across multiple RGB LED matrices.
# This is written for MatrixPortal and four 64x32 pixel matrices, but could
# be adapted to different boards and matrix combinations.
# No additional libraries required, just uses displayio.
# Image wales.bmp should be in CIRCUITPY root directory.

import board
import displayio
import gifio
import storage
import framebufferio
import rgbmatrix
import time
import wifi
import socketpool
from gif import GIFImage
import microcontroller
import adafruit_requests 

from digitalio import DigitalInOut, Direction


pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool)

GIF_URL = "http://192.168.1.10:8000"
print()
print("Fetching GIF from", GIF_URL)
r = requests.get(GIF_URL)
# print(r.content)

r.close()
print("-" * 40)
print("-" * 40)

bit_depth_value = 6 # 6 bits is the max
width_value = 64
height_value = 32

displayio.release_displays() # Release current display, we'll create our own

# Create RGB matrix object for a chain of four 64x32 matrices tiled into
# a single 128x64 pixel display -- two matrices across, two down, with the
# second row being flipped. width and height args are the combined size of
# all the tiled sub-matrices. tile arg is the number of rows of matrices in
# the chain (horizontal tiling is implicit from the width argument, doesn't
# need to be specified, but vertical tiling must be explicitly stated).
# The serpentine argument indicates whether alternate rows are flipped --
# cabling is easier this way, downside is colors may be slightly different
# when viewed off-angle. bit_depth and pins are same as other examples.
matrix = rgbmatrix.RGBMatrix(
    width=width_value, height=height_value, bit_depth=bit_depth_value,
    rgb_pins=[board.GP2, board.GP3, board.GP4, board.GP5, board.GP8, board.GP9],
    addr_pins=[board.GP10, board.GP16, board.GP18, board.GP20],
    clock_pin=board.GP11, latch_pin=board.GP12, output_enable_pin=board.GP13,
    doublebuffer=True)

'''

grid = displayio.TileGrid(gif.frames[0].bitmap, pixel_shader=gif.palette)
group.append(grid)
'''

# Associate matrix with a Display to use displayio features
DISPLAY = framebufferio.FramebufferDisplay(matrix, auto_refresh=True)
# GIF = gifio.OnDiskGif('images/mario.gif')
with open("images/mario.gif", 'rb') as f:
    GIF = GIFImage(f, bitmap=displayio.Bitmap, palette=displayio.Palette)

print('GIF OPENED!')
#start = time.monotonic()
#next_delay = GIF.next_frame()
#end = time.monotonic()
#overhead = end - start

GROUP = displayio.Group()
GROUP.append(displayio.TileGrid(
    #GIF.bitmap, pixel_shader=displayio.ColorConverter(input_colorspace=displayio.Colorspace.RGB565_SWAPPED),  
    GIF.frames[0].bitmap, pixel_shader=GIF.palette,
    width=width_value,
    height=height_value,
))

DISPLAY.show(GROUP)
DISPLAY.refresh()

while True:
    pass
    #sleep = next_delay - overhead
    #time.sleep(max(0, sleep))
    #next_delay = GIF.next_frame()


