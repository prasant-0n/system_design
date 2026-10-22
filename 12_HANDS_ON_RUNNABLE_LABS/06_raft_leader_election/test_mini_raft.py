"""
Unit tests for Mini-Raft Consensus Simulator.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from mini_raft import RaftCluster, RaftRole


class TestMiniRaft(unittest.TestCase):

    def test_leader_election_in_healthy_cluster(self):
        # 5-node Raft cluster (Quorum threshold = 3)
        cluster = RaftCluster(["node-1", "node-2", "node-3", "node-4", "node-5"])

        # Initially no leader
        self.assertIsNone(cluster.get_leader())

        # Advance discrete clock ticks until an election timer fires and elects a leader
        for _ in range(15):
            cluster.tick()
            if cluster.get_leader() is not None:
                break

        leader = cluster.get_leader()
        self.assertIsNotNone(leader, "A leader should have been elected within 15 ticks")
        self.assertEqual(leader.role, RaftRole.LEADER)
        self.assertGreater(leader.current_term, 0)

        # Invariant: Exactly ONE leader should exist in the cluster
        leaders = [n for n in cluster.nodes.values() if n.role == RaftRole.LEADER]
        self.assertEqual(len(leaders), 1)

    def test_leader_crash_and_failover_re_election(self):
        cluster = RaftCluster(["s1", "s2", "s3"])

        # Run until initial leader is elected
        for _ in range(15):
            cluster.tick()
            if cluster.get_leader():
                break

        old_leader = cluster.get_leader()
        self.assertIsNotNone(old_leader)
        old_leader_id = old_leader.node_id
        old_term = old_leader.current_term

        # Kill the leader!
        cluster.crash_node(old_leader_id)
        self.assertIsNone(cluster.get_leader())

        # Run ticks for remaining 2 nodes to detect heartbeat loss and elect new leader
        for _ in range(20):
            cluster.tick()
            new_leader = cluster.get_leader()
            if new_leader and new_leader.node_id != old_leader_id:
                break

        new_leader = cluster.get_leader()
        self.assertIsNotNone(new_leader, "Remaining nodes should have elected a new leader")
        self.assertNotEqual(new_leader.node_id, old_leader_id)
        # Term must have advanced
        self.assertGreater(new_leader.current_term, old_term)

    def test_partition_loss_of_quorum(self):
        """
        In a 5-node cluster, if 3 nodes are dead (only 2 alive),
        quorum (3) cannot be formed, so NO candidate can become leader!
        """
        cluster = RaftCluster(["n1", "n2", "n3", "n4", "n5"])

        # Crash 3 out of 5 nodes
        cluster.crash_node("n3")
        cluster.crash_node("n4")
        cluster.crash_node("n5")

        # Run 20 ticks
        for _ in range(20):
            cluster.tick()

        # Quorum cannot be reached, so no leader can be elected
        self.assertIsNone(cluster.get_leader())


if __name__ == "__main__":
    unittest.main()
