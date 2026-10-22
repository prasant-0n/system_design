import sys
import os
import unittest
import time
import threading

sys.path.insert(0, os.path.dirname(__file__))

from resilience_patterns import CircuitBreaker, CircuitState, CircuitBreakerOpenException, SingleFlight


class TestResiliencePatterns(unittest.TestCase):

    def test_circuit_breaker_transitions(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=5.0)

        # Baseline: Success calls
        self.assertEqual(cb.execute(lambda: "OK", current_time=100.0), "OK")
        self.assertEqual(cb.state, CircuitState.CLOSED)

        # First failure
        with self.assertRaises(ValueError):
            cb.execute(lambda: (_ for _ in ()).throw(ValueError("DB Error")), current_time=101.0)
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.failure_count, 1)

        # Second failure -> trips breaker to OPEN
        with self.assertRaises(ValueError):
            cb.execute(lambda: (_ for _ in ()).throw(ValueError("DB Error")), current_time=102.0)
        self.assertEqual(cb.state, CircuitState.OPEN)

        # Immediate next call fast fails without calling service
        with self.assertRaises(CircuitBreakerOpenException):
            cb.execute(lambda: "Should not run", current_time=103.0)

        # Fast forward time past recovery timeout (102 + 5 = 107) -> transitions to HALF_OPEN
        # Trial run succeeds -> transitions back to CLOSED
        res = cb.execute(lambda: "Recovered!", current_time=108.0)
        self.assertEqual(res, "Recovered!")
        self.assertEqual(cb.state, CircuitState.CLOSED)
        self.assertEqual(cb.failure_count, 0)

    def test_single_flight_duplicate_suppression(self):
        sf = SingleFlight()
        execution_count = 0
        lock = threading.Lock()

        def slow_db_query():
            nonlocal execution_count
            time.sleep(0.05)
            with lock:
                execution_count += 1
            return "Expensive Data"

        results = []
        threads = []

        def worker():
            val, shared = sf.do("user:profile:123", slow_db_query)
            results.append((val, shared))

        # Launch 5 concurrent threads requesting same key
        for _ in range(5):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Invariant: slow_db_query must have run exactly once!
        self.assertEqual(execution_count, 1)
        self.assertEqual(len(results), 5)
        for val, _ in results:
            self.assertEqual(val, "Expensive Data")

        # Count how many got shared response
        shared_count = sum(1 for _, shared in results if shared)
        self.assertEqual(shared_count, 4)


if __name__ == "__main__":
    unittest.main()
