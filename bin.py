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

        # Single reusable bitmap — avoids per-frame allocation
        self.bitmap = bitmap_class(self.w, self.h, 256)
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

            # Read one row at a time (64 bytes) into the shared bitmap
            # instead of buffering the full frame (2048 bytes) before writing
            w, h = self.w, self.h
            for y in range(h):
                row = self.f.read(w)
                if len(row) < w:
                    raise ValueError("Failed to read pixel row")
                for x in range(w):
                    self.bitmap[x, y] = row[x]

            self.frames_read += 1
            return self, delay
        except Exception as e:
            print("Stream decode error:", e)
            self.finished = True
            return None
