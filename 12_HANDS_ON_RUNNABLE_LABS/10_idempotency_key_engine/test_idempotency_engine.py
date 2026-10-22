"""
Unit tests for API Idempotency Key Engine.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from idempotency_engine import (
    ConcurrentRequestError,
    IdempotencyConflictError,
    IdempotencyEngine,
)


class TestIdempotencyEngine(unittest.TestCase):

    def setUp(self):
        self.engine = IdempotencyEngine()
        self.execution_counter = 0

    def payment_handler(self, payload):
        self.execution_counter += 1
        return 201, {"charge_id": f"ch_{self.execution_counter}", "amount": payload["amount"]}

    def test_idempotent_replay_without_reexecution(self):
        key = "idemp_uuid_1001"
        payload = {"amount": 5000, "currency": "USD", "card_token": "tok_visa"}

        # First Call: Actually executes payment logic
        status1, resp1, replayed1 = self.engine.execute(key, payload, self.payment_handler)
        self.assertEqual(status1, 201)
        self.assertEqual(resp1["charge_id"], "ch_1")
        self.assertFalse(replayed1)
        self.assertEqual(self.execution_counter, 1)

        # Second Call with identical key: Returns cached response, DOES NOT increment execution counter!
        status2, resp2, replayed2 = self.engine.execute(key, payload, self.payment_handler)
        self.assertEqual(status2, 201)
        self.assertEqual(resp2["charge_id"], "ch_1")
        self.assertTrue(replayed2)
        # Invariant: Handler was NOT called again! (Prevented double charge)
        self.assertEqual(self.execution_counter, 1)

    def test_payload_mismatch_conflict(self):
        key = "idemp_uuid_2002"
        payload_original = {"amount": 1000}
        payload_tampered = {"amount": 9999}  # Same key, different amount!

        self.engine.execute(key, payload_original, self.payment_handler)

        with self.assertRaises(IdempotencyConflictError):
            self.engine.execute(key, payload_tampered, self.payment_handler)

    def test_retry_after_handler_failure(self):
        key = "idemp_uuid_3003"
        payload = {"amount": 250}
        attempts = 0

        def flaky_handler(p):
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("Bank connection timed out!")
            return 200, {"status": "SUCCESS"}

        # First call fails
        with self.assertRaises(RuntimeError):
            self.engine.execute(key, payload, flaky_handler)

        # Retry with same key should be permitted because previous failed
        status, resp, replayed = self.engine.execute(key, payload, flaky_handler)
        self.assertEqual(status, 200)
        self.assertEqual(resp["status"], "SUCCESS")
        self.assertFalse(replayed)


if __name__ == "__main__":
    unittest.main()
