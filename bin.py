import struct

class BINImage:
    def __init__(self, f, bitmap_class, palette_class, loop=False):
        self.f = f
        self.loop = loop
        self.finished = False

        # Read header
        header = f.read(4)
        if len(header) < 4:
            raise ValueError("Incomplete header")

        self.w = header[0]
        self.h = header[1]
        self.frame_count = struct.unpack('<H', header[2:4])[0]

        # Read fixed 256-color palette
        self.palette = palette_class(256)
        for i in range(256):
            rgb = f.read(3)
            if len(rgb) < 3:
                raise ValueError("Incomplete palette")
            r, g, b = struct.unpack('BBB', rgb)
            self.palette[i] = (r << 16) | (g << 8) | b

        # Two bitmaps: write into the back one while the front is displayed,
        # then swap. Avoids writing into a live/dirty-tracked bitmap.
        self.bitmap = bitmap_class(self.w, self.h, 256)
        self._back = bitmap_class(self.w, self.h, 256)
        self.frames_read = 0

    def reset(self):
        """Reposition stream past header+palette without reallocating bitmap/palette."""
        self.f.seek(4 + 256 * 3)
        self.frames_read = 0
        self.finished = False

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
            delay_bytes = self.f.read(2)
            if len(delay_bytes) < 2:
                raise ValueError("Failed to read frame delay")
            delay = struct.unpack('<H', delay_bytes)[0]

            # Fill the back bitmap (not currently displayed) to avoid
            # dirty-region overhead from writing into a live bitmap.
            w, h = self.w, self.h
            pixels = self.f.read(w * h)
            if len(pixels) < w * h:
                raise ValueError("Failed to read pixel data")
            i = 0
            for y in range(h):
                for x in range(w):
                    self._back[x, y] = pixels[i]
                    i += 1

            # Swap: the filled back buffer becomes the new front
            self.bitmap, self._back = self._back, self.bitmap
            self.frames_read += 1
            return self, delay
        except Exception as e:
            print("Stream decode error:", e)
            self.finished = True
            return None
