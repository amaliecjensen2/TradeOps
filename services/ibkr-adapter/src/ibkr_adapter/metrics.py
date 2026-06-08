"""Prometheus metrics udstillet på :9090/metrics.

Alle countere / gauges for adapteren ligger her, så der præcis er en
import af prometheus_client på tværs af servicen.
"""

from prometheus_client import Counter, Gauge, Histogram, start_http_server

# Forbindelsesstatus
CONNECTED = Gauge(
    "ibkr_adapter_connected",
    "1 when the adapter has an active TWS connection, 0 otherwise",
)

# Ordrebehandling
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
NET_LIQUIDATION = Gauge(
    "ibkr_adapter_net_liquidation",
    "Latest NetLiquidation value reported by TWS account updates",
    ["account"],
)

# Latens: NATS ordrebesked til TWS placeOrder() kald
ORDER_LATENCY = Histogram(
    "ibkr_adapter_order_latency_seconds",
    "Time from receiving NATS order to calling TWS placeOrder",
    buckets=[0.001, 0.005, 0.010, 0.025, 0.050, 0.100, 0.250, 0.500, 1.0],
)


def start_metrics_server(port: int) -> None:
    start_http_server(port)
