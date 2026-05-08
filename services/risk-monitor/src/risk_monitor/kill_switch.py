"""Kubernetes kill switch.

When the circuit breaker trips, KillSwitch.trip() scales every strategy
Deployment to 0 replicas. It uses the in-cluster service account that
Helm already provisions with the correct RBAC (patch Deployments in the
release namespace).

The kill switch is idempotent — calling it twice is safe.

If kill_switch_enabled=False (paper / dev), the action is logged but
no Deployments are modified.
"""

from __future__ import annotations

import asyncio

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config

from risk_monitor.config import Settings
from risk_monitor.logging_setup import get_logger

log = get_logger(__name__)


class KillSwitch:
    def __init__(self, settings: Settings) -> None:
        self._enabled = settings.kill_switch_enabled
        self._namespace = settings.k8s_namespace
        self._release = settings.release_name
        self._apps_v1: k8s_client.AppsV1Api | None = None

    def _load_k8s(self) -> None:
        """Load the in-cluster config (or local kubeconfig for dev)."""
        if self._apps_v1 is not None:
            return
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()
        self._apps_v1 = k8s_client.AppsV1Api()

    async def trip(self, reason: str, nats_bridge=None) -> list[str]:
        """Scale all strategy Deployments to 0. Returns list of affected names."""
        self._load_k8s()

        if not self._enabled:
            log.warning(
                "kill_switch.disabled_skipping",
                reason=reason,
            )
            return []

        # Run the blocking kubernetes SDK call in a thread pool
        loop = asyncio.get_running_loop()
        affected = await loop.run_in_executor(None, self._scale_strategies_to_zero)

        log.critical(
            "kill_switch.tripped",
            reason=reason,
            deployments_scaled=affected,
        )

        # Publish HALT event on NATS so all components know
        if nats_bridge is not None:
            import json
            import datetime
            payload = json.dumps({
                "reason": reason,
                "deployments": affected,
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }).encode()
            await nats_bridge.publish("risk.halt", payload)

        return affected

    def _scale_strategies_to_zero(self) -> list[str]:
        """Synchronous — runs in thread pool via run_in_executor."""
        assert self._apps_v1 is not None

        # Find all Deployments belonging to this release that are strategies
        label_selector = (
            f"app.kubernetes.io/instance={self._release},"
            f"app.kubernetes.io/component=strategy"
        )
        deployments = self._apps_v1.list_namespaced_deployment(
            namespace=self._namespace,
            label_selector=label_selector,
        )

        affected = []
        for dep in deployments.items:
            name = dep.metadata.name
            if dep.spec.replicas == 0:
                log.info("kill_switch.already_zero", deployment=name)
                continue

            self._apps_v1.patch_namespaced_deployment_scale(
                name=name,
                namespace=self._namespace,
                body={"spec": {"replicas": 0}},
            )
            log.warning("kill_switch.scaled_to_zero", deployment=name)
            affected.append(name)

        return affected
