"""Facebook Gorilla Time-Series Compression Codec.

Implements:
1. Low-level BitWriter and BitReader for variable-length bit packing
2. Delta-of-delta timestamp encoding and decoding
3. IEEE 754 Float64 XOR value compression and decompression
"""

import struct
from typing import List, Tuple


class BitWriter:
    """Helper class to write arbitrary bit streams."""

    def __init__(self):
        self.buffer = bytearray()
        self.current_byte = 0
        self.bit_count = 0  # Number of bits currently filled in current_byte (0..7)

    def write_bit(self, bit: int) -> None:
        """Write a single bit (0 or 1)."""
        self.current_byte = (self.current_byte << 1) | (1 if bit else 0)
        self.bit_count += 1
        if self.bit_count == 8:
            self.buffer.append(self.current_byte)
            self.current_byte = 0
            self.bit_count = 0

    def write_bits(self, value: int, num_bits: int) -> None:
        """Write num_bits from value (most significant bits first)."""
        for i in range(num_bits - 1, -1, -1):
            self.write_bit((value >> i) & 1)

    def flush(self) -> bytes:
        """Pad remaining bits with zeros and return byte buffer."""
        out = bytearray(self.buffer)
        if self.bit_count > 0:
            out.append(self.current_byte << (8 - self.bit_count))
        return bytes(out)


class BitReader:
    """Helper class to read arbitrary bit streams."""

    def __init__(self, data: bytes):
        self.data = data
        self.byte_index = 0
        self.bit_index = 0  # Next bit to read in current byte (0..7, from MSB to LSB)

    def read_bit(self) -> int:
        """Read a single bit (0 or 1)."""
        if self.byte_index >= len(self.data):
            return 0
        current_byte = self.data[self.byte_index]
        bit = (current_byte >> (7 - self.bit_index)) & 1
        self.bit_index += 1
        if self.bit_index == 8:
            self.byte_index += 1
            self.bit_index = 0
        return bit

    def read_bits(self, num_bits: int) -> int:
        """Read num_bits as an unsigned integer."""
        val = 0
        for _ in range(num_bits):
            val = (val << 1) | self.read_bit()
        return val


def float_to_bits(f: float) -> int:
    return struct.unpack('>Q', struct.pack('>d', f))[0]


def bits_to_float(b: int) -> float:
    return struct.unpack('>d', struct.pack('>Q', b))[0]


def count_leading_zeros(val: int) -> int:
    if val == 0:
        return 64
    return 64 - val.bit_length()


def count_trailing_zeros(val: int) -> int:
    if val == 0:
        return 64
    return (val & -val).bit_length() - 1


class GorillaEncoder:
    """Encodes a sequence of (timestamp, value) pairs using Gorilla compression."""

    def __init__(self):
        self.writer = BitWriter()
        self.count = 0
        self.prev_time = 0
        self.prev_delta = 0
        self.prev_val_bits = 0
        self.prev_leading = 64
        self.prev_trailing = 64

    def compress_point(self, timestamp: int, value: float) -> None:
        val_bits = float_to_bits(value)

        if self.count == 0:
            # First point: store timestamp (32 bits or 64 bits) and float (64 bits) raw
            self.prev_time = timestamp
            self.prev_val_bits = val_bits
            self.writer.write_bits(timestamp, 64)
            self.writer.write_bits(val_bits, 64)
            self.count += 1
            return

        if self.count == 1:
            # Second point: store delta directly
            self.prev_delta = timestamp - self.prev_time
            self.prev_time = timestamp
            self.writer.write_bits(self.prev_delta, 14)
            self._compress_value(val_bits)
            self.count += 1
            return

        # Subsequent points: delta-of-delta timestamp
        delta = timestamp - self.prev_time
        dod = delta - self.prev_delta
        self.prev_time = timestamp
        self.prev_delta = delta

        # Encode DoD
        if dod == 0:
            self.writer.write_bit(0)
        elif -63 <= dod <= 64:
            self.writer.write_bits(0b10, 2)
            self.writer.write_bits(dod + 63, 7)
        elif -255 <= dod <= 256:
            self.writer.write_bits(0b110, 3)
            self.writer.write_bits(dod + 255, 9)
        elif -2047 <= dod <= 2048:
            self.writer.write_bits(0b1110, 4)
            self.writer.write_bits(dod + 2047, 12)
        else:
            self.writer.write_bits(0b1111, 4)
            self.writer.write_bits(dod & 0xFFFFFFFF, 32)

        # Compress float value
        self._compress_value(val_bits)
        self.count += 1

    def _compress_value(self, val_bits: int) -> None:
        xor = val_bits ^ self.prev_val_bits
        self.prev_val_bits = val_bits

        if xor == 0:
            self.writer.write_bit(0)
            return

        self.writer.write_bit(1)
        leading = count_leading_zeros(xor)
        trailing = count_trailing_zeros(xor)

        # Check if we can reuse previous window
        if leading >= self.prev_leading and trailing >= self.prev_trailing:
            self.writer.write_bit(0)
            length = 64 - self.prev_leading - self.prev_trailing
            bits = (xor >> self.prev_trailing) & ((1 << length) - 1)
            self.writer.write_bits(bits, length)
        else:
            self.writer.write_bit(1)
            # Store leading zeros in 5 bits (max 31; clamp if > 31)
            leading_to_store = min(leading, 31)
            self.writer.write_bits(leading_to_store, 5)
            length = 64 - leading_to_store - trailing
            self.writer.write_bits(length, 6)
            bits = (xor >> trailing) & ((1 << length) - 1)
            self.writer.write_bits(bits, length)
            self.prev_leading = leading_to_store
            self.prev_trailing = trailing

    def finish(self) -> bytes:
        return self.writer.flush()


class GorillaDecoder:
    """Decodes Gorilla-compressed byte stream back into (timestamp, value) pairs."""

    def __init__(self, data: bytes, count: int):
        self.reader = BitReader(data)
        self.total_count = count
        self.prev_time = 0
        self.prev_delta = 0
        self.prev_val_bits = 0
        self.prev_leading = 0
        self.prev_trailing = 0

    def decode_all(self) -> List[Tuple[int, float]]:
        points: List[Tuple[int, float]] = []
        if self.total_count <= 0:
            return points

        # Point 1: 64-bit timestamp, 64-bit value
        self.prev_time = self.reader.read_bits(64)
        self.prev_val_bits = self.reader.read_bits(64)
        points.append((self.prev_time, bits_to_float(self.prev_val_bits)))
        if self.total_count == 1:
            return points

        # Point 2: 14-bit delta + value
        self.prev_delta = self.reader.read_bits(14)
        self.prev_time += self.prev_delta
        val = self._decode_value()
        points.append((self.prev_time, val))

        # Points 3..N
        for _ in range(2, self.total_count):
            # Decode timestamp
            bit0 = self.reader.read_bit()
            if bit0 == 0:
                dod = 0
            else:
                bit1 = self.reader.read_bit()
                if bit1 == 0:  # '10'
                    dod = self.reader.read_bits(7) - 63
                else:
                    bit2 = self.reader.read_bit()
                    if bit2 == 0:  # '110'
                        dod = self.reader.read_bits(9) - 255
                    else:
                        bit3 = self.reader.read_bit()
                        if bit3 == 0:  # '1110'
                            dod = self.reader.read_bits(12) - 2047
                        else:  # '1111'
                            raw_dod = self.reader.read_bits(32)
                            # Convert unsigned 32-bit to signed
                            if raw_dod >= 0x80000000:
                                dod = raw_dod - 0x100000000
                            else:
                                dod = raw_dod

            self.prev_delta += dod
            self.prev_time += self.prev_delta
            val = self._decode_value()
            points.append((self.prev_time, val))

        return points

    def _decode_value(self) -> float:
        bit0 = self.reader.read_bit()
        if bit0 == 0:
            # Value unchanged
            return bits_to_float(self.prev_val_bits)

        control = self.reader.read_bit()
        if control == 0:
            # Reuse previous window
            length = 64 - self.prev_leading - self.prev_trailing
            bits = self.reader.read_bits(length)
            xor = bits << self.prev_trailing
        else:
            leading = self.reader.read_bits(5)
            length = self.reader.read_bits(6)
            bits = self.reader.read_bits(length)
            trailing = 64 - leading - length
            xor = bits << trailing
            self.prev_leading = leading
            self.prev_trailing = trailing

        self.prev_val_bits ^= xor
        return bits_to_float(self.prev_val_bits)
