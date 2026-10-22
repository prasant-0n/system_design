"""
Probabilistic Data Structures for Massive Stream Analytics:
1. Count-Min Sketch: Frequency estimation with mathematical error bounds (Cormode-Muthukrishnan).
2. HyperLogLog: Cardinality estimation (unique elements) with log-log space complexity.
"""

import math
import hashlib
from typing import List


class CountMinSketch:
    """
    Count-Min Sketch frequency estimation.
    Guarantee: True count <= Estimated count <= True count + (epsilon * TotalItems)
    with probability at least 1 - delta.
    """

    def __init__(self, epsilon: float = 0.01, delta: float = 0.01):
        if not (0 < epsilon < 1 and 0 < delta < 1):
            raise ValueError("epsilon and delta must be between 0 and 1")
        self.width = int(math.ceil(math.e / epsilon))
        self.depth = int(math.ceil(math.log(1.0 / delta)))
        self.table = [[0] * self.width for _ in range(self.depth)]
        self.total_count = 0

    def _hash(self, item: str, seed: int) -> int:
        h = hashlib.sha256(f"{seed}:{item}".encode("utf-8")).digest()
        # Extract integer from first 8 bytes
        val = int.from_bytes(h[:8], byteorder="big")
        return val % self.width

    def add(self, item: str, count: int = 1) -> None:
        """Increments count for the given item."""
        self.total_count += count
        for i in range(self.depth):
            col = self._hash(item, i)
            self.table[i][col] += count

    def estimate(self, item: str) -> int:
        """
        Estimates the frequency of the given item.
        Always returns min over all rows, guaranteeing no under-counting.
        """
        min_val = float("inf")
        for i in range(self.depth):
            col = self._hash(item, i)
            val = self.table[i][col]
            if val < min_val:
                min_val = val
        return int(min_val)


class HyperLogLog:
    """
    HyperLogLog cardinality estimator.
    Approximates unique elements using m = 2^b registers.
    Standard error: 1.04 / sqrt(m).
    """

    def __init__(self, b: int = 10):
        if not (4 <= b <= 16):
            raise ValueError("b must be between 4 and 16")
        self.b = b
        self.m = 1 << b  # 2^b registers
        self.registers = [0] * self.m

        # Flajolet alpha constants
        if self.m == 16:
            self.alpha = 0.673
        elif self.m == 32:
            self.alpha = 0.697
        elif self.m == 64:
            self.alpha = 0.709
        else:
            self.alpha = 0.7213 / (1.0 + 1.079 / self.m)

    def _hash(self, item: str) -> int:
        digest = hashlib.sha256(item.encode("utf-8")).digest()
        return int.from_bytes(digest[:8], byteorder="big")

    def _clz(self, val: int, max_bits: int = 64) -> int:
        """Count leading zeros."""
        if val == 0:
            return max_bits
        return (1 << max_bits).bit_length() - 1 - val.bit_length()

    def add(self, item: str) -> None:
        """Adds an item to the HyperLogLog sketch."""
        x = self._hash(item)
        # Use first b bits for register index
        idx = x >> (64 - self.b)
        # Remaining 64 - b bits for leading zero count
        w = x & ((1 << (64 - self.b)) - 1)
        # Count leading zeros + 1
        clz_count = self._clz(w, max_bits=64 - self.b) + 1
        if clz_count > self.registers[idx]:
            self.registers[idx] = clz_count

    def cardinality(self) -> int:
        """Estimates unique item count."""
        # Harmonic mean of 2^register
        indicator_sum = sum(2.0 ** (-reg) for reg in self.registers)
        raw_estimate = (self.alpha * (self.m ** 2)) / indicator_sum

        # Small range correction (LinearCounting)
        if raw_estimate <= 2.5 * self.m:
            zeros = self.registers.count(0)
            if zeros != 0:
                raw_estimate = self.m * math.log(self.m / float(zeros))

        return int(round(raw_estimate))
