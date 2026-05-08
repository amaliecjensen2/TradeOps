"""Kubernetes Lease-based leader election.

Two replicas of risk-monitor run simultaneously for high availability,
but only the *leader* trips the circuit breaker and sends alerts.
The follower keeps its state up to date and takes over instantly if the
leader pod restarts.

Implementation: standard Kubernetes Lease (coordination.k8s.io/v1).
The leader continuously renews the Lease; if it fails to renew within
lease_duration_s, another pod may acquire it.

Usage:
    elector = LeaderElector(settings)
    async with elector:
        while True:
            if elector.is_leader:
                # do leader work
            await asyncio.sleep(1)
"""

from __future__ import annotations

import asyncio
import datetime

from kubernetes import client as k8s_client
from kubernetes import config as k8s_config
from kubernetes.client.rest import ApiException

from risk_monitor.config import Settings
from risk_monitor.logging_setup import get_logger

log = get_logger(__name__)


class LeaderElector:
    def __init__(self, settings: Settings) -> None:
        self._lease_name = settings.lease_name
        self._namespace = settings.k8s_namespace
        self._pod_name = settings.pod_name
        self._duration = settings.lease_duration_s
        self._renew_deadline = settings.lease_renew_deadline_s
        self._retry_period = settings.lease_retry_period_s

        self._is_leader = False
        self._coord_v1: k8s_client.CoordinationV1Api | None = None
        self._task: asyncio.Task | None = None

    @property
    def is_leader(self) -> bool:
        return self._is_leader

    async def __aenter__(self):
        self._load_k8s()
        self._task = asyncio.create_task(self._election_loop())
        return self

    async def __aexit__(self, *_):
        if self._task:
            self._task.cancel()

    def _load_k8s(self) -> None:
        if self._coord_v1 is not None:
            return
        try:
            k8s_config.load_incluster_config()
        except k8s_config.ConfigException:
            k8s_config.load_kube_config()
        self._coord_v1 = k8s_client.CoordinationV1Api()

    async def _election_loop(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            try:
                acquired = await loop.run_in_executor(None, self._try_acquire_or_renew)
                if acquired and not self._is_leader:
                    self._is_leader = True
                    log.info("leader_election.became_leader",
                             pod=self._pod_name)
                elif not acquired and self._is_leader:
                    self._is_leader = False
                    log.info("leader_election.lost_leadership",
                             pod=self._pod_name)
            except Exception as exc:
                log.warning("leader_election.error", error=str(exc))
                self._is_leader = False

            await asyncio.sleep(self._retry_period)

    def _try_acquire_or_renew(self) -> bool:
        assert self._coord_v1 is not None
        now = datetime.datetime.now(datetime.timezone.utc)
        expiry = now + datetime.timedelta(seconds=self._duration)
        expiry_str = expiry.strftime("%Y-%m-%dT%H:%M:%SZ")

        try:
            lease = self._coord_v1.read_namespaced_lease(
                name=self._lease_name, namespace=self._namespace
            )
            spec = lease.spec
            holder = spec.holder_identity or ""
            renew_time = spec.renew_time
            acquire_time = spec.acquire_time

            # Check if existing lease is expired
            if holder != self._pod_name:
                if renew_time is None:
                    pass  # no renew time — treat as expired
                else:
                    elapsed = (
                        now - renew_time.replace(tzinfo=datetime.timezone.utc)).total_seconds()
                    if elapsed < self._duration:
                        # Another pod holds a valid lease
                        return False

            # Try to take / renew the lease
            lease.spec.holder_identity = self._pod_name
            lease.spec.renew_time = now
            lease.spec.lease_duration_seconds = self._duration
            if holder != self._pod_name:
                lease.spec.acquire_time = now
                lease.spec.lease_transitions = (
                    spec.lease_transitions or 0) + 1

            self._coord_v1.replace_namespaced_lease(
                name=self._lease_name,
                namespace=self._namespace,
                body=lease,
            )
            return True

        except ApiException as exc:
            if exc.status == 404:
                return self._create_lease()
            raise

    def _create_lease(self) -> bool:
        assert self._coord_v1 is not None
        now = datetime.datetime.now(datetime.timezone.utc)
        lease = k8s_client.V1Lease(
            metadata=k8s_client.V1ObjectMeta(
                name=self._lease_name,
                namespace=self._namespace,
            ),
            spec=k8s_client.V1LeaseSpec(
                holder_identity=self._pod_name,
                acquire_time=now,
                renew_time=now,
                lease_duration_seconds=self._duration,
                lease_transitions=0,
            ),
        )
        try:
            self._coord_v1.create_namespaced_lease(
                namespace=self._namespace, body=lease
            )
            log.info("leader_election.lease_created", pod=self._pod_name)
            return True
        except ApiException as exc:
            if exc.status == 409:
                # Another pod created it first
                return False
            raise
