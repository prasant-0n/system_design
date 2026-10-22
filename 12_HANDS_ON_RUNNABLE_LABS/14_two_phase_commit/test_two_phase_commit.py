import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from two_phase_commit import Coordinator, Participant, TxState


class TestTwoPhaseCommit(unittest.TestCase):

    def setUp(self):
        self.p1 = Participant("OrderDB")
        self.p2 = Participant("InventoryDB")
        self.p3 = Participant("PaymentLedger")
        self.coordinator = Coordinator([self.p1, self.p2, self.p3])

    def test_successful_commit_all_participants(self):
        mutations = {
            self.p1: {"order_id_101": "PLACED"},
            self.p2: {"item_sku_55": "RESERVED"},
            self.p3: {"payment_ref_88": "CAPTURED"},
        }

        success = self.coordinator.execute_transaction("tx_1001", mutations)
        self.assertTrue(success)

        # Verify state across participants
        self.assertEqual(self.coordinator.get_transaction_status("tx_1001"), TxState.COMMITTED)
        self.assertEqual(self.p1.data_store["order_id_101"], "PLACED")
        self.assertEqual(self.p2.data_store["item_sku_55"], "RESERVED")
        self.assertEqual(self.p3.data_store["payment_ref_88"], "CAPTURED")

        # Verify WAL records
        self.assertIn("tx_1001:COMMIT", self.coordinator.wal)
        self.assertIn("tx_1001:COMMIT", self.p1.wal)

    def test_abort_on_single_participant_failure(self):
        # Participant 2 (Inventory) fails during prepare (out of stock)
        self.p2.should_fail_prepare = True

        mutations = {
            self.p1: {"order_id_102": "PLACED"},
            self.p2: {"item_sku_99": "RESERVED"},
            self.p3: {"payment_ref_89": "CAPTURED"},
        }

        success = self.coordinator.execute_transaction("tx_1002", mutations)
        self.assertFalse(success)

        # Invariant: All must abort atomically
        self.assertEqual(self.coordinator.get_transaction_status("tx_1002"), TxState.ABORTED)
        self.assertNotIn("order_id_102", self.p1.data_store)
        self.assertNotIn("item_sku_99", self.p2.data_store)
        self.assertNotIn("payment_ref_89", self.p3.data_store)

        self.assertEqual(self.p1.state["tx_1002"], TxState.ABORTED)
        self.assertEqual(self.p2.state["tx_1002"], TxState.ABORTED)
        self.assertEqual(self.p3.state["tx_1002"], TxState.ABORTED)

    def test_participant_recovery_from_prepared_state(self):
        # Simulate p1 crashing right after voting PREPARED, while coordinator committed
        tx_id = "tx_crash_test"
        self.p1.prepare(tx_id, {"key": "val"})
        self.assertEqual(self.p1.state[tx_id], TxState.PREPARED)

        # Coordinator recorded commit
        self.coordinator.tx_status[tx_id] = TxState.COMMITTED
        self.coordinator.log(f"{tx_id}:COMMIT")

        # Participant restarts and runs recovery protocol
        self.p1.recover(self.coordinator)

        # Must have transitioned to COMMITTED and applied mutations
        self.assertEqual(self.p1.state[tx_id], TxState.COMMITTED)
        self.assertEqual(self.p1.data_store["key"], "val")


if __name__ == "__main__":
    unittest.main()
