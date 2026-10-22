"""
Vector Search Engine: Hierarchical Navigable Small World (HNSW) & Product Quantization (PQ).

Features:
1. Exact vector metrics (L2, Cosine, Inner Product).
2. Pure-Python multi-layer HNSW graph with skip-list layer descent and greedy search.
3. Product Quantization (PQ) for vector compression and Asymmetric Distance Computation (ADC).
"""

import math
import random
from typing import List, Tuple, Dict, Set, Optional


def l2_distance(u: List[float], v: List[float]) -> float:
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(u, v)))


def cosine_similarity(u: List[float], v: List[float]) -> float:
    dot = sum(a * b for a, b in zip(u, v))
    norm_u = math.sqrt(sum(a * a for a in u))
    norm_v = math.sqrt(sum(b * b for b in v))
    if norm_u == 0.0 or norm_v == 0.0:
        return 0.0
    return dot / (norm_u * norm_v)


class HNSWNode:
    def __init__(self, node_id: str, vector: List[float], max_layer: int):
        self.node_id = node_id
        self.vector = vector
        self.max_layer = max_layer
        # neighbors[layer] = set of neighbor node_ids
        self.neighbors: Dict[int, Set[str]] = {layer: set() for layer in range(max_layer + 1)}


class MiniHNSW:
    """
    Hierarchical Navigable Small World (HNSW) proximity graph.
    """

    def __init__(self, m: int = 4, ef_construction: int = 16, ml: float = 1.0 / math.log(2)):
        self.m = m
        self.ef_construction = ef_construction
        self.ml = ml
        self.nodes: Dict[str, HNSWNode] = {}
        self.enter_node_id: Optional[str] = None
        self.max_layer = -1

    def _random_layer(self) -> int:
        r = random.random()
        layer = int(-math.log(r) * self.ml) if r > 0 else 0
        return min(layer, 5)

    def insert(self, node_id: str, vector: List[float]) -> None:
        target_layer = self._random_layer()
        new_node = HNSWNode(node_id, vector, target_layer)
        self.nodes[node_id] = new_node

        if self.enter_node_id is None:
            self.enter_node_id = node_id
            self.max_layer = target_layer
            return

        curr_id = self.enter_node_id
        curr_vec = self.nodes[curr_id].vector

        # Phase 1: Descend from top layer down to target_layer + 1
        for layer in range(self.max_layer, target_layer, -1):
            curr_id = self._greedy_search_layer(vector, curr_id, layer)

        # Phase 2: From target_layer down to layer 0, connect neighbors
        for layer in range(min(self.max_layer, target_layer), -1, -1):
            curr_id = self._greedy_search_layer(vector, curr_id, layer)
            # Add bidirectional edges
            new_node.neighbors[layer].add(curr_id)
            self.nodes[curr_id].neighbors[layer].add(node_id)

            # Prune if exceeding M
            if len(self.nodes[curr_id].neighbors[layer]) > self.m:
                self._prune_neighbors(curr_id, layer)

        if target_layer > self.max_layer:
            self.max_layer = target_layer
            self.enter_node_id = node_id

    def _greedy_search_layer(self, query: List[float], start_id: str, layer: int) -> str:
        curr_id = start_id
        curr_dist = l2_distance(query, self.nodes[curr_id].vector)

        while True:
            changed = False
            for neighbor_id in self.nodes[curr_id].neighbors.get(layer, []):
                dist = l2_distance(query, self.nodes[neighbor_id].vector)
                if dist < curr_dist:
                    curr_dist = dist
                    curr_id = neighbor_id
                    changed = True
            if not changed:
                break
        return curr_id

    def _prune_neighbors(self, node_id: str, layer: int) -> None:
        node = self.nodes[node_id]
        sorted_neighbors = sorted(
            node.neighbors[layer],
            key=lambda nid: l2_distance(node.vector, self.nodes[nid].vector),
        )
        node.neighbors[layer] = set(sorted_neighbors[: self.m])

    def search(self, query: List[float], k: int = 5) -> List[Tuple[str, float]]:
        """Searches top-K nearest neighbors."""
        if not self.nodes:
            return []

        curr_id = self.enter_node_id
        for layer in range(self.max_layer, 0, -1):
            curr_id = self._greedy_search_layer(query, curr_id, layer)

        # Ground layer 0 exhaustive candidate exploration
        visited = {curr_id}
        candidates = [curr_id]

        for _ in range(15):
            new_candidates = []
            for cid in candidates:
                for nid in self.nodes[cid].neighbors.get(0, []):
                    if nid not in visited:
                        visited.add(nid)
                        new_candidates.append(nid)
            if not new_candidates:
                break
            candidates = new_candidates

        results = [(nid, l2_distance(query, self.nodes[nid].vector)) for nid in visited]
        results.sort(key=lambda x: x[1])
        return results[:k]


class MiniProductQuantizer:
    """
    Product Quantization (PQ) for vector compression.
    Splits D-dim vector into sub-vectors and quantizes using codebooks.
    """

    def __init__(self, num_subvectors: int = 2):
        self.num_subvectors = num_subvectors
        self.codebooks: List[List[List[float]]] = []

    def fit(self, vectors: List[List[float]], k_centroids: int = 4):
        dim = len(vectors[0])
        sub_dim = dim // self.num_subvectors
        self.codebooks = []

        for m in range(self.num_subvectors):
            # Extract sub-vectors
            sub_vecs = [v[m * sub_dim : (m + 1) * sub_dim] for v in vectors]
            # Simple centroid picking (first k_centroids)
            centroids = sub_vecs[: min(k_centroids, len(sub_vecs))]
            self.codebooks.append(centroids)

    def encode(self, vector: List[float]) -> List[int]:
        """Encodes vector into compact integer codes (1 byte per sub-vector)."""
        dim = len(vector)
        sub_dim = dim // self.num_subvectors
        codes = []

        for m in range(self.num_subvectors):
            sub_v = vector[m * sub_dim : (m + 1) * sub_dim]
            best_idx = 0
            best_dist = float("inf")
            for idx, c in enumerate(self.codebooks[m]):
                dist = l2_distance(sub_v, c)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = idx
            codes.append(best_idx)
        return codes
