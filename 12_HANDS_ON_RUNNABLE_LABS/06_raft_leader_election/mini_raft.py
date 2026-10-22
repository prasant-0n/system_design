"""
Mini-Raft Consensus Simulator: Leader Election, Terms, and Split-Vote Handling.

Simulates the discrete state machine replication of the Raft consensus protocol
(Ongaro & Ousterhout, Stanford 2014).
"""

from enum import Enum
import random
from typing import Dict, List, Optional, Tuple


class RaftRole(Enum):
    FOLLOWER = "FOLLOWER"
    CANDIDATE = "CANDIDATE"
    LEADER = "LEADER"


class RaftNode:
    """
    Individual Raft consensus participant node.
    """

    def __init__(
        self,
        node_id: str,
        peers: List[str],
        min_timeout_ticks: int = 3,
        max_timeout_ticks: int = 6,
    ):
        self.node_id = node_id
        self.peers = peers
        self.min_timeout_ticks = min_timeout_ticks
        self.max_timeout_ticks = max_timeout_ticks

        # Persistent State
        self.current_term = 0
        self.voted_for: Optional[str] = None
        self.role = RaftRole.FOLLOWER

        # Volatile Leader Election State
        self.votes_received = 0
        self.leader_id: Optional[str] = None
        self.ticks_since_heartbeat = 0
        self.election_timeout_ticks = self._random_election_timeout()

    def _random_election_timeout(self) -> int:
        return random.randint(self.min_timeout_ticks, self.max_timeout_ticks)

    def reset_election_timer(self) -> None:
        self.ticks_since_heartbeat = 0
        self.election_timeout_ticks = self._random_election_timeout()

    def handle_request_vote(self, term: int, candidate_id: str) -> Tuple[int, bool]:
        """
        Invoked by candidates to gather votes.
        Receiver implementation:
        1. Reply False if term < current_term.
        2. If voted_for is null or candidate_id, and term >= current_term, grant vote.
        """
        if term > self.current_term:
            self.current_term = term
            self.role = RaftRole.FOLLOWER
            self.voted_for = None
            self.leader_id = None

        if term == self.current_term and (self.voted_for is None or self.voted_for == candidate_id):
            self.voted_for = candidate_id
            self.reset_election_timer()
            return self.current_term, True

        return self.current_term, False

    def handle_append_entries(self, term: int, leader_id: str) -> Tuple[int, bool]:
        """
        Invoked by leader to replicate log entries and serve as periodic heartbeat.
        Receiver implementation:
        1. Reply False if term < current_term.
        2. Reset election timer and recognize leader.
        """
        if term > self.current_term:
            self.current_term = term
            self.role = RaftRole.FOLLOWER
            self.voted_for = None

        if term >= self.current_term:
            self.role = RaftRole.FOLLOWER
            self.leader_id = leader_id
            self.reset_election_timer()
            return self.current_term, True

        return self.current_term, False

    def start_election(self, cluster: "RaftCluster") -> bool:
        """Transitions to Candidate, increments Term, and solicits votes from peers."""
        self.role = RaftRole.CANDIDATE
        self.current_term += 1
        self.voted_for = self.node_id
        self.votes_received = 1  # Vote for self
        self.leader_id = None
        self.reset_election_timer()

        # Quorum threshold: majority of all cluster nodes
        quorum = (len(self.peers) + 1) // 2 + 1

        for peer_id in self.peers:
            peer = cluster.get_node(peer_id)
            if peer and peer.is_alive:
                term, granted = peer.handle_request_vote(self.current_term, self.node_id)
                if granted:
                    self.votes_received += 1
                elif term > self.current_term:
                    self.current_term = term
                    self.role = RaftRole.FOLLOWER
                    self.voted_for = None
                    return False

        if self.votes_received >= quorum:
            self.role = RaftRole.LEADER
            self.leader_id = self.node_id
            # Send immediate initial heartbeat to suppress other candidates
            self.broadcast_heartbeats(cluster)
            return True

        return False

    def broadcast_heartbeats(self, cluster: "RaftCluster") -> None:
        """Leader broadcasts empty AppendEntries heartbeats to maintain authority."""
        if self.role != RaftRole.LEADER:
            return
        for peer_id in self.peers:
            peer = cluster.get_node(peer_id)
            if peer and peer.is_alive:
                peer.handle_append_entries(self.current_term, self.node_id)


class RaftCluster:
    """Simulated network cluster of Raft nodes with tick execution."""

    def __init__(self, node_ids: List[str]):
        self.nodes: Dict[str, RaftNode] = {}
        self.active_status: Dict[str, bool] = {nid: True for nid in node_ids}

        for nid in node_ids:
            peers = [p for p in node_ids if p != nid]
            self.nodes[nid] = RaftNode(nid, peers)

    def get_node(self, node_id: str) -> Optional[RaftNode]:
        node = self.nodes.get(node_id)
        if node:
            node.is_alive = self.active_status.get(node_id, True)
        return node

    def crash_node(self, node_id: str) -> None:
        self.active_status[node_id] = False
        if node_id in self.nodes:
            self.nodes[node_id].role = RaftRole.FOLLOWER
            self.nodes[node_id].leader_id = None

    def recover_node(self, node_id: str) -> None:
        self.active_status[node_id] = True
        if node_id in self.nodes:
            self.nodes[node_id].reset_election_timer()

    def get_leader(self) -> Optional[RaftNode]:
        for nid, active in self.active_status.items():
            if active and self.nodes[nid].role == RaftRole.LEADER:
                return self.nodes[nid]
        return None

    def tick(self) -> None:
        """Simulates 1 discrete clock tick across the entire cluster."""
        # 1. Leaders broadcast heartbeats
        for nid, active in self.active_status.items():
            if active and self.nodes[nid].role == RaftRole.LEADER:
                self.nodes[nid].broadcast_heartbeats(self)

        # 2. Followers and candidates increment election timers
        for nid, active in self.active_status.items():
            if active and self.nodes[nid].role != RaftRole.LEADER:
                node = self.nodes[nid]
                node.ticks_since_heartbeat += 1
                if node.ticks_since_heartbeat >= node.election_timeout_ticks:
                    node.start_election(self)
