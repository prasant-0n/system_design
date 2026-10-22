import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from lsm_tree import LSMTree, SSTable


class TestLSMTree(unittest.TestCase):

    def test_sstable_sparse_index_lookup(self):
        # Pairs: [("a", 1), ("b", 2), ("c", 3), ("d", 4), ("e", 5)]
        data = [("a", 1), ("b", 2), ("c", 3), ("d", 4), ("e", 5)]
        sstable = SSTable(data, sparse_index_interval=2)

        # Lookup existing keys
        found, val = sstable.get("c")
        self.assertTrue(found)
        self.assertEqual(val, 3)

        found, val = sstable.get("e")
        self.assertTrue(found)
        self.assertEqual(val, 5)

        # Lookup non-existent keys
        found, val = sstable.get("bb")
        self.assertFalse(found)

        found, val = sstable.get("z")
        self.assertFalse(found)

    def test_lsm_tree_put_flush_and_shadowing(self):
        # Threshold = 2 to force rapid flushes
        lsm = LSMTree(memtable_threshold=2, sparse_interval=2)

        # Put 2 items -> triggers flush to SSTable 1
        lsm.put("user:1", "Alice")
        lsm.put("user:2", "Bob")
        self.assertEqual(len(lsm.sstables), 1)

        # Update user:1 -> sits in MemTable
        lsm.put("user:1", "Alice Updated")
        # Invariant: Must return the newer update from MemTable, shadowing SSTable 1
        self.assertEqual(lsm.get("user:1"), "Alice Updated")
        self.assertEqual(lsm.get("user:2"), "Bob")

        # Put another item -> triggers flush to SSTable 2
        lsm.put("user:3", "Charlie")
        self.assertEqual(len(lsm.sstables), 2)
        self.assertEqual(lsm.get("user:1"), "Alice Updated")

    def test_tombstone_deletion_and_compaction(self):
        lsm = LSMTree(memtable_threshold=2, sparse_interval=2)

        lsm.put("k1", "v1")
        lsm.put("k2", "v2")  # Flushes SSTable 1

        lsm.put("k3", "v3")
        lsm.delete("k1")     # Flushes SSTable 2 (contains tombstone for k1)

        # k1 should be reported as deleted
        self.assertIsNone(lsm.get("k1"))
        self.assertEqual(lsm.get("k2"), "v2")
        self.assertEqual(lsm.get("k3"), "v3")

        # Before compaction: 2 SSTables
        self.assertEqual(len(lsm.sstables), 2)

        # Trigger multi-way compaction
        lsm.compact()

        # After compaction: exactly 1 SSTable, k1 tombstone completely reclaimed
        self.assertEqual(len(lsm.sstables), 1)
        self.assertIsNone(lsm.get("k1"))
        self.assertEqual(lsm.get("k2"), "v2")
        self.assertEqual(lsm.get("k3"), "v3")

        # Verify raw data in compacted sstable does NOT contain k1
        compacted_keys = [k for k, _ in lsm.sstables[0].data]
        self.assertNotIn("k1", compacted_keys)
        self.assertIn("k2", compacted_keys)
        self.assertIn("k3", compacted_keys)


if __name__ == "__main__":
    unittest.main()
