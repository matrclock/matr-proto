# Minimal example displaying an image tiled across multiple RGB LED matrices.
# This is written for MatrixPortal and four 64x32 pixel matrices, but could
# be adapted to different boards and matrix combinations.
# No additional libraries required, just uses displayio.
# Image wales.bmp should be in CIRCUITPY root directory.

import board
import displayio
import gifio
import framebufferio
import rgbmatrix
import time
from digitalio import DigitalInOut, Direction



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


# Associate matrix with a Display to use displayio features
DISPLAY = framebufferio.FramebufferDisplay(matrix, auto_refresh=True,
                                           rotation=180)
# Right side up
DISPLAY.rotation = 0


# Load GIF image, create Group and TileGrid to hold it
GIF = gifio.OnDiskGif('images/mario.gif')

start = time.monotonic()
next_delay = GIF.next_frame()
end = time.monotonic()
overhead = end - start

GROUP = displayio.Group()
"""
GROUP.append(displayio.TileGrid(
    BITMAP,
    pixel_shader=getattr(BITMAP, 'pixel_shader', displayio.ColorConverter()),
    width=1,
    height=1,
    tile_width=BITMAP.width,
    tile_height=BITMAP.height))
"""
GROUP.append(displayio.TileGrid(
    GIF.bitmap,
    pixel_shader=displayio.ColorConverter(
        input_colorspace=displayio.Colorspace.RGB565_SWAPPED
    ),    
    width=width_value,
    height=height_value,
))

DISPLAY.show(GROUP)
DISPLAY.refresh()

i = 0
# Nothing interactive, just hold the image there
while True:
    # Sleep for the frame delay specified by the GIF,
    # minus the overhead measured to advance between frames.
    sleep = next_delay - overhead
    print("Sleeping:", sleep, i)
    time.sleep(max(0, sleep))
    next_delay = GIF.next_frame()
    i = i+1


