import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from probabilistic_analytics import CountMinSketch, HyperLogLog


class TestProbabilisticAnalytics(unittest.TestCase):

    def test_count_min_sketch_bounds(self):
        # CMS with 1% error margin
        cms = CountMinSketch(epsilon=0.01, delta=0.01)

        counts = {
            "apple": 500,
            "banana": 1200,
            "cherry": 50,
            "date": 3,
        }

        for item, count in counts.items():
            cms.add(item, count)

        # Invariant 1: estimate >= true_count
        for item, true_val in counts.items():
            est = cms.estimate(item)
            self.assertGreaterEqual(est, true_val)
            # Invariant 2: error bound <= true_val + epsilon * total
            self.assertLessEqual(est, true_val + (0.01 * cms.total_count) + 5)

        # Check unseen item
        unseen_est = cms.estimate("unseen_item")
        # Should be small (close to 0)
        self.assertLessEqual(unseen_est, 0.01 * cms.total_count + 5)

    def test_hyperloglog_cardinality_estimation(self):
        # b = 10 -> m = 1024 registers, std error ~ 3.25%
        hll = HyperLogLog(b=10)

        true_uniques = 10000
        for i in range(true_uniques):
            hll.add(f"user_session_{i}")

        # Add duplicates to ensure duplicates don't inflate cardinality
        for i in range(1000):
            hll.add(f"user_session_{i}")

        estimated = hll.cardinality()

        # Check that error is within ~6% (within 2 std deviations of theoretical ~3.25%)
        error_ratio = abs(estimated - true_uniques) / float(true_uniques)
        self.assertLess(error_ratio, 0.06, f"HLL estimate {estimated} too far from {true_uniques}")


if __name__ == "__main__":
    unittest.main()
