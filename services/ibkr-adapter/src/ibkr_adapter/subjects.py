"""NATS subject konstanter.

At holde alle subjects et sted gør det trivielt at verificere at
adapteren, strategier, risk gateway og risk monitor alle bruger identiske
subject strenge.

Subject hierarki:
  orders.<strategy>.<symbol>        strategier til adapter (ordrekommandoer)
  fills.<account>.<symbol>          adapter til risk monitor / dashboard
  pnl.<account>                     adapter til risk monitor / dashboard
  positions.<account>.<symbol>      adapter til dashboard / API
  marketdata.<feed>.<symbol>        adapter til strategier
  risk.adapter.heartbeat            adapter til risk monitor (liveness)
  risk.adapter.disconnected         adapter til risk monitor (alarm)
  risk.adapter.reconnected          adapter til risk monitor (alarm)
  risk.adapter.snapshot_complete    adapter signalerer at initial pnl + positions
                                    snapshot er publiceret; risk-gateway gater
                                    /orders indtil denne ses
"""

# Indkommende (adapter abonnerer)
ORDERS_INBOX = "orders.>"          # wildcard, alle strategier, alle symboler

# Udgående (adapter publicerer)


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
SNAPSHOT_COMPLETE = "risk.adapter.snapshot_complete"
