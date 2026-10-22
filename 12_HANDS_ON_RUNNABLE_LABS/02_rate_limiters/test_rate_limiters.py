"""
Unit tests for Token Bucket, Leaky Bucket, and Sliding Window Counter.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from rate_limiters import (
    LeakyBucketRateLimiter,
    SlidingWindowCounterRateLimiter,
    TokenBucketRateLimiter,
)


class TestRateLimiters(unittest.TestCase):

    def test_token_bucket_burst_and_refill(self):
        # Capacity = 5, Refill = 2 tokens / sec
        limiter = TokenBucketRateLimiter(capacity=5, refill_rate=2)
        base_time = 1000.0

        # Consume 5 tokens immediately (Burst)
        for _ in range(5):
            self.assertTrue(limiter.allow_request(1, current_time=base_time))

        # 6th request at exact same timestamp must be rejected
        self.assertFalse(limiter.allow_request(1, current_time=base_time))

        # Advance time by 1.0 second -> Refilled 2 tokens
        self.assertTrue(limiter.allow_request(1, current_time=base_time + 1.0))
        self.assertTrue(limiter.allow_request(1, current_time=base_time + 1.0))
        # 3rd token request should fail
        self.assertFalse(limiter.allow_request(1, current_time=base_time + 1.0))

        # Advance time by 10.0 seconds -> Should cap at max capacity (5 tokens)
        self.assertTrue(limiter.allow_request(5, current_time=base_time + 11.0))
        self.assertFalse(limiter.allow_request(1, current_time=base_time + 11.0))

    def test_leaky_bucket_traffic_smoothing(self):
        # Capacity = 3 slots, Leak rate = 1 req / sec
        limiter = LeakyBucketRateLimiter(capacity=3, leak_rate=1.0)
        base_time = 1000.0

        # Fill 3 slots
        self.assertTrue(limiter.allow_request(current_time=base_time))
        self.assertTrue(limiter.allow_request(current_time=base_time))
        self.assertTrue(limiter.allow_request(current_time=base_time))
        # 4th request overflows bucket
        self.assertFalse(limiter.allow_request(current_time=base_time))

        # Advance 1.5 seconds -> Drained 1.5 units
        self.assertTrue(limiter.allow_request(current_time=base_time + 1.5))
        self.assertFalse(limiter.allow_request(current_time=base_time + 1.5))

    def test_sliding_window_counter_boundary_protection(self):
        # Limit = 100 req per 60 seconds
        limiter = SlidingWindowCounterRateLimiter(limit=100, window_size_seconds=60.0)
        base_time = 60.0  # Window 60..120

        # Send 80 requests at the very end of Window 1 (t = 119s)
        for _ in range(80):
            self.assertTrue(limiter.allow_request(current_time=119.0))

        # Enter Window 2 at t = 121s (1 second into next window: overlap with prev window is ~59/60 = 98%)
        # In a fixed window, this would allow 100 new requests (2x boundary spike exploit).
        # In Sliding Window Counter, estimated requests = (80 * 0.98) + curr = 78.4 requests already!
        # So we can only make ~21 requests before being throttled.
        allowed_count = 0
        for _ in range(50):
            if limiter.allow_request(current_time=121.0):
                allowed_count += 1

        self.assertLessEqual(allowed_count, 23)
        self.assertGreaterEqual(allowed_count, 20)

    def test_sliding_window_counter_reset_after_full_window(self):
        limiter = SlidingWindowCounterRateLimiter(limit=10, window_size_seconds=60.0)
        # Exhaust limit
        for _ in range(10):
            self.assertTrue(limiter.allow_request(current_time=100.0))
        self.assertFalse(limiter.allow_request(current_time=100.0))

        # Advance past 2 full windows (t = 250.0)
        # Should have clean full quota of 10 requests available again
        for _ in range(10):
            self.assertTrue(limiter.allow_request(current_time=250.0))
        self.assertFalse(limiter.allow_request(current_time=250.0))


if __name__ == "__main__":
    unittest.main()
