import sys
import os
import unittest
import time

sys.path.insert(0, os.path.dirname(__file__))

from distributed_lock import DistributedLockManager, LockNode, ProtectedStorageResource, FencingTokenViolationError


class TestDistributedLockAndFencing(unittest.TestCase):

    def setUp(self):
        # Cluster of 5 nodes; Quorum = 3
        self.nodes = [LockNode(f"redis-{i}") for i in range(5)]
        self.manager = DistributedLockManager(self.nodes)
        self.storage = ProtectedStorageResource("bank_account")

    def test_successful_acquisition_and_fencing_token(self):
        token1 = self.manager.acquire("account:101", "client-A", ttl_seconds=10.0, current_time=1000.0)
        self.assertIsNotNone(token1)
        self.assertEqual(token1, 1)

        # Storage write succeeds with token 1
        success = self.storage.write({"balance": 500}, fencing_token=token1)
        self.assertTrue(success)
        val, token = self.storage.read()
        self.assertEqual(val["balance"], 500)
        self.assertEqual(token, 1)

        # Release lock
        self.manager.release("account:101", "client-A", token1)

    def test_concurrent_acquisition_rejection(self):
        token1 = self.manager.acquire("account:101", "client-A", ttl_seconds=10.0, current_time=1000.0)
        self.assertIsNotNone(token1)

        # Client B tries to acquire while A holds it
        token2 = self.manager.acquire("account:101", "client-B", ttl_seconds=10.0, current_time=1001.0)
        self.assertIsNone(token2)

    def test_martin_kleppmann_gc_pause_fencing_invariant(self):
        """
        Simulate Martin Kleppmann's GC Pause Hazard:
        1. Client A acquires lock with TTL=5s, token=1.
        2. Client A enters a long GC pause / hypervisor deschedule.
        3. Lock expires at t=1005s.
        4. Client B acquires lock at t=1006s, token=2.
        5. Client B writes to storage with token=2.
        6. Client A awakens from GC pause and attempts to write with token=1.
        7. Target storage MUST reject Client A's write, preventing split-brain corruption.
        """
        # Step 1: Client A gets lock
        token_A = self.manager.acquire("order:999", "client-A", ttl_seconds=5.0, current_time=1000.0)
        self.assertEqual(token_A, 1)

        # Step 2 & 3: Time passes past TTL (GC pause) -> t=1006.0
        # Step 4: Client B acquires lock
        token_B = self.manager.acquire("order:999", "client-B", ttl_seconds=5.0, current_time=1006.0)
        self.assertIsNotNone(token_B)
        self.assertEqual(token_B, 2)

        # Step 5: Client B writes to storage
        self.storage.write("Client B Data", fencing_token=token_B)

        # Step 6 & 7: Client A wakes up and attempts to write with token 1 -> MUST FAIL
        with self.assertRaises(FencingTokenViolationError):
            self.storage.write("Client A Corrupted Data", fencing_token=token_A)

        # Confirm data integrity
        val, tok = self.storage.read()
        self.assertEqual(val, "Client B Data")
        self.assertEqual(tok, 2)


if __name__ == "__main__":
    unittest.main()
