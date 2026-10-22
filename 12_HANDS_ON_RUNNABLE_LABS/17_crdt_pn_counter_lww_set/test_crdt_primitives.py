import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from crdt_primitives import PNCounter, LWWElementSet


class TestCRDTPrimitives(unittest.TestCase):

    def test_pn_counter_operations_and_merge(self):
        # Replica A increments 5 times and decrements 1
        r_a = PNCounter()
        r_a.increment("node_A", 5)
        r_a.decrement("node_A", 1)
        self.assertEqual(r_a.value(), 4)

        # Replica B concurrently increments 3 times and decrements 2
        r_b = PNCounter()
        r_b.increment("node_B", 3)
        r_b.decrement("node_B", 2)
        self.assertEqual(r_b.value(), 1)

        # Merge A into B and B into A (Commutativity test)
        merged_ab = r_a.merge(r_b)
        merged_ba = r_b.merge(r_a)

        # Net expected: (5 + 3) - (1 + 2) = 5
        self.assertEqual(merged_ab.value(), 5)
        self.assertEqual(merged_ba.value(), 5)

        # Idempotence: merged ⊔ merged == merged
        double_merge = merged_ab.merge(merged_ab)
        self.assertEqual(double_merge.value(), 5)

    def test_lww_element_set_resolution(self):
        s1 = LWWElementSet()
        s2 = LWWElementSet()

        # s1 adds item 'item_x' at t=100
        s1.add("item_x", timestamp=100.0)
        self.assertTrue(s1.contains("item_x"))

        # s2 removes 'item_x' at t=105 (newer timestamp)
        s2.remove("item_x", timestamp=105.0)

        # Merging s1 and s2: Remove wins because t=105 > t=100
        merged = s1.merge(s2)
        self.assertFalse(merged.contains("item_x"))

        # Concurrent re-add at t=110
        s1.add("item_x", timestamp=110.0)
        re_merged = merged.merge(s1)
        self.assertTrue(re_merged.contains("item_x"))
        self.assertIn("item_x", re_merged.elements())


if __name__ == "__main__":
    unittest.main()
