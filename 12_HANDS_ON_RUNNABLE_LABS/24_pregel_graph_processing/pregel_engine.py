"""
Google Pregel Bulk Synchronous Parallel (BSP) Graph Engine.

Features:
1. "Think Like a Vertex" programming model.
2. Superstep barrier synchronization.
3. Message mailboxes partitioned between current step and next step.
4. Active / Inactive vertex state machine with automatic reactivation.
5. Concrete implementation: Distributed PageRank.
"""

from typing import List, Dict, Any, Optional
from collections import defaultdict


class Vertex:
    def __init__(self, vertex_id: str, initial_value: Any, out_edges: List[str]):
        self.vertex_id = vertex_id
        self.value = initial_value
        self.out_edges = list(out_edges)
        self.is_active = True
        self.master: Optional["PregelMaster"] = None

    def compute(self, messages: List[Any], superstep: int) -> None:
        raise NotImplementedError

    def send_message(self, target_id: str, message: Any) -> None:
        if self.master:
            self.master.send_message(target_id, message)

    def vote_to_halt(self) -> None:
        self.is_active = False


class PregelMaster:
    def __init__(self, vertices: List[Vertex]):
        self.vertices: Dict[str, Vertex] = {v.vertex_id: v for v in vertices}
        for v in self.vertices.values():
            v.master = self

        # Double-buffered mailboxes: current superstep vs next superstep
        self.current_messages: Dict[str, List[Any]] = defaultdict(list)
        self.next_messages: Dict[str, List[Any]] = defaultdict(list)
        self.superstep = 0

    def send_message(self, target_id: str, message: Any) -> None:
        self.next_messages[target_id].append(message)

    def run(self, max_supersteps: int = 30) -> int:
        """
        Executes supersteps until all vertices halt and no messages are in-flight.
        Returns total supersteps executed.
        """
        while self.superstep < max_supersteps:
            # Check termination invariant: all inactive and no incoming messages
            all_inactive = all(not v.is_active for v in self.vertices.values())
            no_messages = len(self.current_messages) == 0

            if all_inactive and no_messages and self.superstep > 0:
                break

            # Execute active vertices or vertices with incoming messages
            for vid, v in self.vertices.items():
                msgs = self.current_messages.get(vid, [])
                if msgs:
                    # Reactivate vertex if it received a message
                    v.is_active = True

                if v.is_active:
                    v.compute(msgs, self.superstep)

            # Barrier: Swap mailboxes for next superstep
            self.current_messages = self.next_messages
            self.next_messages = defaultdict(list)
            self.superstep += 1

        return self.superstep


class PageRankVertex(Vertex):
    """
    Pregel implementation of PageRank.
    """

    def __init__(self, vertex_id: str, out_edges: List[str], total_vertices: int, damping: float = 0.85):
        # Initial rank = 1.0 / total_vertices
        super().__init__(vertex_id, 1.0 / total_vertices, out_edges)
        self.total_vertices = total_vertices
        self.damping = damping

    def compute(self, messages: List[Any], superstep: int) -> None:
        if superstep >= 1:
            # Sum incoming contributions
            sum_ranks = sum(messages)
            self.value = ((1.0 - self.damping) / self.total_vertices) + (self.damping * sum_ranks)

        # In supersteps 0 to 15, broadcast outgoing contribution
        if superstep < 15:
            if self.out_edges:
                out_msg = self.value / len(self.out_edges)
                for neighbor in self.out_edges:
                    self.send_message(neighbor, out_msg)
        else:
            self.vote_to_halt()
