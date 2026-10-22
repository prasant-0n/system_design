import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from controller_simulator import KubernetesClusterSimulator


class TestKubernetesReconciliationLoop(unittest.TestCase):

    def setUp(self):
        self.k8s = KubernetesClusterSimulator()

    def test_initial_deployment_scaling(self):
        # Apply deployment wanting 3 replicas
        self.k8s.apply_deployment("frontend-app", replicas=3, app_label="frontend")
        self.assertEqual(len(self.k8s.work_queue), 1)

        # Execute reconciliation loop
        reconciled = self.k8s.reconcile_one()
        self.assertEqual(reconciled, "frontend-app")

        # Invariant: 3 pods must be running
        active_pods = [p for p in self.k8s.pods.values() if p.app_label == "frontend" and p.is_running]
        self.assertEqual(len(active_pods), 3)

        dep = self.k8s.deployments["frontend-app"]
        self.assertEqual(dep.status.replicas, 3)

    def test_self_healing_after_pod_crash(self):
        # Initial 3 pods
        self.k8s.apply_deployment("auth-svc", replicas=3, app_label="auth")
        self.k8s.reconcile_one()

        active_pods = [p for p in self.k8s.pods.values() if p.app_label == "auth" and p.is_running]
        self.assertEqual(len(active_pods), 3)
        victim_pod_name = active_pods[0].name

        # Simulate out-of-band node crash / OOM kill
        self.k8s.kill_pod(victim_pod_name)
        active_after_kill = [p for p in self.k8s.pods.values() if p.app_label == "auth" and p.is_running]
        self.assertEqual(len(active_after_kill), 2)

        # Reconciliation loop observes actual=2 < desired=3 and self-heals!
        self.k8s.reconcile_one()

        healed_pods = [p for p in self.k8s.pods.values() if p.app_label == "auth" and p.is_running]
        self.assertEqual(len(healed_pods), 3)

    def test_scale_down(self):
        # Scale down from 3 to 1
        self.k8s.apply_deployment("batch-job", replicas=3, app_label="batch")
        self.k8s.reconcile_one()

        # Update spec to 1 replica
        self.k8s.apply_deployment("batch-job", replicas=1, app_label="batch")
        self.k8s.reconcile_one()

        active_pods = [p for p in self.k8s.pods.values() if p.app_label == "batch" and p.is_running]
        self.assertEqual(len(active_pods), 1)


if __name__ == "__main__":
    unittest.main()
