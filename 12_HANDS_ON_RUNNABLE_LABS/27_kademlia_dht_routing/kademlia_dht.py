"""Kademlia Distributed Hash Table (DHT) Routing Engine.

Implements:
1. XOR metric distance computation: d(x, y) = x ^ y
2. K-buckets routing table with logarithmic distance partitioning
3. Kademlia node contact management and replacement policies
4. Iterative lookup algorithm (alpha concurrency) for key-value routing
"""

import hashlib
from typing import List, Dict, Optional, Tuple, Set


def xor_distance(id1: int, id2: int) -> int:
    """Calculate the XOR metric distance between two node IDs."""
    return id1 ^ id2


class Contact:
    """Represents a node contact in the Kademlia network."""

    def __init__(self, node_id: int, ip: str = "127.0.0.1", port: int = 8000):
        self.node_id = node_id
        self.ip = ip
        self.port = port

    def __repr__(self) -> str:
        return f"Contact(id={self.node_id:#06x}, {self.ip}:{self.port})"

    def __eq__(self, other) -> bool:
        if isinstance(other, Contact):
            return self.node_id == other.node_id
        return False

    def __hash__(self) -> int:
        return hash(self.node_id)


class KBucket:
    """A single K-bucket storing up to k contacts."""

    def __init__(self, k_size: int = 4):
        self.k_size = k_size
        self.contacts: List[Contact] = []

    def update(self, contact: Contact) -> bool:
        """Insert or refresh a contact.

        Returns True if contact was added/refreshed, False if bucket full.
        """
        if contact in self.contacts:
            self.contacts.remove(contact)
            self.contacts.append(contact)  # Move to tail (most recently seen)
            return True

        if len(self.contacts) < self.k_size:
            self.contacts.append(contact)
            return True

        return False  # Bucket is full

    def remove(self, contact: Contact) -> None:
        if contact in self.contacts:
            self.contacts.remove(contact)

    def __len__(self) -> int:
        return len(self.contacts)


class RoutingTable:
    """Routing table containing buckets for logarithmic distance partitions."""

    def __init__(self, local_node_id: int, num_bits: int = 16, k_size: int = 4):
        self.local_node_id = local_node_id
        self.num_bits = num_bits
        self.k_size = k_size
        self.buckets: List[KBucket] = [KBucket(k_size) for _ in range(num_bits)]

    def _get_bucket_index(self, node_id: int) -> int:
        dist = xor_distance(self.local_node_id, node_id)
        if dist == 0:
            return 0
        # Determine bit position of most significant 1-bit
        return min(dist.bit_length() - 1, self.num_bits - 1)

    def add_contact(self, contact: Contact) -> bool:
        """Add or refresh contact in appropriate bucket."""
        if contact.node_id == self.local_node_id:
            return False
        idx = self._get_bucket_index(contact.node_id)
        return self.buckets[idx].update(contact)

    def find_closest(self, target_id: int, count: Optional[int] = None) -> List[Contact]:
        """Find the 'count' closest contacts to target_id."""
        k = count or self.k_size
        all_contacts: List[Contact] = []
        for bucket in self.buckets:
            all_contacts.extend(bucket.contacts)

        all_contacts.sort(key=lambda c: xor_distance(c.node_id, target_id))
        return all_contacts[:k]


class KademliaNode:
    """A full simulated Kademlia node with DHT storage and RPC routing."""

    def __init__(self, node_id: int, num_bits: int = 16, k_size: int = 4):
        self.node_id = node_id
        self.contact = Contact(node_id)
        self.routing_table = RoutingTable(node_id, num_bits=num_bits, k_size=k_size)
        self.storage: Dict[int, str] = {}  # key_id -> value string
        self.network: Optional[Dict[int, "KademliaNode"]] = None

    def attach_network(self, network: Dict[int, "KademliaNode"]) -> None:
        """Connect node to a simulated network registry."""
        self.network = network
        self.network[self.node_id] = self

    # RPC methods
    def rpc_ping(self, sender: Contact) -> bool:
        self.routing_table.add_contact(sender)
        return True

    def rpc_store(self, sender: Contact, key: int, value: str) -> bool:
        self.routing_table.add_contact(sender)
        self.storage[key] = value
        return True

    def rpc_find_node(self, sender: Contact, target_id: int) -> List[Contact]:
        self.routing_table.add_contact(sender)
        return self.routing_table.find_closest(target_id)

    def rpc_find_value(self, sender: Contact, key: int) -> Tuple[Optional[str], List[Contact]]:
        self.routing_table.add_contact(sender)
        if key in self.storage:
            return (self.storage[key], [])
        return (None, self.routing_table.find_closest(key))

    # High-level operations
    def iterative_find_node(self, target_id: int, alpha: int = 3) -> List[Contact]:
        """Kademlia iterative node lookup algorithm."""
        if not self.network:
            return self.routing_table.find_closest(target_id)

        closest = self.routing_table.find_closest(target_id)
        visited: Set[int] = {self.node_id}

        while True:
            # Pick alpha unqueried nodes closest to target
            candidates = [c for c in closest if c.node_id not in visited][:alpha]
            if not candidates:
                break

            found_closer = False
            for c in candidates:
                visited.add(c.node_id)
                peer = self.network.get(c.node_id)
                if not peer:
                    continue
                # Query peer for closest contacts
                neighbors = peer.rpc_find_node(self.contact, target_id)
                for n in neighbors:
                    if n.node_id not in [x.node_id for x in closest]:
                        closest.append(n)
                        found_closer = True

            closest.sort(key=lambda x: xor_distance(x.node_id, target_id))
            closest = closest[:self.routing_table.k_size]

            if not found_closer:
                break

        return closest

    def put(self, key_str: str, value: str) -> int:
        """Hash key string and store on k closest nodes."""
        key_id = int(hashlib.sha256(key_str.encode()).hexdigest(), 16) % (1 << self.routing_table.num_bits)
        closest_nodes = self.iterative_find_node(key_id)

        # Store locally if we are closest or have space
        self.storage[key_id] = value

        for c in closest_nodes:
            if self.network and c.node_id in self.network:
                self.network[c.node_id].rpc_store(self.contact, key_id, value)

        return key_id

    def get(self, key_str: str) -> Optional[str]:
        """Locate and retrieve value across DHT peers."""
        key_id = int(hashlib.sha256(key_str.encode()).hexdigest(), 16) % (1 << self.routing_table.num_bits)
        if key_id in self.storage:
            return self.storage[key_id]

        closest_nodes = self.iterative_find_node(key_id)
        for c in closest_nodes:
            if self.network and c.node_id in self.network:
                val, _ = self.network[c.node_id].rpc_find_value(self.contact, key_id)
                if val is not None:
                    return val
        return None
