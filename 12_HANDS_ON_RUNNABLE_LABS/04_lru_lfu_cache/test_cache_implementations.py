"""
Unit tests for O(1) LRU and O(1) LFU Cache implementations.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from cache_implementations import LFUCache, LRUCache


class TestCacheImplementations(unittest.TestCase):

    def test_lru_cache_basic_and_eviction(self):
        cache = LRUCache(capacity=2)

        cache.put("a", 1)
        cache.put("b", 2)
        self.assertEqual(cache.get("a"), 1)  # "a" is now most recently used; "b" is LRU

        cache.put("c", 3)  # Evicts "b"
        self.assertIsNone(cache.get("b"))

        # Access "a" so "a" becomes MRU and "c" becomes LRU
        self.assertEqual(cache.get("a"), 1)

        cache.put("d", 4)  # Evicts "c"
        self.assertIsNone(cache.get("c"))
        self.assertEqual(cache.get("a"), 1)
        self.assertEqual(cache.get("d"), 4)

    def test_lru_cache_update_existing_key(self):
        cache = LRUCache(capacity=2)
        cache.put("k1", "v1")
        cache.put("k2", "v2")
        cache.put("k1", "v1_updated")  # Update existing key

        cache.put("k3", "v3")  # Should evict "k2", not "k1"
        self.assertEqual(cache.get("k1"), "v1_updated")
        self.assertIsNone(cache.get("k2"))
        self.assertEqual(cache.get("k3"), "v3")

    def test_lfu_cache_frequency_eviction(self):
        # Capacity = 2
        cache = LFUCache(capacity=2)

        cache.put("k1", 10)
        cache.put("k2", 20)

        # Access k1 twice (frequency becomes 3: 1 put + 2 gets)
        self.assertEqual(cache.get("k1"), 10)
        self.assertEqual(cache.get("k1"), 10)

        # Insert k3 (capacity exceeded).
        # k1 has freq=3, k2 has freq=1 -> Must evict k2!
        cache.put("k3", 30)

        self.assertIsNone(cache.get("k2"))
        self.assertEqual(cache.get("k1"), 10)
        self.assertEqual(cache.get("k3"), 30)

    def test_lfu_cache_tie_breaking_via_recency(self):
        """
        When two keys have identical minimum frequency,
        LFU must evict the LEAST RECENTLY USED among them.
        """
        cache = LFUCache(capacity=2)

        cache.put("k1", 100)  # freq = 1
        cache.put("k2", 200)  # freq = 1

        # Both k1 and k2 have freq=1.
        # But k2 was added more recently than k1.
        # Inserting k3 should evict the older one: k1!
        cache.put("k3", 300)

        self.assertIsNone(cache.get("k1"))
        self.assertEqual(cache.get("k2"), 200)
        self.assertEqual(cache.get("k3"), 300)


if __name__ == "__main__":
    unittest.main()
