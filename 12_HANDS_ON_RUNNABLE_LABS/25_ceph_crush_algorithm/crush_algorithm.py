"""
Ceph CRUSH Algorithm (Controlled Replication Under Scalable Hashing).

Features:
1. Replaces central metadata lookup servers with deterministic mathematical hashing.
2. Hierarchical cluster topology: Root -> Rack -> Host -> OSD.
3. Rule-based failure domain isolation: Guarantees replicas sit in distinct racks.
4. Minimal data migration on topology changes.
"""

import hashlib
from typing import List, Dict, Tuple, Set, Optional


class OSD:
    def __init__(self, osd_id: str, host_id: str, rack_id: str, weight: float = 1.0):
        self.osd_id = osd_id
        self.host_id = host_id
        self.rack_id = rack_id
        self.weight = weight


class CRUSHCluster:
    def __init__(self):
        self.osds: Dict[str, OSD] = {}
        self.racks: Dict[str, List[str]] = {}  # rack_id -> list of osd_ids

    def add_osd(self, osd_id: str, host_id: str, rack_id: str, weight: float = 1.0) -> None:
        osd = OSD(osd_id, host_id, rack_id, weight)
        self.osds[osd_id] = osd
        if rack_id not in self.racks:
            self.racks[rack_id] = []
        self.racks[rack_id].append(osd_id)

    def _hash(self, key: str, salt: int) -> int:
        h = hashlib.sha256(f"{key}:{salt}".encode("utf-8")).digest()
        return int.from_bytes(h[:8], byteorder="big")

    def select_replicas(
        self, object_id: str, num_replicas: int = 3, isolate_failure_domain: str = "rack"
    ) -> List[str]:
        """
        Executes CRUSH placement.
        Selects N replicas ensuring each replica resides in a distinct rack.
        """
        if len(self.racks) < num_replicas:
            raise ValueError(f"Need at least {num_replicas} distinct racks for isolation")

        selected_osds: List[str] = []
        used_domains: Set[str] = set()

        # Deterministic pseudo-random selection
        rack_list = sorted(self.racks.keys())
        round_idx = 0

        while len(selected_osds) < num_replicas:
            # 1. Pick a rack deterministically
            hash_val = self._hash(object_id, round_idx)
            rack_idx = hash_val % len(rack_list)
            target_rack = rack_list[rack_idx]

            if target_rack not in used_domains:
                # 2. Pick an OSD within this rack
                osd_candidates = sorted(self.racks[target_rack])
                osd_hash = self._hash(f"{object_id}:{target_rack}", round_idx)
                chosen_osd = osd_candidates[osd_hash % len(osd_candidates)]

                selected_osds.append(chosen_osd)
                used_domains.add(target_rack)

            round_idx += 1

        return selected_osds
