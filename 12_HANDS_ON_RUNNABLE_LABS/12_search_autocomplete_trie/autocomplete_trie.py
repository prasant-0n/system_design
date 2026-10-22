"""
Search Autocomplete System with Cached Top-K Prefix Trie.

Features:
1. Trie data structure with cached Top-K suggestions at each prefix node.
2. O(L) prefix search latency instead of traversing entire subtrees.
3. Frequency scoring and incremental updates.
4. Top-K ranking propagation.
"""

import heapq
from typing import List, Dict, Optional, Tuple


class TrieNode:
    def __init__(self):
        self.children: Dict[str, "TrieNode"] = {}
        self.is_terminal: bool = False
        self.query: Optional[str] = None
        self.frequency: float = 0.0
        # Cached list of (query, frequency) sorted by frequency descending
        self.top_k_cache: List[Tuple[str, float]] = []


class AutocompleteTrie:
    def __init__(self, max_cached_suggestions: int = 10):
        self.root = TrieNode()
        self.max_cached = max_cached_suggestions

    def insert(self, query: str, weight: float = 1.0) -> None:
        """
        Inserts or increments frequency of a query, updating the path nodes
        and their cached Top-K lists.
        """
        curr = self.root
        path = [curr]

        for char in query.lower():
            if char not in curr.children:
                curr.children[char] = TrieNode()
            curr = curr.children[char]
            path.append(curr)

        curr.is_terminal = True
        curr.query = query.lower()
        curr.frequency += weight

        final_freq = curr.frequency
        target_query = curr.query

        # Propagate top-K cache update backwards up to the root
        for node in path:
            self._update_node_cache(node, target_query, final_freq)

    def _update_node_cache(self, node: TrieNode, query: str, freq: float) -> None:
        """Maintains top-K suggestions sorted by frequency descending."""
        # Replace existing or append
        updated = False
        new_list = []
        for q, f in node.top_k_cache:
            if q == query:
                new_list.append((query, freq))
                updated = True
            else:
                new_list.append((q, f))

        if not updated:
            new_list.append((query, freq))

        # Sort descending by frequency, then lexicographically
        new_list.sort(key=lambda x: (-x[1], x[0]))

        # Keep top max_cached
        node.top_k_cache = new_list[: self.max_cached]

    def search(self, prefix: str, k: int = 5) -> List[Tuple[str, float]]:
        """
        Retrieves top-K autocomplete suggestions for a given prefix in O(L) time.
        """
        curr = self.root
        for char in prefix.lower():
            if char not in curr.children:
                return []
            curr = curr.children[char]

        # Returns pre-aggregated top suggestions directly from node cache
        return curr.top_k_cache[:k]
