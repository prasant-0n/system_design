import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from autocomplete_trie import AutocompleteTrie


class TestAutocompleteTrie(unittest.TestCase):

    def setUp(self):
        self.trie = AutocompleteTrie(max_cached_suggestions=5)
        # Populate initial corpus
        corpus = [
            ("apple", 100),
            ("app", 50),
            ("application", 80),
            ("apply", 30),
            ("ape", 20),
            ("banana", 90),
            ("band", 40),
        ]
        for query, freq in corpus:
            self.trie.insert(query, freq)

    def test_prefix_search_ranking(self):
        results = self.trie.search("app", k=3)
        self.assertEqual(len(results), 3)
        # Expected order: apple (100), application (80), app (50)
        self.assertEqual(results[0][0], "apple")
        self.assertEqual(results[0][1], 100)
        self.assertEqual(results[1][0], "application")
        self.assertEqual(results[1][1], 80)
        self.assertEqual(results[2][0], "app")
        self.assertEqual(results[2][1], 50)

    def test_incremental_frequency_boost(self):
        # Boost "app" by 60 -> total frequency becomes 110 (greater than apple 100)
        self.trie.insert("app", 60)
        results = self.trie.search("app", k=2)
        self.assertEqual(results[0][0], "app")
        self.assertEqual(results[0][1], 110)
        self.assertEqual(results[1][0], "apple")
        self.assertEqual(results[1][1], 100)

    def test_non_existent_prefix(self):
        results = self.trie.search("xyz")
        self.assertEqual(results, [])

    def test_case_insensitivity(self):
        results_lower = self.trie.search("ban", k=2)
        results_upper = self.trie.search("BAN", k=2)
        self.assertEqual(results_lower, results_upper)
        self.assertEqual(results_lower[0][0], "banana")


if __name__ == "__main__":
    unittest.main()
