"""NATS subject constants.

Keeping all subjects in one place makes it trivial to verify that the
adapter, strategies, risk-gateway, and risk-monitor all use identical
subject strings.

Subject hierarchy:
  orders.<strategy>.<symbol>        — strategies → adapter (order commands)
  fills.<account>.<symbol>          — adapter → risk-monitor / dashboard
  pnl.<account>                     — adapter → risk-monitor / dashboard
  positions.<account>.<symbol>      — adapter → dashboard / API
  marketdata.<feed>.<symbol>        — adapter → strategies
  risk.adapter.heartbeat            — adapter → risk-monitor (liveness)
  risk.adapter.disconnected         — adapter → risk-monitor (alert)
  risk.adapter.reconnected          — adapter → risk-monitor (alert)
"""

# Inbound (adapter subscribes)
ORDERS_INBOX = "orders.>"          # wildcard — all strategies, all symbols

# Outbound (adapter publishes)


def fills(account: str, symbol: str) -> str:
    return f"fills.{account}.{symbol}"


def pnl(account: str) -> str:
    return f"pnl.{account}"


def positions(account: str, symbol: str) -> str:
    return f"positions.{account}.{symbol}"


def marketdata(feed: str, symbol: str) -> str:
    return f"marketdata.{feed}.{symbol}"


HEARTBEAT = "risk.adapter.heartbeat"
DISCONNECTED = "risk.adapter.disconnected"
RECONNECTED = "risk.adapter.reconnected"
