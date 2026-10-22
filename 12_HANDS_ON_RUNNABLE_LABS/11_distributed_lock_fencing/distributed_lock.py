"""
Distributed Lock with Monotonic Fencing Tokens & Quorum Consensus.

Simulates:
1. Multi-node distributed lock service (Redlock-inspired quorum).
2. Monotonic fencing tokens (Martin Kleppmann's correctness invariant).
3. Target resource / storage engine that rejects stale writes with lower fencing tokens.
4. Process pause (JVM GC / descheduling) handling demonstrating why fencing tokens prevent corruption.
"""

import time
import threading
from typing import Dict, List, Optional, Tuple, Any


class FencingTokenViolationError(Exception):
    """Raised when a storage write is rejected due to a stale fencing token."""
    pass


class LockNode:
    """An individual independent lock node (e.g., Redis instance)."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self._lock = threading.Lock()
        self.held_by: Optional[str] = None
        self.token: Optional[int] = None
        self.expires_at: float = 0.0

    def acquire(self, lock_key: str, client_id: str, token: int, ttl_seconds: float, current_time: Optional[float] = None) -> bool:
        now = time.time() if current_time is None else current_time
        with self._lock:
            # If expired, clear
            if self.held_by is not None and now >= self.expires_at:
                self.held_by = None
                self.token = None

            if self.held_by is None:
                self.held_by = client_id
                self.token = token
                self.expires_at = now + ttl_seconds
                return True
            return False

    def release(self, lock_key: str, client_id: str, token: int) -> bool:
        with self._lock:
            if self.held_by == client_id and self.token == token:
                self.held_by = None
                self.token = None
                self.expires_at = 0.0
                return True
            return False

    def is_locked(self, current_time: Optional[float] = None) -> bool:
        now = time.time() if current_time is None else current_time
        with self._lock:
            if self.held_by is not None and now < self.expires_at:
                return True
            return False


class DistributedLockManager:
    """
    Quorum-based Distributed Lock Coordinator with Monotonic Fencing Tokens.
    """

    def __init__(self, nodes: List[LockNode]):
        if not nodes:
            raise ValueError("Must provide at least one lock node")
        self.nodes = nodes
        self.quorum_size = (len(nodes) // 2) + 1
        self._token_counter = 0
        self._counter_lock = threading.Lock()

    def _next_token(self) -> int:
        with self._counter_lock:
            self._token_counter += 1
            return self._token_counter

    def acquire(self, lock_key: str, client_id: str, ttl_seconds: float, current_time: Optional[float] = None) -> Optional[int]:
        """
        Attempts to acquire lock across majority of nodes.
        Returns the monotonic fencing token if quorum acquired, else None.
        """
        token = self._next_token()
        votes = 0
        now = time.time() if current_time is None else current_time

        for node in self.nodes:
            if node.acquire(lock_key, client_id, token, ttl_seconds, current_time=now):
                votes += 1

        if votes >= self.quorum_size:
            return token
        else:
            # Rollback any acquired nodes
            for node in self.nodes:
                node.release(lock_key, client_id, token)
            return None

    def release(self, lock_key: str, client_id: str, token: int):
        """Releases the lock on all nodes."""
        for node in self.nodes:
            node.release(lock_key, client_id, token)


class ProtectedStorageResource:
    """
    Storage engine / database table that enforces fencing token invariants.
    Invariant: Reject any mutation with token <= highest_seen_token.
    """

    def __init__(self, name: str):
        self.name = name
        self.current_value: Any = None
        self.highest_token: int = 0
        self._lock = threading.Lock()

    def write(self, value: Any, fencing_token: int) -> bool:
        with self._lock:
            if fencing_token <= self.highest_token:
                raise FencingTokenViolationError(
                    f"Rejected write with stale token {fencing_token}. Current highest token is {self.highest_token}."
                )
            self.current_value = value
            self.highest_token = fencing_token
            return True

    def read(self) -> Tuple[Any, int]:
        with self._lock:
            return self.current_value, self.highest_token
