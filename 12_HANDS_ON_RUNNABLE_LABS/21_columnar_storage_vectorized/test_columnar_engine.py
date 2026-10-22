import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from columnar_engine import MiniColumnarTable


class TestColumnarEngine(unittest.TestCase):

    def setUp(self):
        # Schema: age (int, no dict), country (string, dictionary encoded), spend (float, no dict)
        schema = {"age": False, "country": True, "spend": False}
        self.table = MiniColumnarTable(schema)

        # Chunk 1: young users (age 18-25)
        chunk1 = [
            {"age": 19, "country": "US", "spend": 100.0},
            {"age": 22, "country": "UK", "spend": 50.0},
            {"age": 25, "country": "US", "spend": 150.0},
        ]
        # Chunk 2: middle-aged users (age 30-45)
        chunk2 = [
            {"age": 32, "country": "CA", "spend": 200.0},
            {"age": 41, "country": "US", "spend": 300.0},
        ]
        # Chunk 3: senior users (age 60-75)
        chunk3 = [
            {"age": 65, "country": "UK", "spend": 400.0},
            {"age": 70, "country": "DE", "spend": 250.0},
        ]

        self.table.append_chunk(chunk1)
        self.table.append_chunk(chunk2)
        self.table.append_chunk(chunk3)

    def test_dictionary_compression(self):
        # Chunk 1 country chunk should have dictionary
        country_chunk = self.table.chunks[0]["country"]
        self.assertTrue(country_chunk.use_dictionary)
        self.assertIn("US", country_chunk.dictionary)
        self.assertIn("UK", country_chunk.dictionary)
        self.assertEqual(country_chunk.get_value(0), "US")
        self.assertEqual(country_chunk.get_value(1), "UK")

    def test_predicate_pushdown_chunk_skipping(self):
        # Query: WHERE age > 50 -> should skip Chunk 1 (max=25) and Chunk 2 (max=45)!
        result = self.table.query(
            filter_col="age",
            predicate=lambda a: a > 50,
            min_bound=51,
            sum_col="spend",
        )

        # 2 chunks skipped out of 3 total chunks
        self.assertEqual(result["skipped_chunks"], 2)
        # 2 matching rows in Chunk 3
        self.assertEqual(result["matching_rows"], 2)
        # Spend sum = 400 + 250 = 650.0
        self.assertEqual(result["sum"], 650.0)


if __name__ == "__main__":
    unittest.main()
