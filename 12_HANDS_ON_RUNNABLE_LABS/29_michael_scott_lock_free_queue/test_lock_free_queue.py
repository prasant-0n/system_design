"""Tests for Michael-Scott Lock-Free Queue."""

import unittest
import threading
from .lock_free_queue import MichaelScottQueue, AtomicReference


class TestLockFreeQueue(unittest.TestCase):

    def test_atomic_reference_cas(self):
        ref = AtomicReference(10)
        self.assertEqual(ref.get(), 10)

        # Expected does not match
        self.assertFalse(ref.compare_and_set(99, 20))
        self.assertEqual(ref.get(), 10)

        # Expected matches
        self.assertTrue(ref.compare_and_set(10, 20))
        self.assertEqual(ref.get(), 20)

    def test_single_threaded_fifo_behavior(self):
        q = MichaelScottQueue()
        self.assertTrue(q.is_empty())
        self.assertIsNone(q.dequeue())

        q.enqueue("alpha")
        q.enqueue("beta")
        q.enqueue("gamma")
        self.assertFalse(q.is_empty())

        self.assertEqual(q.dequeue(), "alpha")
        self.assertEqual(q.dequeue(), "beta")
        self.assertEqual(q.dequeue(), "gamma")
        self.assertIsNone(q.dequeue())
        self.assertTrue(q.is_empty())

    def test_concurrent_producers_and_consumers(self):
        q = MichaelScottQueue()
        num_producers = 4
        items_per_producer = 250
        total_items = num_producers * items_per_producer

        def producer(thread_id: int):
            for i in range(items_per_producer):
                q.enqueue((thread_id, i))

        producers = [threading.Thread(target=producer, args=(t,)) for t in range(num_producers)]
        for p in producers:
            p.start()
        for p in producers:
            p.join()

        # Dequeue everything concurrently
        consumed = []
        consumed_lock = threading.Lock()

        def consumer():
            while True:
                item = q.dequeue()
                if item is None:
                    break
                with consumed_lock:
                    consumed.append(item)

        consumers = [threading.Thread(target=consumer) for _ in range(4)]
        for c in consumers:
            c.start()
        for c in consumers:
            c.join()

        # Any remaining items
        while not q.is_empty():
            val = q.dequeue()
            if val is not None:
                consumed.append(val)

        self.assertEqual(len(consumed), total_items)
        # Verify no duplicates or missing elements
        self.assertEqual(len(set(consumed)), total_items)


if __name__ == "__main__":
    unittest.main()
