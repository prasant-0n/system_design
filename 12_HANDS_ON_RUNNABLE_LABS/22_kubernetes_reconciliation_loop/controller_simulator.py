"""
Kubernetes Declarative Controller & Level-Triggered Reconciliation Loop.

Features:
1. Declarative Desired State (Spec) vs Observed Actual State (Status).
2. Level-triggered idempotent reconciliation loop.
3. Self-healing state convergence (re-spawns killed pods, scales down excess pods).
"""

from typing import Dict, List, Optional
from collections import deque
import uuid


class Pod:
    def __init__(self, name: str, app_label: str):
        self.name = name
        self.app_label = app_label
        self.is_running = True


class DeploymentSpec:
    def __init__(self, replicas: int, app_label: str):
        self.replicas = replicas
        self.app_label = app_label


class DeploymentStatus:
    def __init__(self):
        self.replicas = 0
        self.ready_replicas = 0


class Deployment:
    def __init__(self, name: str, spec: DeploymentSpec):
        self.name = name
        self.spec = spec
        self.status = DeploymentStatus()


class KubernetesClusterSimulator:
    """
    Simulates Kubernetes API Server, etcd, and the DeploymentController.
    """

    def __init__(self):
        self.deployments: Dict[str, Deployment] = {}
        self.pods: Dict[str, Pod] = {}
        self.work_queue: deque = deque()

    def apply_deployment(self, name: str, replicas: int, app_label: str) -> None:
        if name in self.deployments:
            self.deployments[name].spec.replicas = replicas
        else:
            self.deployments[name] = Deployment(name, DeploymentSpec(replicas, app_label))

        # Enqueue key for reconciliation
        self.work_queue.append(name)

    def kill_pod(self, pod_name: str) -> None:
        """Simulates external out-of-band crash of a pod."""
        if pod_name in self.pods:
            self.pods[pod_name].is_running = False
            # In level-triggered K8s, an Informer watches pod deletions and enqueues deployment
            app = self.pods[pod_name].app_label
            for dep_name, dep in self.deployments.items():
                if dep.spec.app_label == app:
                    self.work_queue.append(dep_name)

    def reconcile_one(self) -> Optional[str]:
        """
        Executes one iteration of the level-triggered reconciliation loop.
        Delta = DesiredState - ActualState -> Apply correction.
        """
        if not self.work_queue:
            return None

        dep_name = self.work_queue.popleft()
        if dep_name not in self.deployments:
            return None

        dep = self.deployments[dep_name]
        desired_replicas = dep.spec.replicas
        label = dep.spec.app_label

        # 1. Observe Actual State: Query active running pods with matching label
        active_pods = [p for p in self.pods.values() if p.app_label == label and p.is_running]
        actual_count = len(active_pods)

        # 2. Compute Difference & Actuate
        if actual_count < desired_replicas:
            # Scale UP: spawn missing pods
            to_create = desired_replicas - actual_count
            for _ in range(to_create):
                p_id = f"{dep_name}-{str(uuid.uuid4())[:6]}"
                self.pods[p_id] = Pod(p_id, label)
        elif actual_count > desired_replicas:
            # Scale DOWN: terminate excess pods
            to_delete = actual_count - desired_replicas
            for i in range(to_delete):
                pod_to_remove = active_pods[i]
                pod_to_remove.is_running = False

        # 3. Update Status
        current_active = [p for p in self.pods.values() if p.app_label == label and p.is_running]
        dep.status.replicas = len(current_active)
        dep.status.ready_replicas = len(current_active)

        return dep_name
