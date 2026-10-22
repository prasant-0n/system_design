"""
Consistent Hashing Ring with Virtual Nodes.

Pioneered by David Karger et al. (MIT, 1997) and used in Amazon Dynamo,
Apache Cassandra, and modern distributed caches.
"""

import bisect
import hashlib
from typing import Dict, List, Optional, Set


class ConsistentHashRing:
    """
    Consistent Hash Ring mapping arbitrary keys to physical server nodes
    with virtual node replication for uniform distribution.
    """

    def __init__(self, num_vnodes: int = 150):
        if num_vnodes <= 0:
            raise ValueError("num_vnodes must be a positive integer")
        self.num_vnodes = num_vnodes
        self.ring_keys: List[int] = []  # Sorted list of virtual node hashes
        self.ring: Dict[int, str] = {}   # Maps hash -> physical node ID
        self.nodes: Set[str] = set()    # Set of physical node IDs

    def _hash(self, key: str) -> int:
        """Computes a 32-bit unsigned integer hash using MD5."""
        digest = hashlib.md5(key.encode("utf-8")).hexdigest()
        return int(digest[:8], 16)

    def add_node(self, node_id: str) -> None:
        """Adds a physical node and its virtual nodes to the ring."""
        if node_id in self.nodes:
            return
        self.nodes.add(node_id)
        for i in range(self.num_vnodes):
            vnode_key = f"{node_id}#vnode-{i}"
            h = self._hash(vnode_key)
            self.ring[h] = node_id
            bisect.insort(self.ring_keys, h)

    def remove_node(self, node_id: str) -> None:
        """Removes a physical node and all its virtual nodes from the ring."""
        if node_id not in self.nodes:
            return
        self.nodes.remove(node_id)
        for i in range(self.num_vnodes):
            vnode_key = f"{node_id}#vnode-{i}"
            h = self._hash(vnode_key)
            if h in self.ring:
                del self.ring[h]
                idx = bisect.bisect_left(self.ring_keys, h)
                if idx < len(self.ring_keys) and self.ring_keys[idx] == h:
                    del self.ring_keys[idx]

    def get_node(self, key: str) -> Optional[str]:
        """
        Locates the physical node responsible for a given key.
        Searches clockwise on the ring for the first virtual node hash >= key_hash.
        """
        if not self.ring_keys:
            return None

        h = self._hash(key)
        idx = bisect.bisect_right(self.ring_keys, h)
        # Wrap around to the start of the ring if past the end
        if idx == len(self.ring_keys):
            idx = 0

        vnode_hash = self.ring_keys[idx]
        return self.ring[vnode_hash]

    def get_preference_list(self, key: str, n: int) -> List[str]:
        """
        Returns N distinct physical nodes for quorum replication (Dynamo-style).
        Walks clockwise around the ring until N unique physical nodes are found.
        """
        if not self.nodes or n <= 0:
            return []

        target_count = min(n, len(self.nodes))
        h = self._hash(key)
        idx = bisect.bisect_right(self.ring_keys, h)
        total_vnodes = len(self.ring_keys)

        preference_list: List[str] = []
        seen: Set[str] = set()

        for step in range(total_vnodes):
            curr_idx = (idx + step) % total_vnodes
            node = self.ring[self.ring_keys[curr_idx]]
            if node not in seen:
                seen.add(node)
                preference_list.append(node)
                if len(preference_list) == target_count:
                    break

        return preference_list

    def get_distribution_stats(self, keys: List[str]) -> Dict[str, int]:
        """Returns the count of keys mapped to each physical node."""
        distribution: Dict[str, int] = {node: 0 for node in self.nodes}
        for k in keys:
            node = self.get_node(k)
            if node:
                distribution[node] += 1
        return distribution
