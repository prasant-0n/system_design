import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from crush_algorithm import CRUSHCluster


class TestCRUSHAlgorithm(unittest.TestCase):

    def setUp(self):
        self.cluster = CRUSHCluster()
        # Build a cluster with 4 racks, each having 3 OSDs (12 OSDs total)
        for r in range(4):
            rack_name = f"rack_{r}"
            for h in range(3):
                osd_name = f"osd_r{r}_h{h}"
                host_name = f"host_r{r}_h{h}"
                self.cluster.add_osd(osd_name, host_name, rack_name)

    def test_deterministic_placement(self):
        # Invariant 1: Same object ID must always map to identical OSDs
        obj_id = "user_photo_99214.jpg"
        replicas_1 = self.cluster.select_replicas(obj_id, num_replicas=3)
        replicas_2 = self.cluster.select_replicas(obj_id, num_replicas=3)

        self.assertEqual(len(replicas_1), 3)
        self.assertEqual(replicas_1, replicas_2)

    def test_failure_domain_isolation(self):
        # Invariant 2: No two replicas may reside in the same rack
        obj_id = "database_backup_wal_100.bin"
        replicas = self.cluster.select_replicas(obj_id, num_replicas=3)

        racks_used = set()
        for osd_id in replicas:
            osd = self.cluster.osds[osd_id]
            self.assertNotIn(osd.rack_id, racks_used)
            racks_used.add(osd.rack_id)

        self.assertEqual(len(racks_used), 3)

    def test_different_objects_distribute(self):
        # Different objects should hash to different OSDs
        reps_a = self.cluster.select_replicas("obj_A", num_replicas=3)
        reps_b = self.cluster.select_replicas("obj_B", num_replicas=3)

        # It is highly improbable for two different hashes to choose identical sets of 3 OSDs
        self.assertNotEqual(reps_a, reps_b)


if __name__ == "__main__":
    unittest.main()
