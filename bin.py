import struct
import gc

class BinFrame:
    def __init__(self, f, w, h, bitmap_class, palette):
        self.w = w
        self.h = h

        delay_bytes = f.read(2)
        if len(delay_bytes) < 2:
            raise ValueError("Failed to read frame delay")
        
        self.delay = struct.unpack('<H', delay_bytes)[0]

        # Read all pixel data at once (in large chunk)
        pixels = f.read(w * h)
        if len(pixels) < w * h:
            raise ValueError("Failed to read pixel data")

        self.bitmap = bitmap_class(w, h, 256)
        self.palette = palette

        # Directly assign pixels in a batch, avoiding unnecessary looping
        i = 0
        for y in range(h):
            for x in range(w):
                self.bitmap[x, y] = pixels[i]
                i += 1

class BINImage:
    def __init__(self, f, bitmap_class, palette_class, loop=False):
        self.f = f
        self.bitmap_class = bitmap_class
        self.palette_class = palette_class
        self.loop = loop
        self.finished = False

        # Read header
        header = f.read(3)
        self.w = header[0]
        self.h = header[1]
        self.frame_count = header[2]

        # Read fixed 256-color palette
        self.palette = palette_class(256)
        for i in range(256):
            r, g, b = struct.unpack('BBB', f.read(3))
            self.palette[i] = (r << 16) | (g << 8) | b

        self.frames_read = 0

    def read_next_frame(self):
        if self.finished:
            return None

        if self.frames_read >= self.frame_count:
            if self.loop:
                raise NotImplementedError("Looping not supported on non-seekable streams")
            else:
                self.finished = True
                return None

        try:
            frame = BinFrame(self.f, self.w, self.h, self.bitmap_class, self.palette)
            self.frames_read += 1
            return frame, frame.delay
        except Exception as e:
            print("Stream decode error:", e)
            self.finished = True
            return None
