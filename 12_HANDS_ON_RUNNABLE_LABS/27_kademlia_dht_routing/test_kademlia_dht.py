"""Tests for Kademlia DHT Routing Engine."""

import unittest
from .kademlia_dht import xor_distance, Contact, KBucket, RoutingTable, KademliaNode


class TestKademliaDHT(unittest.TestCase):

    def test_xor_distance_properties(self):
        # Identity: d(x, x) == 0
        self.assertEqual(xor_distance(0x1234, 0x1234), 0)
        # Symmetry: d(x, y) == d(y, x)
        self.assertEqual(xor_distance(0x1234, 0x5678), xor_distance(0x5678, 0x1234))
        # Triangle inequality: d(x, z) <= d(x, y) ^ d(y, z)
        x, y, z = 10, 25, 42
        self.assertEqual(xor_distance(x, z), xor_distance(x, y) ^ xor_distance(y, z))

    def test_kbucket_lru_and_capacity(self):
        bucket = KBucket(k_size=3)
        c1 = Contact(1)
        c2 = Contact(2)
        c3 = Contact(3)
        c4 = Contact(4)

        self.assertTrue(bucket.update(c1))
        self.assertTrue(bucket.update(c2))
        self.assertTrue(bucket.update(c3))
        self.assertEqual(len(bucket), 3)

        # 4th contact rejected because bucket is full
        self.assertFalse(bucket.update(c4))

        # Re-adding c1 moves it to tail (most recently used)
        self.assertTrue(bucket.update(c1))
        self.assertEqual(bucket.contacts[-1], c1)

    def test_routing_table_closest(self):
        table = RoutingTable(local_node_id=0x0000, num_bits=16, k_size=4)
        c1 = Contact(0x0002)
        c2 = Contact(0x0008)
        c3 = Contact(0x00F0)
        c4 = Contact(0x0F00)

        table.add_contact(c1)
        table.add_contact(c2)
        table.add_contact(c3)
        table.add_contact(c4)

        closest = table.find_closest(0x0001, count=2)
        self.assertEqual(len(closest), 2)
        # 0x0002 is closest to 0x0001 (distance = 3)
        self.assertEqual(closest[0].node_id, 0x0002)

    def test_kademlia_network_put_get(self):
        network = {}
        nodes = []
        # Create 8 nodes with 16-bit keyspace
        for node_id in [0x0010, 0x0020, 0x0040, 0x0080, 0x0100, 0x0200, 0x0400, 0x0800]:
            n = KademliaNode(node_id, num_bits=16, k_size=4)
            n.attach_network(network)
            nodes.append(n)

        # Populate routing tables by cross-pinging
        for n1 in nodes:
            for n2 in nodes:
                if n1 != n2:
                    n1.routing_table.add_contact(n2.contact)

        # Node 0 puts a key-value pair
        key = "distributed_systems_bible"
        val = "Lamport_Chandy_1985"
        nodes[0].put(key, val)

        # Node 7 retrieves it through the DHT
        retrieved = nodes[7].get(key)
        self.assertEqual(retrieved, val)


if __name__ == "__main__":
    unittest.main()
