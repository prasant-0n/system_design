"""
Unit tests for Consistent Hashing Ring.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from consistent_hash import ConsistentHashRing


class TestConsistentHashRing(unittest.TestCase):

    def setUp(self):
        self.ring = ConsistentHashRing(num_vnodes=150)

    def test_empty_ring(self):
        self.assertIsNone(self.ring.get_node("user_101"))
        self.assertEqual(self.ring.get_preference_list("user_101", 3), [])

    def test_single_node(self):
        self.ring.add_node("node-1")
        self.assertEqual(self.ring.get_node("key1"), "node-1")
        self.assertEqual(self.ring.get_node("key2"), "node-1")
        self.assertEqual(self.ring.get_preference_list("key1", 3), ["node-1"])

    def test_multi_node_distribution_and_balance(self):
        nodes = ["node-1", "node-2", "node-3", "node-4"]
        for node in nodes:
            self.ring.add_node(node)

        # Generate 10,000 random keys
        keys = [f"user-session-token-{i}" for i in range(10000)]
        stats = self.ring.get_distribution_stats(keys)

        # Expected average is 2,500 keys per node.
        # With 150 vnodes, each node should receive between 2000 and 3000 keys (within 20% variance)
        for node in nodes:
            count = stats[node]
            self.assertGreater(count, 1800, f"{node} received too few keys: {count}")
            self.assertLess(count, 3200, f"{node} received too many keys: {count}")

    def test_minimal_key_migration_on_node_add(self):
        """
        When adding 1 node to an N-node cluster, ideally only ~1/(N+1) of keys
        should migrate to the new node, while existing keys on other nodes do not churn.
        """
        initial_nodes = ["node-1", "node-2", "node-3"]
        for node in initial_nodes:
            self.ring.add_node(node)

        keys = [f"item-{i}" for i in range(3000)]
        initial_mapping = {k: self.ring.get_node(k) for k in keys}

        # Add 4th node
        self.ring.add_node("node-4")
        new_mapping = {k: self.ring.get_node(k) for k in keys}

        migrated_keys = 0
        migrated_to_node4 = 0

        for k in keys:
            if initial_mapping[k] != new_mapping[k]:
                migrated_keys += 1
                if new_mapping[k] == "node-4":
                    migrated_to_node4 += 1

        # In consistent hashing, virtually ALL migrated keys must move to the newly added node!
        self.assertEqual(migrated_keys, migrated_to_node4)
        # Expected migration ratio ~ 1/4 = 25% (20% - 32% acceptable window)
        migration_ratio = migrated_keys / len(keys)
        self.assertGreater(migration_ratio, 0.18)
        self.assertLess(migration_ratio, 0.32)

    def test_node_removal(self):
        nodes = ["node-A", "node-B", "node-C"]
        for node in nodes:
            self.ring.add_node(node)

        keys = [f"order-{i}" for i in range(500)]
        self.ring.remove_node("node-B")

        for k in keys:
            owner = self.ring.get_node(k)
            self.assertIn(owner, ["node-A", "node-C"])
            self.assertNotEqual(owner, "node-B")

    def test_preference_list_uniqueness(self):
        nodes = ["server-1", "server-2", "server-3", "server-4", "server-5"]
        for node in nodes:
            self.ring.add_node(node)

        for i in range(20):
            pref = self.ring.get_preference_list(f"key-{i}", 3)
            self.assertEqual(len(pref), 3)
            # All 3 nodes in preference list must be unique physical servers
            self.assertEqual(len(set(pref)), 3)


if __name__ == "__main__":
    unittest.main()
