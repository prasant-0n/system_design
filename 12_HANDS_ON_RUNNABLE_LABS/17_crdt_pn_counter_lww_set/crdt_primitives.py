"""
Conflict-Free Replicated Data Types (CRDTs):
1. PNCounter: State-based Positive-Negative Counter.
2. LWWElementSet: Last-Write-Wins Element Set with timestamp-based conflict resolution.

All implementations satisfy Join-Semilattice mathematical invariants:
- Commutativity: A ⊔ B == B ⊔ A
- Associativity: (A ⊔ B) ⊔ C == A ⊔ (B ⊔ C)
- Idempotence: A ⊔ A == A
"""

from typing import Dict, Any, Set, Tuple


class PNCounter:
    """
    Positive-Negative Counter CRDT (State-based / CvRDT).
    """

    def __init__(self, p_counts: Dict[str, int] = None, n_counts: Dict[str, int] = None):
        self.p_counts: Dict[str, int] = dict(p_counts) if p_counts else {}
        self.n_counts: Dict[str, int] = dict(n_counts) if n_counts else {}

    def increment(self, replica_id: str, value: int = 1) -> None:
        if value < 0:
            raise ValueError("Increment value must be non-negative")
        self.p_counts[replica_id] = self.p_counts.get(replica_id, 0) + value

    def decrement(self, replica_id: str, value: int = 1) -> None:
        if value < 0:
            raise ValueError("Decrement value must be non-negative")
        self.n_counts[replica_id] = self.n_counts.get(replica_id, 0) + value

    def value(self) -> int:
        total_p = sum(self.p_counts.values())
        total_n = sum(self.n_counts.values())
        return total_p - total_n

    def merge(self, other: "PNCounter") -> "PNCounter":
        """Computes the Join-Semilattice supremum (pairwise max)."""
        new_p: Dict[str, int] = {}
        all_p_keys = set(self.p_counts.keys()) | set(other.p_counts.keys())
        for k in all_p_keys:
            new_p[k] = max(self.p_counts.get(k, 0), other.p_counts.get(k, 0))

        new_n: Dict[str, int] = {}
        all_n_keys = set(self.n_counts.keys()) | set(other.n_counts.keys())
        for k in all_n_keys:
            new_n[k] = max(self.n_counts.get(k, 0), other.n_counts.get(k, 0))

        return PNCounter(new_p, new_n)


class LWWElementSet:
    """
    Last-Write-Wins Element Set CRDT.
    Uses timestamps to deterministically resolve concurrent add and remove operations.
    """

    def __init__(self, add_set: Dict[Any, float] = None, remove_set: Dict[Any, float] = None):
        self.add_set: Dict[Any, float] = dict(add_set) if add_set else {}
        self.remove_set: Dict[Any, float] = dict(remove_set) if remove_set else {}

    def add(self, element: Any, timestamp: float) -> None:
        if element not in self.add_set or timestamp > self.add_set[element]:
            self.add_set[element] = timestamp

    def remove(self, element: Any, timestamp: float) -> None:
        if element not in self.remove_set or timestamp > self.remove_set[element]:
            self.remove_set[element] = timestamp

    def contains(self, element: Any) -> bool:
        if element not in self.add_set:
            return False
        if element not in self.remove_set:
            return True
        # Bias towards add if timestamps are identical
        return self.add_set[element] >= self.remove_set[element]

    def elements(self) -> Set[Any]:
        return {el for el in self.add_set if self.contains(el)}

    def merge(self, other: "LWWElementSet") -> "LWWElementSet":
        """Merges two sets taking the maximum timestamp for all operations."""
        merged_add: Dict[Any, float] = {}
        all_add = set(self.add_set.keys()) | set(other.add_set.keys())
        for k in all_add:
            merged_add[k] = max(self.add_set.get(k, 0.0), other.add_set.get(k, 0.0))

        merged_rem: Dict[Any, float] = {}
        all_rem = set(self.remove_set.keys()) | set(other.remove_set.keys())
        for k in all_rem:
            merged_rem[k] = max(self.remove_set.get(k, 0.0), other.remove_set.get(k, 0.0))

        return LWWElementSet(merged_add, merged_rem)
