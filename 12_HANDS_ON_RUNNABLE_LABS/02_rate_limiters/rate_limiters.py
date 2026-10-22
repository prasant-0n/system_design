"""
Production implementations of the 3 primary Rate Limiting algorithms:
1. Token Bucket
2. Leaky Bucket
3. Sliding Window Counter
"""

import math
import time
from typing import Dict, Tuple


class TokenBucketRateLimiter:
    """
    Token Bucket Algorithm.
    Allows bursts up to capacity, refills at a constant continuous rate.
    """

    def __init__(self, capacity: float, refill_rate: float):
        if capacity <= 0 or refill_rate <= 0:
            raise ValueError("Capacity and refill_rate must be positive numbers")
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)  # Tokens per second
        self.tokens = float(capacity)
        self.last_refill = None

    def allow_request(self, tokens: float = 1.0, current_time: float = None) -> bool:
        now = time.time() if current_time is None else current_time
        if self.last_refill is None:
            self.last_refill = now
        else:
            # Refill tokens based on elapsed time
            elapsed = now - self.last_refill
            if elapsed > 0:
                self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
                self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class LeakyBucketRateLimiter:
    """
    Leaky Bucket Algorithm (Traffic Shaping).
    Smooths out incoming bursts into a strictly uniform leak rate.
    """

    def __init__(self, capacity: int, leak_rate: float):
        if capacity <= 0 or leak_rate <= 0:
            raise ValueError("Capacity and leak_rate must be positive numbers")
        self.capacity = capacity
        self.leak_rate = float(leak_rate)  # Requests per second
        self.water_level = 0.0
        self.last_leak = None

    def allow_request(self, current_time: float = None) -> bool:
        now = time.time() if current_time is None else current_time
        if self.last_leak is None:
            self.last_leak = now
        else:
            elapsed = now - self.last_leak
            if elapsed > 0:
                # Drain water
                self.water_level = max(0.0, self.water_level - elapsed * self.leak_rate)
                self.last_leak = now

        if self.water_level + 1.0 <= self.capacity:
            self.water_level += 1.0
            return True
        return False


class SlidingWindowCounterRateLimiter:
    """
    Sliding Window Counter Algorithm.
    Approximates sliding window traffic using weighted previous window count.
    Combines the low memory of fixed windows with smooth edge protection.
    """

    def __init__(self, limit: int, window_size_seconds: float = 60.0):
        if limit <= 0 or window_size_seconds <= 0:
            raise ValueError("Limit and window_size_seconds must be positive numbers")
        self.limit = limit
        self.window_size = float(window_size_seconds)
        # Tracks {window_start_timestamp: request_count}
        self.windows: Dict[int, int] = {}

    def _get_current_window_key(self, timestamp: float) -> int:
        return int(timestamp // self.window_size) * int(self.window_size)

    def allow_request(self, current_time: float = None) -> bool:
        now = time.time() if current_time is None else current_time
        curr_window_key = self._get_current_window_key(now)
        prev_window_key = curr_window_key - int(self.window_size)

        curr_count = self.windows.get(curr_window_key, 0)
        prev_count = self.windows.get(prev_window_key, 0)

        # Weight of the previous window is the fraction of the window that overlaps
        # with the sliding 60-second window
        elapsed_in_curr = now - curr_window_key
        overlap_weight = max(0.0, (self.window_size - elapsed_in_curr) / self.window_size)

        estimated_requests = (prev_count * overlap_weight) + curr_count

        if estimated_requests < self.limit:
            self.windows[curr_window_key] = curr_count + 1
            # Clean up old windows
            for k in list(self.windows.keys()):
                if k < prev_window_key:
                    del self.windows[k]
            return True

        return False
