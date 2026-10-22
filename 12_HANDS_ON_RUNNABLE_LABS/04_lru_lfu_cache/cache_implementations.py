"""
True O(1) Cache Implementations:
1. O(1) Least Recently Used (LRU) Cache (Doubly Linked List + Hash Map)
2. O(1) Least Frequently Used (LFU) Cache (Frequency Buckets + Recency Lists)
"""

from typing import Any, Dict, Optional


# -------------------------------------------------------------
# 1. LRU Cache Implementation (O(1))
# -------------------------------------------------------------

class LRUNode:
    def __init__(self, key: Any = None, value: Any = None):
        self.key = key
        self.value = value
        self.prev: Optional["LRUNode"] = None
        self.next: Optional["LRUNode"] = None


class LRUCache:
    """
    O(1) Least Recently Used (LRU) Cache.
    Combines a Doubly Linked List (for recency tracking) with a Hash Map.
    """

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self.capacity = capacity
        self.cache: Dict[Any, LRUNode] = {}

        # Dummy sentinel head and tail nodes
        self.head = LRUNode()
        self.tail = LRUNode()
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node: LRUNode) -> None:
        """Detaches node from its current linked list position."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _add_to_head(self, node: LRUNode) -> None:
        """Splices node directly after the head sentinel (Most Recently Used)."""
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node

    def get(self, key: Any) -> Optional[Any]:
        if key not in self.cache:
            return None
        node = self.cache[key]
        self._remove(node)
        self._add_to_head(node)
        return node.value

    def put(self, key: Any, value: Any) -> None:
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._remove(node)
            self._add_to_head(node)
        else:
            if len(self.cache) >= self.capacity:
                # Evict least recently used (node directly before tail sentinel)
                lru_node = self.tail.prev
                self._remove(lru_node)
                del self.cache[lru_node.key]

            new_node = LRUNode(key, value)
            self.cache[key] = new_node
            self._add_to_head(new_node)

    def __len__(self) -> int:
        return len(self.cache)


# -------------------------------------------------------------
# 2. LFU Cache Implementation (True O(1))
# -------------------------------------------------------------

class DLinkedNode:
    def __init__(self, key: Any = None, value: Any = None, freq: int = 1):
        self.key = key
        self.value = value
        self.freq = freq
        self.prev: Optional["DLinkedNode"] = None
        self.next: Optional["DLinkedNode"] = None


class DLinkedList:
    """Doubly Linked List tracking recency for a specific frequency bucket."""

    def __init__(self):
        self.head = DLinkedNode()
        self.tail = DLinkedNode()
        self.head.next = self.tail
        self.tail.prev = self.head
        self.size = 0

    def add_to_head(self, node: DLinkedNode) -> None:
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node
        self.size += 1

    def remove(self, node: DLinkedNode) -> None:
        node.prev.next = node.next
        node.next.prev = node.prev
        self.size -= 1

    def pop_tail(self) -> Optional[DLinkedNode]:
        if self.size == 0:
            return None
        tail_node = self.tail.prev
        self.remove(tail_node)
        return tail_node


class LFUCache:
    """
    True O(1) Least Frequently Used (LFU) Cache.
    Uses Frequency Buckets of Doubly Linked Lists to break frequency ties via LRU.
    """

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self.capacity = capacity
        self.node_map: Dict[Any, DLinkedNode] = {}
        self.freq_map: Dict[int, DLinkedList] = {}
        self.min_freq = 0

    def _update_frequency(self, node: DLinkedNode) -> None:
        old_freq = node.freq
        self.freq_map[old_freq].remove(node)

        # If min_freq list is now empty, increment min_freq
        if self.min_freq == old_freq and self.freq_map[old_freq].size == 0:
            self.min_freq += 1

        node.freq += 1
        new_freq = node.freq
        if new_freq not in self.freq_map:
            self.freq_map[new_freq] = DLinkedList()
        self.freq_map[new_freq].add_to_head(node)

    def get(self, key: Any) -> Optional[Any]:
        if key not in self.node_map:
            return None
        node = self.node_map[key]
        self._update_frequency(node)
        return node.value

    def put(self, key: Any, value: Any) -> None:
        if key in self.node_map:
            node = self.node_map[key]
            node.value = value
            self._update_frequency(node)
        else:
            if len(self.node_map) >= self.capacity:
                # Evict least frequently used node (and oldest in min_freq bucket)
                min_list = self.freq_map[self.min_freq]
                evicted_node = min_list.pop_tail()
                if evicted_node:
                    del self.node_map[evicted_node.key]

            new_node = DLinkedNode(key, value, freq=1)
            self.node_map[key] = new_node
            self.min_freq = 1
            if 1 not in self.freq_map:
                self.freq_map[1] = DLinkedList()
            self.freq_map[1].add_to_head(new_node)

    def __len__(self) -> int:
        return len(self.node_map)
