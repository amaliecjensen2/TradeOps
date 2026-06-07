"""Prometheus metrics for risk monitor."""

from prometheus_client import Counter, Gauge, start_http_server

IS_LEADER = Gauge(
    "risk_monitor_is_leader",
    "1 if this pod is the current leader, 0 otherwise",
)

EVALUATIONS_TOTAL = Counter(
    "risk_monitor_evaluations_total",
    "Number of risk evaluation cycles completed",
)

BREACHES_TOTAL = Counter(
    "risk_monitor_breaches_total",
    "Number of circuit breaker trips",
    ["reason_type"],
)

ALERTS_SENT_TOTAL = Counter(
    "risk_monitor_alerts_sent_total",
    "Telegram alerts sent",
    ["alert_type"],
)

DAILY_PNL = Gauge(
    "risk_monitor_daily_pnl",
    "Current daily P&L as tracked by risk monitor",
    ["account"],
)

DRAWDOWN_PCT = Gauge(
    "risk_monitor_drawdown_pct",
    "Current intra-day drawdown fraction (0.05 = 5%)",
    ["account"],
)

GROSS_EXPOSURE = Gauge(
    "risk_monitor_gross_exposure",
    "Current gross exposure in account currency",
    ["account"],
)

ADAPTER_CONNECTED = Gauge(
    "risk_monitor_adapter_connected",
    "1 if the ibkr-adapter is heartbeating normally",
)

HALTED = Gauge(
    "risk_monitor_halted",
    "1 if the circuit breaker has been tripped",
)


def start_metrics_server(port: int) -> None:
    start_http_server(port)
