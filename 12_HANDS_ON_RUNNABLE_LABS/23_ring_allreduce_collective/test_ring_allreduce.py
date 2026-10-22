import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from ring_allreduce import RingAllReduceCluster


class TestRingAllReduce(unittest.TestCase):

    def test_ring_allreduce_three_ranks(self):
        # 3 ranks, tensor length 6 (chunk size = 2)
        r0 = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        r1 = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]
        r2 = [100.0, 200.0, 300.0, 400.0, 500.0, 600.0]

        expected = [111.0, 222.0, 333.0, 444.0, 555.0, 666.0]

        cluster = RingAllReduceCluster([r0, r1, r2])
        cluster.execute_allreduce()

        # Invariant: Every rank MUST end up with the identical global sum
        for rank_idx, buf in enumerate(cluster.buffers):
            self.assertEqual(len(buf), 6)
            for val, exp in zip(buf, expected):
                self.assertAlmostEqual(val, exp, delta=1e-5)

    def test_ring_allreduce_four_ranks(self):
        # 4 ranks, tensor length 8 (chunk size = 2)
        ranks = [
            [1.0] * 8,
            [2.0] * 8,
            [3.0] * 8,
            [4.0] * 8,
        ]
        # Sum of 1 + 2 + 3 + 4 = 10.0 for every element
        expected = [10.0] * 8

        cluster = RingAllReduceCluster(ranks)
        cluster.execute_allreduce()

        for buf in cluster.buffers:
            for val, exp in zip(buf, expected):
                self.assertAlmostEqual(val, exp, delta=1e-5)


if __name__ == "__main__":
    unittest.main()
