"""
Unit tests for Partitioned Message Broker.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from message_broker import PartitionedMessageBroker


class TestMessageBroker(unittest.TestCase):

    def setUp(self):
        self.broker = PartitionedMessageBroker()
        self.broker.create_topic("orders", num_partitions=3)

    def test_partition_key_ordering_invariance(self):
        """
        All messages with identical partition key (e.g., 'user_101')
        must land on the EXACT SAME partition in strict order.
        """
        user_key = "user_101"
        offsets = []
        partitions = []

        for i in range(10):
            part, offset = self.broker.produce("orders", key=user_key, value=f"Order_{i}")
            partitions.append(part)
            offsets.append(offset)

        # Invariant: Every single message routed to the exact same partition
        self.assertEqual(len(set(partitions)), 1)
        # Offsets are monotonically increasing (0, 1, 2, ...)
        self.assertEqual(offsets, list(range(10)))

    def test_multi_consumer_group_independence(self):
        """
        Two independent consumer groups ('billing' and 'analytics')
        can consume the exact same partition at completely different paces.
        """
        # Produce 5 messages to partition 0
        part_0_key = None
        for i in range(20):
            p, off = self.broker.produce("orders", key=f"k_{i}", value=f"val_{i}")
            if p == 0:
                part_0_key = f"k_{i}"

        # Group 1: 'billing' reads 2 messages and commits offset 2
        msgs_billing = self.broker.consume("orders", group_id="billing", partition_id=0, max_records=2)
        self.assertEqual(len(msgs_billing), 2)
        self.broker.commit_offset("orders", group_id="billing", partition_id=0, offset=2)

        # Group 2: 'analytics' reads 4 messages and commits offset 4
        msgs_analytics = self.broker.consume("orders", group_id="analytics", partition_id=0, max_records=4)
        self.assertGreaterEqual(len(msgs_analytics), 2)
        self.broker.commit_offset("orders", group_id="analytics", partition_id=0, offset=4)

        # Next consume for billing starts at offset 2!
        next_billing = self.broker.consume("orders", group_id="billing", partition_id=0, max_records=1)
        self.assertEqual(next_billing[0].offset, 2)

    def test_log_replay_via_seek(self):
        """
        Verify that consumer can seek backward to offset 0 and replay all messages.
        """
        p, off1 = self.broker.produce("orders", key="order_1", value="Create")
        p, off2 = self.broker.produce("orders", key="order_1", value="Pay")

        # Read both messages and advance offset
        msgs = self.broker.consume("orders", group_id="audit", partition_id=p, max_records=10)
        self.assertEqual(len(msgs), 2)
        self.broker.commit_offset("orders", group_id="audit", partition_id=p, offset=2)

        # Now queue is exhausted
        empty = self.broker.consume("orders", group_id="audit", partition_id=p, max_records=10)
        self.assertEqual(len(empty), 0)

        # Time travel: Seek back to offset 0 and replay!
        self.broker.seek("orders", group_id="audit", partition_id=p, offset=0)
        replayed = self.broker.consume("orders", group_id="audit", partition_id=p, max_records=10)
        self.assertEqual(len(replayed), 2)
        self.assertEqual(replayed[0].value, "Create")
        self.assertEqual(replayed[1].value, "Pay")


if __name__ == "__main__":
    unittest.main()
