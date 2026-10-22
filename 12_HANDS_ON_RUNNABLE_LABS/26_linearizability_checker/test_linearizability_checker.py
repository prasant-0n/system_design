import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from linearizability_checker import RegisterLinearizabilityChecker, Operation


class TestLinearizabilityChecker(unittest.TestCase):

    def setUp(self):
        self.checker = RegisterLinearizabilityChecker()

    def test_valid_sequential_history(self):
        # Sequential: Write 1 [10..20], Read 1 [25..30], Write 2 [35..40], Read 2 [45..50]
        history = [
            Operation("w1", "p1", "write", 1, 10.0, 20.0),
            Operation("r1", "p2", "read", 1, 25.0, 30.0),
            Operation("w2", "p1", "write", 2, 35.0, 40.0),
            Operation("r2", "p3", "read", 2, 45.0, 50.0),
        ]
        self.assertTrue(self.checker.is_linearizable(history, initial_val=0))

    def test_valid_concurrent_overlapping_history(self):
        # Process 1 writes 100 [10..50]
        # Process 2 reads 100 [20..30] (concurrent with write)
        # Process 3 reads 0 [15..25] (also concurrent, linearized before write takes effect)
        history = [
            Operation("w1", "p1", "write", 100, 10.0, 50.0),
            Operation("r1", "p3", "read", 0, 15.0, 25.0),
            Operation("r2", "p2", "read", 100, 30.0, 40.0),
        ]
        self.assertTrue(self.checker.is_linearizable(history, initial_val=0))

    def test_stale_read_violation(self):
        """
        Classic Jepsen anomaly:
        Write 1 completes at t=20.
        Process 2 invokes read at t=30 (AFTER write completed) and reads old value 0!
        MUST BE DETECTED AS NON-LINEARIZABLE.
        """
        history = [
            Operation("w1", "p1", "write", 1, 10.0, 20.0),
            # Invoked at 30.0 (strictly after 20.0), but returns 0 instead of 1
            Operation("r_stale", "p2", "read", 0, 30.0, 40.0),
        ]
        self.assertFalse(self.checker.is_linearizable(history, initial_val=0))


if __name__ == "__main__":
    unittest.main()
