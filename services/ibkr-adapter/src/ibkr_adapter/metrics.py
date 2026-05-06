"""Prometheus metrics exposed on :9090/metrics.

All counters / gauges for the adapter live here so there is exactly one
import of prometheus_client across the service.
"""

from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Connection state
CONNECTED = Gauge(
    "ibkr_adapter_connected",
    "1 when the adapter has an active TWS connection, 0 otherwise",
)

# Order processing
ORDERS_RECEIVED = Counter(
    "ibkr_adapter_orders_received_total",
    "NATS order commands received",
    ["strategy"],
)
ORDERS_PLACED = Counter(
    "ibkr_adapter_orders_placed_total",
    "Orders successfully placed with TWS",
    ["strategy"],
)
ORDERS_REJECTED = Counter(
    "ibkr_adapter_orders_rejected_total",
    "Orders rejected before reaching TWS",
    ["strategy", "reason"],
)

# Fill throughput
FILLS_PUBLISHED = Counter(
    "ibkr_adapter_fills_published_total",
    "Fill events published to NATS",
    ["account"],
)

# PnL
PNL_DAILY = Gauge(
    "ibkr_adapter_daily_pnl",
    "Current daily PnL as reported by TWS",
    ["account"],
)

# Latency: NATS order message → TWS placeOrder() call
ORDER_LATENCY = Histogram(
    "ibkr_adapter_order_latency_seconds",
    "Time from receiving NATS order to calling TWS placeOrder",
    buckets=[0.001, 0.005, 0.010, 0.025, 0.050, 0.100, 0.250, 0.500, 1.0],
)


def start_metrics_server(port: int) -> None:
    start_http_server(port)
