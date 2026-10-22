"""
Vector Clock Implementation for Distributed Causality & Conflict Detection.

Enables distributed nodes to determine whether two events are causally related
(A happened before B, or B happened before A) or occurred concurrently (A || B).
"""

from typing import Dict, Optional


class VectorClock:
    """
    Vector Clock representation maintaining a map of node_id -> sequence counter.
    """

    def __init__(self, node_id: str, initial_clock: Optional[Dict[str, int]] = None):
        self.node_id = node_id
        self.clock: Dict[str, int] = dict(initial_clock) if initial_clock else {}

    def tick(self) -> "VectorClock":
        """Increments this node's logical clock by 1 for an internal or send event."""
        self.clock[self.node_id] = self.clock.get(self.node_id, 0) + 1
        return self

    def send_event(self) -> "VectorClock":
        """Prepares a vector clock snapshot to attach to an outgoing message."""
        self.tick()
        return self.clone()

    def receive_event(self, received_clock: "VectorClock") -> "VectorClock":
        """
        Merges an incoming vector clock from a network message:
        1. V_local[k] = max(V_local[k], V_msg[k]) for all k
        2. V_local[node_id] += 1 (local receive event)
        """
        all_nodes = set(self.clock.keys()).union(received_clock.clock.keys())
        for node in all_nodes:
            self.clock[node] = max(self.clock.get(node, 0), received_clock.clock.get(node, 0))
        self.tick()
        return self

    def clone(self) -> "VectorClock":
        return VectorClock(self.node_id, dict(self.clock))

    def __le__(self, other: "VectorClock") -> bool:
        """
        Returns True if self <= other:
        For all nodes k: self.clock[k] <= other.clock[k]
        """
        all_nodes = set(self.clock.keys()).union(other.clock.keys())
        return all(self.clock.get(k, 0) <= other.clock.get(k, 0) for k in all_nodes)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VectorClock):
            return False
        all_nodes = set(self.clock.keys()).union(other.clock.keys())
        return all(self.clock.get(k, 0) == other.clock.get(k, 0) for k in all_nodes)

    def happened_before(self, other: "VectorClock") -> bool:
        """
        Returns True if self strictly causally preceded other (self -> other):
        self <= other and self != other
        """
        return self <= other and self != other

    def concurrent_with(self, other: "VectorClock") -> bool:
        """
        Returns True if self and other are concurrent (conflict detected! self || other):
        Neither happened before the other.
        """
        return not (self <= other) and not (other <= self)

    def __repr__(self) -> str:
        items = ", ".join(f"{k}:{v}" for k, v in sorted(self.clock.items()))
        return f"VC({self.node_id})[{items}]"
