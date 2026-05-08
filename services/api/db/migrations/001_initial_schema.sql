-- ibkrtrader TimescaleDB schema
-- Run once at cluster bootstrap via the init Job (see timescale-init-job.yaml).
-- Safe to re-run: all statements use IF NOT EXISTS.

-- ============================================================
-- Extensions
-- ============================================================
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================
-- fills — every execution report from TWS
-- ============================================================
CREATE TABLE IF NOT EXISTS fills (
    timestamp       TIMESTAMPTZ NOT NULL,
    account         TEXT        NOT NULL,
    symbol          TEXT        NOT NULL,
    sec_type        TEXT        NOT NULL DEFAULT 'STK',
    exchange        TEXT        NOT NULL DEFAULT 'SMART',
    side            TEXT        NOT NULL,           -- BUY | SELL
    quantity        DOUBLE PRECISION NOT NULL,
    price           DOUBLE PRECISION NOT NULL,
    commission      DOUBLE PRECISION,
    perm_id         BIGINT,
    exec_id         TEXT        NOT NULL,
    order_ref       TEXT        NOT NULL DEFAULT ''
);

SELECT create_hypertable('fills', 'timestamp', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS fills_account_symbol_idx ON fills (account, symbol, timestamp DESC);
CREATE UNIQUE INDEX IF NOT EXISTS fills_exec_id_idx ON fills (exec_id);

-- ============================================================
-- pnl_ticks — periodic PnL snapshots from the adapter
-- ============================================================
CREATE TABLE IF NOT EXISTS pnl_ticks (
    timestamp           TIMESTAMPTZ      NOT NULL,
    account             TEXT             NOT NULL,
    daily_pnl           DOUBLE PRECISION NOT NULL DEFAULT 0,
    unrealized_pnl      DOUBLE PRECISION NOT NULL DEFAULT 0,
    realized_pnl        DOUBLE PRECISION NOT NULL DEFAULT 0,
    net_liquidation     DOUBLE PRECISION
);

SELECT create_hypertable('pnl_ticks', 'timestamp', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS pnl_ticks_account_idx ON pnl_ticks (account, timestamp DESC);

-- Continuous aggregate: 1-minute PnL bars for the chart
CREATE MATERIALIZED VIEW IF NOT EXISTS pnl_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', timestamp) AS bucket,
    account,
    last(daily_pnl, timestamp)         AS daily_pnl,
    last(net_liquidation, timestamp)   AS net_liquidation
FROM pnl_ticks
GROUP BY bucket, account
WITH NO DATA;

-- ============================================================
-- positions_snapshot — latest known position per symbol
-- ============================================================
CREATE TABLE IF NOT EXISTS positions_snapshot (
    timestamp       TIMESTAMPTZ      NOT NULL,
    account         TEXT             NOT NULL,
    symbol          TEXT             NOT NULL,
    sec_type        TEXT             NOT NULL DEFAULT 'STK',
    avg_cost        DOUBLE PRECISION NOT NULL DEFAULT 0,
    position        DOUBLE PRECISION NOT NULL DEFAULT 0,
    market_price    DOUBLE PRECISION,
    market_value    DOUBLE PRECISION
);

SELECT create_hypertable('positions_snapshot', 'timestamp', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS positions_account_symbol_idx ON positions_snapshot (account, symbol, timestamp DESC);

-- ============================================================
-- order_events — audit trail for every order attempt
-- ============================================================
CREATE TABLE IF NOT EXISTS order_events (
    timestamp       TIMESTAMPTZ NOT NULL,
    strategy        TEXT        NOT NULL,
    symbol          TEXT        NOT NULL,
    side            TEXT        NOT NULL,
    quantity        DOUBLE PRECISION NOT NULL,
    order_type      TEXT        NOT NULL DEFAULT 'MKT',
    status          TEXT        NOT NULL,           -- accepted | rejected | filled | cancelled
    reject_reason   TEXT,
    idempotency_key TEXT,
    tws_order_id    BIGINT
);

SELECT create_hypertable('order_events', 'timestamp', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS order_events_strategy_idx ON order_events (strategy, timestamp DESC);

-- ============================================================
-- marketdata_bars — optional OHLCV storage (1-min bars)
-- ============================================================
CREATE TABLE IF NOT EXISTS marketdata_bars (
    timestamp   TIMESTAMPTZ      NOT NULL,
    symbol      TEXT             NOT NULL,
    feed        TEXT             NOT NULL DEFAULT 'realtime',
    open        DOUBLE PRECISION NOT NULL,
    high        DOUBLE PRECISION NOT NULL,
    low         DOUBLE PRECISION NOT NULL,
    close       DOUBLE PRECISION NOT NULL,
    volume      BIGINT           NOT NULL DEFAULT 0
);

SELECT create_hypertable('marketdata_bars', 'timestamp', if_not_exists => TRUE);
CREATE UNIQUE INDEX IF NOT EXISTS marketdata_symbol_ts_idx ON marketdata_bars (symbol, feed, timestamp DESC);
