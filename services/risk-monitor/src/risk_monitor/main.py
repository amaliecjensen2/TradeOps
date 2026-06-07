"""Indgangspunkt for risk monitor.

Startrækkefølge:
  1. Konfigurer logging + metrics
  2. Forbind til NATS
  3. Start health server
  4. Start leader election
  5. Kør reconcile loopet (kun lederen agerer på overtrædelser)

Reconcile loopet kører for evigt. Ved SIGTERM drainer den NATS og afslutter.
"""

from __future__ import annotations

import asyncio
import signal

from risk_monitor import metrics as m
from risk_monitor.alerts import AlertSender
from risk_monitor.circuit_breaker import CircuitBreaker
from risk_monitor.config import get_settings
from risk_monitor.health import HealthServer
from risk_monitor.kill_switch import KillSwitch
from risk_monitor.leader import LeaderElector
from risk_monitor.logging_setup import configure_logging, get_logger
from risk_monitor.metrics import start_metrics_server
from risk_monitor.nats_listener import NATSListener
from risk_monitor.state import AccountState

log = get_logger(__name__)


async def _main() -> None:
    settings = get_settings()
    configure_logging()

    log.info(
        "risk_monitor.starting",
        mode=settings.ibkr_mode,
        pod=settings.pod_name,
        kill_switch=settings.kill_switch_enabled,
    )

    # Metrics
    start_metrics_server(settings.metrics_port)

    # Delt state
    state = AccountState(account=settings.ibkr_account)

    # Komponenter
    nats_listener = NATSListener(settings, state)
    alerts = AlertSender(settings)
    circuit_breaker = CircuitBreaker(settings)
    kill_switch = KillSwitch(settings)
    health = HealthServer(settings.health_port)

    # Forbind til NATS
    await nats_listener.connect()
    await nats_listener.subscribe_all()

    # Health server
    health.set_dependencies(
        state, lambda: elector.is_leader if 'elector' in dir() else False)
    await health.start()

    # Graceful nedlukningsflag
    _shutdown = asyncio.Event()

    def _handle_signal():
        log.info("risk_monitor.shutdown_requested")
        _shutdown.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _handle_signal)

    # Leader election
    async with LeaderElector(settings) as elector:
        health.set_dependencies(state, lambda: elector.is_leader)

        log.info("risk_monitor.reconcile_loop_started",
                 interval_s=settings.reconcile_interval_s)

        while not _shutdown.is_set():
            await asyncio.sleep(settings.reconcile_interval_s)

            # Opdater Prometheus gauges hver cyklus (både leader og follower)
            m.IS_LEADER.set(1 if elector.is_leader else 0)
            if state.account:
                m.DAILY_PNL.labels(account=state.account).set(state.daily_pnl)
                m.DRAWDOWN_PCT.labels(account=state.account).set(
                    state.drawdown_pct)
                m.GROSS_EXPOSURE.labels(account=state.account).set(
                    state.gross_exposure)
            m.ADAPTER_CONNECTED.set(1 if state.adapter_connected else 0)
            m.HALTED.set(1 if state.halted else 0)

            # Kun lederen agerer
            if not elector.is_leader:
                continue

            m.EVALUATIONS_TOTAL.inc()

            result = circuit_breaker.evaluate(state)

            if result.alert_only:
                # Heartbeat timeout, alarm men halt ikke
                log.warning("risk_monitor.alert_only", reason=result.reason)
                secs = state.seconds_since_heartbeat or 0
                await alerts.heartbeat_timeout(secs)
                m.ALERTS_SENT_TOTAL.labels(
                    alert_type="heartbeat_timeout").inc()

            elif result.should_halt:
                # Circuit breaker udløst
                log.critical("risk_monitor.halting", reason=result.reason)
                state.halted = True
                state.halt_reason = result.reason

                # 1. Send Telegram alarm
                await alerts.halt(result.reason)
                m.ALERTS_SENT_TOTAL.labels(alert_type="halt").inc()
                m.BREACHES_TOTAL.labels(reason_type="halt").inc()

                # 2. Scaler alle strategi pods til 0
                affected = await kill_switch.trip(result.reason, nats_bridge=nats_listener)
                log.critical(
                    "risk_monitor.kill_switch_executed",
                    deployments=affected,
                )

        log.info("risk_monitor.stopped")
        await nats_listener.close()


def run() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    run()
