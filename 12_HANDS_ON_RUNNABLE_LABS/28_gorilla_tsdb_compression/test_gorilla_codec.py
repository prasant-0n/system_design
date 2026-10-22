"""Tests for Facebook Gorilla Time-Series Compression."""

import unittest
from .gorilla_codec import BitWriter, BitReader, GorillaEncoder, GorillaDecoder


class TestGorillaCodec(unittest.TestCase):

    def test_bitwriter_bitreader_roundtrip(self):
        writer = BitWriter()
        writer.write_bit(1)
        writer.write_bit(0)
        writer.write_bit(1)
        writer.write_bits(0b1011, 4)
        writer.write_bits(42, 8)
        data = writer.flush()

        reader = BitReader(data)
        self.assertEqual(reader.read_bit(), 1)
        self.assertEqual(reader.read_bit(), 0)
        self.assertEqual(reader.read_bit(), 1)
        self.assertEqual(reader.read_bits(4), 0b1011)
        self.assertEqual(reader.read_bits(8), 42)

    def test_gorilla_regular_timestamps_and_repeating_values(self):
        # 100 regular points: every 60s, steady metric value 42.0
        original = [(1600000000 + i * 60, 42.0) for i in range(100)]

        encoder = GorillaEncoder()
        for t, v in original:
            encoder.compress_point(t, v)
        compressed = encoder.finish()

        # Raw size: 100 * 16 bytes = 1600 bytes
        # Gorilla compression should be vastly smaller (< 50 bytes)
        self.assertLess(len(compressed), 50)

        decoder = GorillaDecoder(compressed, count=100)
        decoded = decoder.decode_all()

        self.assertEqual(len(decoded), 100)
        for orig, dec in zip(original, decoded):
            self.assertEqual(orig[0], dec[0])
            self.assertAlmostEqual(orig[1], dec[1], places=6)

    def test_gorilla_fluctuating_values_and_jittered_timestamps(self):
        # Realistic metrics: varying CPU usage and minor network jitter
        original = [
            (1600000000, 10.5),
            (1600000060, 10.5),
            (1600000121, 11.2),  # +1s jitter
            (1600000181, 11.2),
            (1600000240, 12.0),  # -1s jitter
            (1600000300, 12.0),
            (1600000360, 95.8),  # Spike
            (1600000420, 95.8),
        ]

        encoder = GorillaEncoder()
        for t, v in original:
            encoder.compress_point(t, v)
        compressed = encoder.finish()

        decoder = GorillaDecoder(compressed, count=len(original))
        decoded = decoder.decode_all()

        self.assertEqual(len(decoded), len(original))
        for orig, dec in zip(original, decoded):
            self.assertEqual(orig[0], dec[0])
            self.assertAlmostEqual(orig[1], dec[1], places=6)


if __name__ == "__main__":
    unittest.main()
