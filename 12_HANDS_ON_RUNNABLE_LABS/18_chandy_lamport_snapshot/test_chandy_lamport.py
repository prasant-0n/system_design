import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from chandy_lamport import DistributedSnapshotCluster


class TestChandyLamportSnapshot(unittest.TestCase):

    def test_consistent_snapshot_with_in_flight_messages(self):
        # 3 processes: P1, P2, P3 with total initial balance = 1000
        # Ring topology: P1 -> P2 -> P3 -> P1
        balances = {"P1": 500, "P2": 300, "P3": 200}
        topology = [("P1", "P2"), ("P2", "P3"), ("P3", "P1")]

        cluster = DistributedSnapshotCluster(balances, topology)
        self.assertEqual(cluster.total_system_balance(), 1000)

        # 1. P1 transfers 150 to P2 (Message in flight on P1 -> P2 channel)
        cluster.processes["P1"].transfer("P2", 150)
        self.assertEqual(cluster.processes["P1"].balance, 350)

        # 2. P1 initiates snapshot
        cluster.processes["P1"].initiate_snapshot()
        self.assertEqual(cluster.processes["P1"].recorded_balance, 350)

        # Now in channel P1 -> P2 we have: [TRANSFER $150, MARKER from P1]
        p1_to_p2 = cluster.processes["P1"].outgoing_channels["P2"]
        self.assertEqual(len(p1_to_p2.queue), 2)

        # 3. P2 receives the TRANSFER $150 message BEFORE the marker
        transfer_msg = p1_to_p2.receive()
        cluster.processes["P2"].process_incoming_message("P1", transfer_msg)
        self.assertEqual(cluster.processes["P2"].balance, 450)

        # 4. P2 receives MARKER from P1
        marker_msg = p1_to_p2.receive()
        cluster.processes["P2"].process_incoming_message("P1", marker_msg)
        # P2 records state = 450
        self.assertEqual(cluster.processes["P2"].recorded_balance, 450)

        # P2 sends marker to P3
        p2_to_p3 = cluster.processes["P2"].outgoing_channels["P3"]
        marker_p2 = p2_to_p3.receive()
        cluster.processes["P3"].process_incoming_message("P2", marker_p2)
        self.assertEqual(cluster.processes["P3"].recorded_balance, 200)

        # P3 sends marker to P1
        p3_to_p1 = cluster.processes["P3"].outgoing_channels["P1"]
        marker_p3 = p3_to_p1.receive()
        cluster.processes["P1"].process_incoming_message("P3", marker_p3)

        # Invariant: Snapshot Total MUST EXACTLY EQUAL 1000!
        # P1 recorded 350 + P2 recorded 450 + P3 recorded 200 = 1000
        self.assertEqual(cluster.snapshot_total(), 1000)

    def test_in_flight_channel_recording(self):
        """Test case where transfer is sent AFTER initiator takes snapshot, so it is captured in channel."""
        balances = {"P1": 500, "P2": 300}
        topology = [("P1", "P2"), ("P2", "P1")]

        cluster = DistributedSnapshotCluster(balances, topology)

        # P1 takes snapshot FIRST
        cluster.processes["P1"].initiate_snapshot()
        self.assertEqual(cluster.processes["P1"].recorded_balance, 500)

        # P2 transfers 100 to P1 BEFORE P2 receives marker
        cluster.processes["P2"].transfer("P1", 100)

        # P2 receives marker from P1
        p1_to_p2 = cluster.processes["P1"].outgoing_channels["P2"]
        marker_from_p1 = p1_to_p2.receive()
        cluster.processes["P2"].process_incoming_message("P1", marker_from_p1)
        # P2 records its state AFTER the transfer (200)
        self.assertEqual(cluster.processes["P2"].recorded_balance, 200)

        # Now P1 receives the $100 transfer from P2 while P1 is recording on channel P2 -> P1
        p2_to_p1 = cluster.processes["P2"].outgoing_channels["P1"]
        transfer_from_p2 = p2_to_p1.receive()
        cluster.processes["P1"].process_incoming_message("P2", transfer_from_p2)

        # P1 receives marker from P2, closing channel recording
        marker_from_p2 = p2_to_p1.receive()
        cluster.processes["P1"].process_incoming_message("P2", marker_from_p2)

        # Verified: P1 recorded state was 500, P2 recorded state was 200, and channel recorded 100
        # 500 + 200 + 100 = 800 (Consistent Cut Invariant Preserved!)
        self.assertEqual(cluster.snapshot_total(), 800)


if __name__ == "__main__":
    unittest.main()
