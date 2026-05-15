# AmalieTrader Codebase Overview

AmalieTrader is a multi-service trading platform designed around one Interactive Brokers account and one IBKR Gateway session. The repository contains Python backend services, a Next.js dashboard, Docker packaging for each service, and a Helm chart that deploys the full topology to Kubernetes.

The core runtime path is:

```text
strategy pod -> risk-gateway -> NATS orders.* -> ibkr-adapter -> IBKR Gateway
IBKR callbacks -> ibkr-adapter -> NATS fills/positions/pnl/risk -> API, risk-monitor, storage/dashboard consumers
```

## Repository Layout

```text
.
|-- build-and-push.ps1
|-- helm/
|   `-- ibkrtrader/
|       |-- Chart.yaml
|       |-- values.yaml
|       |-- values.paper.yaml
|       |-- values.live.yaml
|       |-- values.schema.json
|       |-- ARCHITECTURE.md
|       |-- templates/
|       `-- charts/
`-- services/
    |-- api/
    |-- dashboard/
    |-- ibkr-adapter/
    |-- risk-gateway/
    |-- risk-monitor/
    `-- strategy-hello/
```

## Main Components

### `services/strategy-hello`

Example strategy service written in Python 3.12. It implements a simple moving-average crossover strategy:

- Subscribes to `marketdata.realtime.<symbol>` on NATS.
- Maintains rolling close-price buffers per symbol.
- Sends BUY/SELL orders to the risk gateway over HTTP.
- Exposes `/healthz`, `/readyz`, and Prometheus metrics.

The reusable strategy foundation lives in `strategy_hello/base.py`. New strategies can follow the same shape by subclassing `BaseStrategy` and implementing `on_bar()`.

### `services/risk-gateway`

FastAPI service that acts as the synchronous pre-trade gate for all strategy orders.

Primary route:

- `POST /orders`: validate an order, reject it with a structured reason, or publish it to NATS as `orders.<strategy>.<symbol>`.

Implemented checks include:

- Global halt flag.
- Restricted symbols.
- Fat-finger limit-price band.
- Per-strategy max order notional.
- Per-strategy daily loss.
- Per-strategy position limit.
- Per-strategy and global order-rate limits.
- Idempotency key duplicate detection.

Important implementation detail: the check engine currently keeps state in memory. That is simple and fast, but multiple replicas will not share idempotency, rate-limit, position, or halt state unless externalized.

### `services/ibkr-adapter`

Python service that owns the broker connection. It bridges NATS order messages to the IBKR Gateway and publishes broker callbacks back onto NATS.

Responsibilities:

- Connect to NATS.
- Subscribe to `orders.>`.
- Connect to IBKR Gateway with reserved client ID `1`.
- Place orders through `ib_insync`.
- Publish fills, positions, PnL, heartbeat, disconnect, and risk events.
- Expose health and Prometheus metrics.

The adapter is the only service that should talk directly to IBKR Gateway in the current implementation.

### `services/risk-monitor`

Out-of-band portfolio risk monitor. It listens to NATS state updates, evaluates account-level risk, sends alerts, and can trip a kill switch.

Key responsibilities:

- Track account state from fills, PnL, positions, heartbeat, and risk events.
- Run a reconciliation/evaluation loop on a configurable interval.
- Use Kubernetes Lease-based leader election so only one replica performs actions.
- Trigger circuit-breaker behavior on threshold breaches.
- Optionally scale strategy Deployments to zero through Kubernetes APIs.
- Optionally send Telegram alerts.

Configured thresholds include max daily loss, max drawdown percent, max gross exposure, and adapter heartbeat timeout.

### `services/api`

Read-only FastAPI service for the dashboard.

Routes:

- `GET /healthz`
- `GET /readyz`
- `GET /status`
- `GET /positions`
- `GET /pnl`
- `GET /pnl/history`
- `GET /fills`
- `GET /orders`

The API keeps a low-latency in-memory cache from NATS for current status, positions, and PnL, and falls back to Timescale/Postgres for historical reads.

### `services/dashboard`

Next.js 14 dashboard with React, SWR, Tailwind, and Recharts.

It displays:

- System/account status.
- Daily, realized, unrealized, and net-liquidation PnL.
- PnL history chart.
- Open positions.
- Recent fills.

The dashboard calls the API through `src/lib/api.ts`, with `NEXT_PUBLIC_API_URL` controlling the backend URL.

## Data Plane

### NATS JetStream

NATS is the event bus between services. The chart enables JetStream by default.

Common subjects:

- `orders.<strategy>.<symbol>`: accepted order commands.
- `fills.<account>.<symbol>`: broker execution reports.
- `positions.>`: position snapshots.
- `pnl.>`: PnL snapshots.
- `risk.adapter.heartbeat`: adapter liveness.
- `risk.adapter.disconnected`: adapter disconnect event.
- `risk.halt`: circuit-breaker halt state.
- `marketdata.realtime.<symbol>`: market data consumed by strategies.

The Helm chart includes optional JetStream stream templates, disabled by default through `jetstreamStreams.enabled`.

### TimescaleDB / Postgres

The schema is in `services/api/db/migrations/001_initial_schema.sql`.

Tables and hypertables:

- `fills`
- `pnl_ticks`
- `positions_snapshot`
- `order_events`
- `marketdata_bars`

There is also a continuous aggregate `pnl_1min` for chart-friendly one-minute PnL data.

## Kubernetes and Helm

The Helm chart under `helm/ibkrtrader` deploys:

- IBKR Gateway StatefulSet and Service.
- IBKR adapter Deployment.
- One strategy Deployment per item in `values.yaml` under `strategies`.
- Risk gateway Deployment.
- Risk monitor Deployment and RBAC.
- API Deployment.
- Dashboard Deployment.
- CloudNativePG/Timescale cluster resources.
- NATS dependency chart.
- Optional ServiceMonitor resources.

Default values target paper trading. `values.paper.yaml` and `values.live.yaml` provide environment-specific overrides.

Important chart conventions:

- `ibkr.mode` selects paper or live gateway routing.
- `ibkrAdapter.clientId` reserves client ID `1`.
- Each strategy must have a unique `clientId`.
- Images default to `ghcr.io/amaliecjensen/ibkrtrader/<service>:v0`.
- IBKR credentials are expected through an existing Kubernetes Secret by default.

## Build and Deployment

`build-and-push.ps1` builds and pushes all service images:

```powershell
.\build-and-push.ps1 -GithubUser <github-user> -Tag v0
```

Services built by the script:

- `ibkr-adapter`
- `risk-monitor`
- `risk-gateway`
- `api`
- `strategy-hello`
- `dashboard`

The script pushes images to:

```text
ghcr.io/<github-user>/ibkrtrader/<service>:<tag>
```

The intended install path is Helm, for example:

```powershell
helm install trader ./helm/ibkrtrader -f helm/ibkrtrader/values.paper.yaml -n trading --set global.imageRegistry=ghcr.io/<github-user>
```

## Configuration Model

The Python services use `pydantic-settings` and are configured primarily through environment variables injected by Helm.

Common settings:

- `NATS_URL`
- `IBKR_ACCOUNT`
- `IBKR_MODE`
- `LOG_LEVEL`
- `LOG_FORMAT`
- `HEALTH_PORT`
- `METRICS_PORT`

Service-specific settings include:

- IBKR adapter: `IBGW_HOST`, `IBGW_PORT`, `IBKR_CLIENT_ID`, reconnect settings.
- Risk gateway: global risk limits, restricted symbols, `STRATEGY_LIMITS_JSON`.
- Risk monitor: drawdown/loss/exposure thresholds, Telegram settings, Kubernetes namespace/release, leader election timings.
- Strategy: strategy name, universe, MA periods, trade quantity, risk gateway URL.
- API: Postgres host/port/database/user/password.
- Dashboard: `NEXT_PUBLIC_API_URL`.

## Testing

Python services use pytest through Hatch environments. Test coverage currently exists for:

- `ibkr-adapter`: models and NATS bridge behavior.
- `risk-gateway`: risk checks.
- `risk-monitor`: account state and circuit breaker behavior.
- `strategy-hello`: strategy behavior.

The dashboard has npm scripts for development, build, start, and lint.

Typical local commands by service:

```powershell
cd services\risk-gateway
hatch run pytest
```

```powershell
cd services\dashboard
npm run build
```

## Current Implementation Notes

- The architecture document in `helm/ibkrtrader/ARCHITECTURE.md` is more aspirational and detailed than some current service implementations.
- The codebase is in a v0-style state: the topology is present, but some production-hardening pieces still need externalized state, stricter network policy, complete reconciliation, persistent audit writes from all event paths, and operational secrets management.
- Risk gateway state is currently in-memory, which matters if running the configured two replicas.
- The dashboard polls the API with SWR every 10 seconds rather than using server-sent events.
- The strategy example is intentionally simple and intended as a template for new strategy services.
- The repo includes vendored Helm chart dependencies under `helm/ibkrtrader/charts`.

## High-Level Mental Model

Strategies generate intent, the risk gateway decides whether that intent may enter the system, NATS carries accepted commands and broker events, the IBKR adapter owns broker I/O, the risk monitor watches the whole account for emergent breaches, TimescaleDB stores history, and the API/dashboard expose read-only operational visibility.
