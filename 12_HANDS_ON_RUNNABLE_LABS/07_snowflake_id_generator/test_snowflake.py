"""
Unit tests for Twitter Snowflake 64-bit ID Generator.
"""

import concurrent.futures
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from snowflake import SnowflakeGenerator


class TestSnowflake(unittest.TestCase):

    def test_id_uniqueness_and_sortability(self):
        generator = SnowflakeGenerator(datacenter_id=1, worker_id=2)
        count = 5000
        ids = [generator.generate_id() for _ in range(count)]

        # All IDs must be unique
        self.assertEqual(len(set(ids)), count)

        # Monotonically increasing / sortable
        for i in range(len(ids) - 1):
            self.assertLess(ids[i], ids[i + 1])

    def test_id_parsing_and_bitwise_integrity(self):
        dc_id = 7
        worker_id = 15
        generator = SnowflakeGenerator(datacenter_id=dc_id, worker_id=worker_id)

        generated_id = generator.generate_id()
        parsed = generator.parse_id(generated_id)

        self.assertEqual(parsed["id"], generated_id)
        self.assertEqual(parsed["datacenter_id"], dc_id)
        self.assertEqual(parsed["worker_id"], worker_id)
        self.assertGreater(parsed["timestamp_ms"], generator.custom_epoch)

    def test_concurrent_multithreaded_generation(self):
        """
        Verify that 10 concurrent threads generating thousands of IDs simultaneously
        produce zero duplicate IDs.
        """
        generator = SnowflakeGenerator(datacenter_id=3, worker_id=4)
        num_threads = 10
        ids_per_thread = 1000

        def worker_task():
            return [generator.generate_id() for _ in range(ids_per_thread)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker_task) for _ in range(num_threads)]
            results = []
            for f in futures:
                results.extend(f.result())

        total_expected = num_threads * ids_per_thread
        self.assertEqual(len(results), total_expected)
        self.assertEqual(len(set(results)), total_expected, "Collision detected in multithreaded test!")


if __name__ == "__main__":
    unittest.main()
