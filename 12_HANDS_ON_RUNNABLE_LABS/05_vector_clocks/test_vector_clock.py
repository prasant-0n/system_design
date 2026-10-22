"""
Unit tests for Vector Clock causality and concurrent conflict detection.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from vector_clock import VectorClock


class TestVectorClock(unittest.TestCase):

    def test_causal_chain(self):
        # Node A sends to Node B, then Node B sends to Node C
        vc_a = VectorClock("A")
        vc_b = VectorClock("B")
        vc_c = VectorClock("C")

        # Event 1: A ticks and sends to B
        msg_a = vc_a.send_event()  # A: {A: 1}
        self.assertEqual(vc_a.clock, {"A": 1})

        # Event 2: B receives from A
        vc_b.receive_event(msg_a)  # B merges {A: 1} and ticks B: {A: 1, B: 1}
        self.assertTrue(msg_a.happened_before(vc_b))
        self.assertFalse(vc_b.happened_before(msg_a))

        # Event 3: B sends to C
        msg_b = vc_b.send_event()  # B ticks B: {A: 1, B: 2}
        vc_c.receive_event(msg_b)  # C merges and ticks C: {A: 1, B: 2, C: 1}

        # Transitivity: A happened before C!
        self.assertTrue(msg_a.happened_before(vc_c))
        self.assertTrue(msg_b.happened_before(vc_c))

    def test_concurrent_conflict_detection(self):
        """
        Classic distributed split-brain or concurrent shopping cart updates:
        Node A and Node B both accept updates without communicating.
        """
        vc_a = VectorClock("A")
        vc_b = VectorClock("B")

        # Node A and Node B both do local updates independently
        vc_a.tick()  # A: {A: 1}
        vc_a.tick()  # A: {A: 2}

        vc_b.tick()  # B: {B: 1}

        # Neither happened before the other!
        self.assertFalse(vc_a.happened_before(vc_b))
        self.assertFalse(vc_b.happened_before(vc_a))
        # Conflict detected: They are concurrent!
        self.assertTrue(vc_a.concurrent_with(vc_b))
        self.assertTrue(vc_b.concurrent_with(vc_a))

    def test_equality_and_cloning(self):
        vc1 = VectorClock("A", {"A": 2, "B": 1})
        vc2 = VectorClock("B", {"A": 2, "B": 1})
        self.assertEqual(vc1, vc2)
        self.assertFalse(vc1.happened_before(vc2))
        self.assertFalse(vc1.concurrent_with(vc2))

        clone = vc1.clone()
        self.assertEqual(vc1, clone)
        clone.tick()
        self.assertTrue(vc1.happened_before(clone))


if __name__ == "__main__":
    unittest.main()
