"""
Unit tests for Bloom Filter.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from bloom_filter import BloomFilter


class TestBloomFilter(unittest.TestCase):

    def test_zero_false_negatives(self):
        """
        The cardinal invariant of Bloom Filters:
        Every element that was added MUST return True on contains().
        """
        n = 5000
        bf = BloomFilter(expected_elements=n, false_positive_rate=0.01)

        added_elements = [f"user_{i}@example.com" for i in range(n)]
        for item in added_elements:
            bf.add(item)

        # Invariant check: ZERO false negatives
        for item in added_elements:
            self.assertIn(item, bf)

    def test_empirical_false_positive_rate(self):
        """
        Verify that the measured false positive rate on un-added items
        is reasonably close to the requested 1% target rate.
        """
        n = 10000
        target_fp = 0.02  # 2% target
        bf = BloomFilter(expected_elements=n, false_positive_rate=target_fp)

        # Add 10,000 items
        for i in range(n):
            bf.add(f"item_inserted_{i}")

        # Test 10,000 distinct items that were NEVER inserted
        unadded_items = [f"item_unadded_{j}" for j in range(10000)]
        false_positives = sum(1 for item in unadded_items if item in bf)

        empirical_fp_rate = false_positives / len(unadded_items)
        # Should be approximately 2% (bounded within 0.5% to 3.5%)
        self.assertLess(empirical_fp_rate, 0.035, f"FP rate too high: {empirical_fp_rate}")
        self.assertGreater(empirical_fp_rate, 0.005, f"FP rate unexpectedly low: {empirical_fp_rate}")

    def test_fill_ratio_and_size_calculations(self):
        bf = BloomFilter(expected_elements=1000, false_positive_rate=0.01)
        # For 1% FP and 1000 items: bit_size should be ~9585 bits, num_hashes ~7
        self.assertGreater(bf.bit_size, 9000)
        self.assertEqual(bf.num_hashes, 7)
        self.assertEqual(bf.current_fill_ratio(), 0.0)

        # Add 1000 items
        for i in range(1000):
            bf.add(f"key_{i}")

        # For an optimally dimensioned bloom filter with target load, fill ratio should be ~50%
        fill_ratio = bf.current_fill_ratio()
        self.assertGreater(fill_ratio, 0.40)
        self.assertLess(fill_ratio, 0.60)


if __name__ == "__main__":
    unittest.main()
