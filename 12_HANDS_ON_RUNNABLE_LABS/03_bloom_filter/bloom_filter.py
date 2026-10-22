"""
Production Bloom Filter Implementation.

Uses Kirsch-Mitzenmacher dual-hashing optimization to simulate k independent
hash functions from two base 64-bit cryptographic hashes.
"""

import hashlib
import math
from typing import Any


class BloomFilter:
    """
    Space-efficient probabilistic data structure.
    Guarantees: Zero False Negatives.
    Allows: Configurable False Positive Probability.
    """

    def __init__(self, expected_elements: int, false_positive_rate: float = 0.01):
        if expected_elements <= 0:
            raise ValueError("expected_elements must be a positive integer")
        if not (0 < false_positive_rate < 1):
            raise ValueError("false_positive_rate must be between 0 and 1 exclusive")

        self.expected_elements = expected_elements
        self.target_fp_rate = false_positive_rate

        # Optimal bit array size: m = - (n * ln(p)) / (ln(2)^2)
        self.bit_size = int(
            math.ceil(-1.0 * (expected_elements * math.log(false_positive_rate)) / (math.log(2) ** 2))
        )

        # Optimal number of hash functions: k = (m / n) * ln(2)
        self.num_hashes = int(
            math.ceil((self.bit_size / expected_elements) * math.log(2))
        )

        # Allocate bytearray (bit array)
        num_bytes = (self.bit_size + 7) // 8
        self.bit_array = bytearray(num_bytes)
        self.count = 0

    def _get_hashes(self, item: str):
        """
        Kirsch-Mitzenmacher technique:
        Generates k hash indices using: g_i(x) = (h1(x) + i * h2(x)) mod m
        """
        digest = hashlib.sha256(item.encode("utf-8")).digest()
        h1 = int.from_bytes(digest[:8], byteorder="big")
        h2 = int.from_bytes(digest[8:16], byteorder="big")

        for i in range(self.num_hashes):
            yield (h1 + i * h2) % self.bit_size

    def add(self, item: Any) -> None:
        """Adds an item into the Bloom filter."""
        item_str = str(item)
        for bit_index in self._get_hashes(item_str):
            byte_idx = bit_index // 8
            bit_idx = bit_index % 8
            self.bit_array[byte_idx] |= (1 << bit_idx)
        self.count += 1

    def contains(self, item: Any) -> bool:
        """
        Checks if an item might be in the set.
        Returns:
            False: The item is DEFINITELY NOT in the set (Zero false negatives).
            True:  The item MIGHT be in the set (Subject to false positive rate).
        """
        item_str = str(item)
        for bit_index in self._get_hashes(item_str):
            byte_idx = bit_index // 8
            bit_idx = bit_index % 8
            if not (self.bit_array[byte_idx] & (1 << bit_idx)):
                return False
        return True

    def __contains__(self, item: Any) -> bool:
        return self.contains(item)

    def current_fill_ratio(self) -> float:
        """Calculates the proportion of bits set to 1."""
        set_bits = sum(bin(byte).count("1") for byte in self.bit_array)
        return set_bits / self.bit_size

    def estimated_false_positive_rate(self) -> float:
        """
        Calculates theoretical false positive rate for current element count:
        p ≈ (1 - e^(-k * n / m))^k
        """
        exponent = -1.0 * self.num_hashes * self.count / self.bit_size
        return (1.0 - math.exp(exponent)) ** self.num_hashes
