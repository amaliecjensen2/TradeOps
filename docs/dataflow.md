# TradeOps — Dataflow Diagram

Detaljeret diagram over NATS topics og dataflows mellem de forskellige services i TradeOps.

## Services

- `ibkr-adapter` — eneste service der taler med IB Gateway/TWS. Oversætter mellem `ib_insync`-events og NATS-meddelelser.
- `risk-gateway` — pre-trade gate. FastAPI med én write-endpoint (`POST /orders`).
- `risk-monitor` — post-trade circuit breaker med leader election + Kubernetes kill switch.
- `strategy-*` — trading-strategier som arver `BaseStrategy`. Modtager markedsdata, sender ordrer via HTTP.
- `api` — read-only FastAPI. Hybrid datakilde: in-memory NATS-cache for realtime + TimescaleDB for historik.
- `dashboard` — Next.js. Kun HTTP til API.

## NATS subject-hierarki

| Subject pattern | Producent | Subscribers | JetStream |
|---|---|---|---|
| `orders.<strategy>.<symbol>` | risk-gateway | ibkr-adapter (`orders.>`) | `ORDERS` (7d) |
| `fills.<account>.<symbol>` | ibkr-adapter | risk-monitor | `FILLS` (∞) |
| `pnl.<account>` | ibkr-adapter | risk-monitor, risk-gateway, api | `RISK` (30d) |
| `positions.<account>.<symbol>` | ibkr-adapter | risk-monitor, risk-gateway, api | `RISK` (30d) |
| `marketdata.realtime.<symbol>` | ibkr-adapter | strategies, risk-gateway | `MARKETDATA` (1h) |
| `risk.adapter.heartbeat` | ibkr-adapter | risk-monitor, api | `RISK` |
| `risk.adapter.disconnected` | ibkr-adapter | risk-monitor, api | `RISK` |
| `risk.adapter.reconnected` | ibkr-adapter | risk-monitor | `RISK` |
| `risk.halt` | risk-monitor | risk-gateway, api | `RISK` |

## Diagram

```mermaid
flowchart LR
    %% =============== EXTERNAL ===============
    TWS["IB Gateway / TWS<br/>(port 4002 paper / 4001 live)"]
    User["Browser"]

    %% =============== SERVICES ===============
    subgraph K8s["Kubernetes cluster (namespace: trading)"]
        Adapter["ibkr-adapter<br/>nats_bridge.py + gateway.py"]
        Strategies["strategy-hello / strategy-nvidia<br/>BaseStrategy"]
        RG["risk-gateway<br/>FastAPI POST /orders"]
        RM["risk-monitor<br/>CircuitBreaker + leader election"]
        API["trader-api<br/>FastAPI (read-only)"]
        Dash["dashboard<br/>Next.js"]
        TSDB[("TimescaleDB<br/>fills, pnl_ticks,<br/>positions_snapshot,<br/>order_events")]
        K8sAPI["Kubernetes API<br/>(scale Deployments)"]
    end

    %% =============== JETSTREAM STREAMS ===============
    subgraph NATS["NATS / JetStream"]
        S_ORDERS{{"ORDERS<br/>orders.> · 7d"}}
        S_FILLS{{"FILLS<br/>fills.> · ∞"}}
        S_MD{{"MARKETDATA<br/>marketdata.> · 1h"}}
        S_RISK{{"RISK<br/>risk.> · pnl.> · positions.> · 30d"}}
    end

    %% =============== TWS <-> ADAPTER ===============
    TWS -- "execDetailsEvent<br/>pnlEvent<br/>positionEvent<br/>pendingTickersEvent" --> Adapter
    Adapter -- "placeOrder(contract, order)" --> TWS

    %% =============== ADAPTER PUBLISHES ===============
    Adapter == "marketdata.realtime.&lt;symbol&gt;<br/>Tick{bid,ask,last}" ==> S_MD
    Adapter == "fills.&lt;account&gt;.&lt;symbol&gt;<br/>Fill{qty,price,exec_id}" ==> S_FILLS
    Adapter == "pnl.&lt;account&gt;<br/>PnLSnapshot{daily,unreal,real}" ==> S_RISK
    Adapter == "positions.&lt;account&gt;.&lt;symbol&gt;<br/>PositionSnapshot{qty,avg_cost}" ==> S_RISK
    Adapter == "risk.adapter.heartbeat (15s)<br/>risk.adapter.disconnected<br/>risk.adapter.reconnected" ==> S_RISK

    %% =============== STRATEGIES ===============
    S_MD == "marketdata.realtime.&lt;symbol&gt;" ==> Strategies
    Strategies -- "HTTP POST /orders<br/>OrderRequest{strategy,sym,side,qty,idem_key}" --> RG

    %% =============== RISK-GATEWAY ===============
    S_RISK == "pnl.> → strategy_daily_pnl<br/>positions.> → strategy_positions" ==> RG
    S_MD == "marketdata.> → last_prices<br/>(fat-finger ref)" ==> RG
    S_RISK == "risk.halt → halted=true" ==> RG
    RG == "orders.&lt;strategy&gt;.&lt;symbol&gt;<br/>(only if all 9 checks pass)" ==> S_ORDERS
    S_ORDERS == "orders.&gt; subscribe" ==> Adapter

    %% =============== RISK-MONITOR ===============
    S_FILLS == "fills.> (audit log)" ==> RM
    S_RISK == "pnl.> → AccountState<br/>positions.> → AccountState<br/>risk.adapter.heartbeat → liveness<br/>risk.adapter.disconnected" ==> RM
    RM == "risk.halt<br/>{reason, deployments, ts}" ==> S_RISK
    RM -- "list+patch Deployments<br/>replicas=0<br/>(label: component=strategy)" --> K8sAPI
    K8sAPI -. "scales to 0" .-> Strategies

    %% =============== API ===============
    S_RISK == "positions.> · pnl.><br/>risk.adapter.heartbeat<br/>risk.adapter.disconnected<br/>risk.halt → RealtimeCache" ==> API
    TSDB -- "asyncpg SELECT<br/>(fallback / history)" --> API

    %% =============== DASHBOARD ===============
    API -- "GET /status /positions<br/>/pnl /pnl/history<br/>/fills /orders" --> Dash
    Dash -- "HTML/JSON" --> User

    %% =============== STYLING ===============
    classDef stream fill:#1f3a5f,stroke:#6cf,color:#fff,stroke-width:2px
    classDef svc fill:#2d2d2d,stroke:#fbd38d,color:#fff
    classDef ext fill:#4a1a1a,stroke:#f56565,color:#fff
    classDef db fill:#1a4a2e,stroke:#68d391,color:#fff
    class S_ORDERS,S_FILLS,S_MD,S_RISK stream
    class Adapter,Strategies,RG,RM,API,Dash svc
    class TWS,User,K8sAPI ext
    class TSDB db
```

## Detaljerede dataflows

### 1. Order-flow (happy path)
Strategy beslutter (i `on_bar`) → `POST /orders` → `CheckEngine.check()` kører 9 fail-fast checks (`risk-gateway/src/risk_gateway/checks.py:70-80`) → ved success publiceres på `orders.<strategy>.<symbol>` → ibkr-adapter dekoder `OrderCommand`, kalder `place_order()` på `ib_insync` → TWS executes → `execDetailsEvent` → publiceres som `fills.<account>.<symbol>`.

### 2. State-feedback til risk-gateway
`pnl.>`, `positions.>`, `marketdata.>` fra ibkr-adapter opdaterer `CheckEngine.strategy_daily_pnl`, `strategy_positions`, og `last_prices` (`risk-gateway/src/risk_gateway/nats_sync.py:56-92`). Det er disse caches der bagefter tjekker daily-loss, position-limit og fat-finger på næste indkommende ordre.

### 3. Kill switch
risk-monitor leader-pod evaluerer `AccountState` mod thresholds (`risk-monitor/src/risk_monitor/circuit_breaker.py:40-91`) → ved breach: scaler alle deployments med label `app.kubernetes.io/component=strategy` til 0 replicas via Kubernetes API (`risk-monitor/src/risk_monitor/kill_switch.py:78-107`) + publicerer `risk.halt`. risk-gateway lytter på `risk.halt` og afviser efterfølgende ordrer (`risk-gateway/src/risk_gateway/checks.py:86-88`).

### 4. API hybrid-cache
`RealtimeCache` holder seneste position/PnL/halt-status i hukommelse (`api/src/trader_api/realtime.py:20-30`). Endpoints falder først tilbage til TimescaleDB hvis cachen er tom (`api/src/trader_api/app.py:62-68`).

## Vigtige observationer

- **Ingen anden service end ibkr-adapter har en TWS-forbindelse** — det er bevidst single-writer for at undgå dobbelte ordre-reservationer per `clientId`.
- **Adapter er stateless ift. NATS** — alle TWS-events oversættes 1:1 til pydantic-modeller og publiceres. Persistens er ned-streams ansvar.
- **JetStream er "best effort"** for adapter: hvis JS-publish fejler, falder den tilbage til core NATS (`ibkr-adapter/src/ibkr_adapter/nats_bridge.py:65-78`).
- **Risk-gateway og risk-monitor er to forskellige forsvarslag:** gateway = preventive (afvis ordre før send), monitor = corrective (sluk strategier efter tab).
- **TimescaleDB-skriverhuller:** `fills`, `pnl_ticks`, etc. defineres i schemaet og læses af API, men ingen service i repoet skriver til dem pt. — det er en åben ende.
