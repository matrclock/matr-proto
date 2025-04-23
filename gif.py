import struct
import gc

def read_blockstream(f):
    while True:
        size_bytes = f.read(1)
        if not size_bytes:
            break  # Reached EOF or broken stream

        size = size_bytes[0]
        if size == 0:
            break

        chunk = f.read(size)
        if not chunk or len(chunk) != size:
            break  # Incomplete chunk, probably interrupted
        for b in chunk:
            yield b

class EndOfData(Exception):
    pass

class LZWDict:
    def __init__(self, code_size):
        self.code_size = code_size
        self.clear_code = 1 << code_size
        self.end_code = self.clear_code + 1
        self.codes = []
        self.clear()

    def clear(self):
        self.codes = []
        self.last = b''
        self.code_len = self.code_size + 1

    def decode(self, code):
        if code == self.clear_code:
            self.clear()
            return b''
        elif code == self.end_code:
            raise EndOfData()
        elif code < self.clear_code:
            value = bytes([code])
        elif code <= len(self.codes) + self.end_code:
            value = self.codes[code - self.end_code - 1]
        else:
            value = self.last + self.last[0:1]
        if self.last and len(self.codes) < 4096:
            self.codes.append(self.last + value[0:1])
        if (len(self.codes) + self.end_code + 1 >= 1 << self.code_len and self.code_len < 12):
            self.code_len += 1
        self.last = value
        return value

def lzw_decode(data, code_size):
    dictionary = LZWDict(code_size)
    bit = 0
    try: 
        byte = next(data)
        try:
            while True:
                code = 0
                for i in range(dictionary.code_len):
                    code |= ((byte >> bit) & 0x01) << i
                    bit += 1
                    if bit >= 8:
                        bit = 0
                        byte = next(data)
                yield dictionary.decode(code)
        except EndOfData:
            while True:
                next(data)
    except StopIteration:
        pass

class Extension:
    def __init__(self, f):
        self.type = f.read(1)[0]
        self.data = bytes(read_blockstream(f))
        gc.collect()

class Frame:
    def __init__(self, f, bitmap_class, palette_class, colors, delay):
        self.delay = delay
        self.x, self.y, self.w, self.h, flags = struct.unpack('<HHHHB', f.read(9))

        self.palette_flag = (flags & 0x80) != 0
        self.interlace_flag = (flags & 0x40) != 0
        self.palette_size = 1 << ((flags & 0x07) + 1)

        self.bitmap_class = bitmap_class
        self.palette_class = palette_class

        if self.palette_flag:
            self.read_palette(f)
            colors = self.palette_size
        else:
            self.palette = None  # fallback to global later

        self.min_code_sz = f.read(1)[0]
        self.bitmap = self.bitmap_class(self.w, self.h, colors)

        x = 0
        y = 0
        for decoded in lzw_decode(read_blockstream(f), self.min_code_sz):
            for byte in decoded:
                if y < self.h:
                    self.bitmap[x, y] = byte
                    x += 1
                    if x >= self.w:
                        x = 0
                        y += 1
        gc.collect()

    def read_palette(self, f):
        self.palette = self.palette_class(self.palette_size)
        for i in range(self.palette_size):
            rgb = f.read(3)
            self.palette[i] = (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]

class GIFImage:
    def __init__(self, f, bitmap, palette):
        self.bitmap_class = bitmap
        self.palette_class = palette
        self.read_header(f)
        if self.palette_flag:
            self.read_palette(f)
        self.has_more_frames = True
        self.frame = None

    def read_next_frame(self, f):
        if not self.has_more_frames:
            return

        delay = 0
        while True:
            block_type = f.read(1)[0]
            if block_type == 0x21:
                extension = Extension(f)
                if extension.type == 0xF9:  # Graphic Control Extension
                    delay = struct.unpack('<H', extension.data[1:3])[0] * 10  # CORRECTED
                del extension
                gc.collect()
            elif block_type == 0x2C:
                self.frame = Frame(f, self.bitmap_class, self.palette_class,
                                   self.palette_size, delay)
                if self.frame.palette is None:
                    self.frame.palette = self.palette  # fallback to global
                break
            elif block_type == 0x3B:
                self.has_more_frames = False
                break
            else:
                f.read(1)  # skip unknown label
                for _ in read_blockstream(f):
                    pass
                gc.collect()
        return delay

    def read_palette(self, f):
        self.palette = self.palette_class(self.palette_size)
        for i in range(self.palette_size):
            rgb = f.read(3)
            self.palette[i] = (rgb[0] << 16) | (rgb[1] << 8) | rgb[2]

    def read_header(self, f):
        header = f.read(6)
        if header not in {b'GIF87a', b'GIF89a'}:
            raise ValueError("Not a valid GIF")
        self.w, self.h, flags, self.background, self.aspect = struct.unpack('<HHBBB', f.read(7))
        self.palette_flag = (flags & 0x80) != 0
        self.color_bits = ((flags & 0x70) >> 4) + 1
        self.palette_size = 1 << ((flags & 0x07) + 1)
