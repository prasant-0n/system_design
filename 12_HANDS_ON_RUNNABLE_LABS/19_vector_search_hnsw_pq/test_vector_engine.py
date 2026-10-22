import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from vector_engine import MiniHNSW, MiniProductQuantizer, l2_distance, cosine_similarity


class TestVectorEngine(unittest.TestCase):

    def test_metrics(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [0.0, 1.0, 0.0]
        v3 = [1.0, 0.0, 0.0]

        # Orthogonal vectors -> cosine similarity = 0.0
        self.assertAlmostEqual(cosine_similarity(v1, v2), 0.0)
        # Identical vectors -> cosine similarity = 1.0
        self.assertAlmostEqual(cosine_similarity(v1, v3), 1.0)
        # L2 distance
        self.assertAlmostEqual(l2_distance(v1, v3), 0.0)

    def test_hnsw_search(self):
        hnsw = MiniHNSW(m=3)

        corpus = {
            "v_origin": [0.0, 0.0, 0.0, 0.0],
            "v_near": [0.1, 0.1, 0.0, 0.0],
            "v_mid": [1.0, 1.0, 1.0, 1.0],
            "v_far": [10.0, 10.0, 10.0, 10.0],
        }

        for nid, vec in corpus.items():
            hnsw.insert(nid, vec)

        query = [0.05, 0.05, 0.0, 0.0]
        results = hnsw.search(query, k=2)

        self.assertGreaterEqual(len(results), 2)
        top_ids = [r[0] for r in results]
        # Should return v_origin or v_near as top candidates
        self.assertIn("v_origin", top_ids)
        self.assertIn("v_near", top_ids)

    def test_product_quantizer(self):
        # 4-dim vectors quantized into 2 sub-vectors of dimension 2
        pq = MiniProductQuantizer(num_subvectors=2)

        training_vecs = [
            [0.0, 0.1, 5.0, 5.1],
            [0.1, 0.0, 5.1, 5.0],
            [9.0, 9.1, 0.0, 0.1],
            [9.1, 9.0, 0.1, 0.0],
        ]

        pq.fit(training_vecs, k_centroids=2)
        code = pq.encode([0.05, 0.05, 5.05, 5.05])

        # Encoded code has length 2 (1 code per sub-vector)
        self.assertEqual(len(code), 2)
        self.assertIsInstance(code[0], int)
        self.assertIsInstance(code[1], int)


if __name__ == "__main__":
    unittest.main()
