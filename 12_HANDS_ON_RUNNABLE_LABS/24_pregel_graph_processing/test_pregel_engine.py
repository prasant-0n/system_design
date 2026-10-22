import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from pregel_engine import PregelMaster, PageRankVertex


class TestPregelEngine(unittest.TestCase):

    def test_pagerank_star_network(self):
        # 4 vertices: A, B, C all point to Center D. Center D points to A.
        # Graph: A -> D, B -> D, C -> D, D -> A
        # Vertex D should accumulate the highest PageRank because of 3 inbound links!
        vA = PageRankVertex("A", out_edges=["D"], total_vertices=4)
        vB = PageRankVertex("B", out_edges=["D"], total_vertices=4)
        vC = PageRankVertex("C", out_edges=["D"], total_vertices=4)
        vD = PageRankVertex("D", out_edges=["A"], total_vertices=4)

        master = PregelMaster([vA, vB, vC, vD])
        steps = master.run(max_supersteps=20)

        self.assertGreater(steps, 5)

        # Invariant: PageRank sum across all vertices must equal ~1.0
        total_rank = sum(v.value for v in master.vertices.values())
        self.assertAlmostEqual(total_rank, 1.0, places=2)

        # Invariant: D should have the highest PageRank
        rank_D = master.vertices["D"].value
        rank_A = master.vertices["A"].value
        rank_B = master.vertices["B"].value
        rank_C = master.vertices["C"].value

        self.assertGreater(rank_D, rank_B)
        self.assertGreater(rank_D, rank_C)


if __name__ == "__main__":
    unittest.main()
