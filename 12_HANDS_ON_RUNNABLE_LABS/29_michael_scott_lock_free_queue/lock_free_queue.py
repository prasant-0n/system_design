"""Michael & Scott (PODC 1996) Lock-Free Concurrent FIFO Queue.

Implements:
1. AtomicReference with Compare-And-Swap (CAS)
2. Sentinel node linked queue topology
3. Cooperative tail advancement (helping mechanism)
4. Multi-threaded thread-safe enqueue and dequeue operations without mutexes
"""

import threading
from typing import Any, Optional, Generic, TypeVar

T = TypeVar('T')


class AtomicReference(Generic[T]):
    """Simulates a hardware atomic memory word with Compare-And-Swap (CAS)."""

    def __init__(self, initial_value: Optional[T] = None):
        self._value: Optional[T] = initial_value
        self._lock = threading.Lock()  # Simulates hardware atomic bus-lock (CMPXCHG)

    def get(self) -> Optional[T]:
        with self._lock:
            return self._value

    def set(self, new_value: Optional[T]) -> None:
        with self._lock:
            self._value = new_value

    def compare_and_set(self, expected: Optional[T], desired: Optional[T]) -> bool:
        """Atomic Compare-And-Swap (CAS).

        Returns True if value equaled expected and was updated to desired.
        """
        with self._lock:
            if self._value == expected:
                self._value = desired
                return True
            return False


class Node(Generic[T]):
    """Queue linked list node."""

    def __init__(self, value: Optional[T] = None):
        self.value: Optional[T] = value
        self.next: AtomicReference["Node[T]"] = AtomicReference(None)


class MichaelScottQueue(Generic[T]):
    """Lock-Free Non-Blocking Concurrent Queue (Michael & Scott, 1996)."""

    def __init__(self):
        # Initialize with dummy sentinel node so head and tail are never null
        sentinel: Node[T] = Node(None)
        self.head: AtomicReference[Node[T]] = AtomicReference(sentinel)
        self.tail: AtomicReference[Node[T]] = AtomicReference(sentinel)

    def enqueue(self, value: T) -> None:
        """Insert value into tail of queue without blocking."""
        node = Node(value)
        while True:
            tail = self.tail.get()
            next_node = tail.next.get()

            # Verify consistency: tail hasn't changed
            if tail == self.tail.get():
                if next_node is None:
                    # Tail is pointing to last node; attempt linking new node
                    if tail.next.compare_and_set(None, node):
                        # Successfully linked; now attempt to swing tail to new node
                        self.tail.compare_and_set(tail, node)
                        return
                else:
                    # Tail is lagging behind; help advance it forward
                    self.tail.compare_and_set(tail, next_node)

    def dequeue(self) -> Optional[T]:
        """Remove and return value from head of queue without blocking.

        Returns None if queue is empty.
        """
        while True:
            head = self.head.get()
            tail = self.tail.get()
            first = head.next.get()

            # Verify consistency: head hasn't changed
            if head == self.head.get():
                if head == tail:
                    if first is None:
                        return None  # Queue is empty
                    # Tail is lagging; help advance it forward
                    self.tail.compare_and_set(tail, first)
                else:
                    if first is None:
                        continue
                    value = first.value
                    # Attempt to advance head pointer past sentinel
                    if self.head.compare_and_set(head, first):
                        return value

    def is_empty(self) -> bool:
        head = self.head.get()
        return head.next.get() is None
