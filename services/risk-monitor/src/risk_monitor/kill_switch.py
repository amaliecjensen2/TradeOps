"""Kubernetes kill switch.

Når circuit breakeren trippes scalere KillSwitch.trip() hver strategi
Deployment til 0 replicas. Den bruger den in cluster service account som
Helm allerede provisionerer med korrekt RBAC (patch Deployments i
release namespace).

Kill switchen er idempotent, det er sikkert at kalde den to gange.

Hvis kill_switch_enabled=False (paper / dev) springes Deployment scaling
over, men risk.halt NATS beskeden publiceres stadig så risk-gateway
afviser nye ordrer. Det giver et soft halt uden at dræbe pods.
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
        """Indlæs in cluster config (eller lokal kubeconfig til dev)."""
        if self._apps_v1 is not None:
            return
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()
        self._apps_v1 = k8s_client.AppsV1Api()

    async def trip(self, reason: str, nats_bridge=None) -> list[str]:
        """Scalere alle strategi Deployments til 0. Returnerer liste af berørte navne.

        risk.halt publiceres altid på NATS uanset kill_switch_enabled, så
        risk-gateway kan afvise nye ordrer. Kun pod scaling springes over
        når flaget er false.
        """
        affected: list[str] = []

        if self._enabled:
            self._load_k8s()
            # Kør det blokkerende kubernetes SDK kald i en thread pool
            loop = asyncio.get_running_loop()
            affected = await loop.run_in_executor(None, self._scale_strategies_to_zero)
            log.critical(
                "kill_switch.tripped",
                reason=reason,
                deployments_scaled=affected,
            )
        else:
            log.warning(
                "kill_switch.scaling_disabled",
                reason=reason,
            )

        # Publicér HALT event på NATS så risk-gateway og api ved det
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
        """Synkron, kører i thread pool via run_in_executor."""
        assert self._apps_v1 is not None

        # Find alle Deployments der hører til dette release og er strategier
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
