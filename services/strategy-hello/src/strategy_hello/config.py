"""Strategy configuration — loaded from env vars + ConfigMap mount.

The Helm strategy-deployment template mounts the strategy's ConfigMap
at /config/strategy.yaml and sets CONFIG_PATH to that path.
Values in the YAML override env-var defaults.
"""

from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # ------------------------------------------------------------------ Identity
    strategy_name: str = Field("hello", alias="STRATEGY_NAME")
    client_id: int = Field(11, alias="IBKR_CLIENT_ID")
    ibkr_account: str = Field("", alias="IBKR_ACCOUNT")

    # ------------------------------------------------------------------ Connectivity
    nats_url: str = Field("nats://nats:4222", alias="NATS_URL")
    risk_gateway_url: str = Field(
        "http://ibkrtrader-risk-gateway:8080", alias="RISK_GATEWAY_URL")

    # ------------------------------------------------------------------ Strategy params
    # These can also be set via the ConfigMap (values.yaml strategies[].config)
    universe: list[str] = Field(["AAPL"], alias="UNIVERSE")
    # short MA window (bars)
    fast_period: int = Field(5,  alias="FAST_PERIOD")
    slow_period: int = Field(20, alias="SLOW_PERIOD")   # long MA window (bars)
    trade_qty: float = Field(1.0, alias="TRADE_QTY")    # shares per signal

    # ------------------------------------------------------------------ Risk
    max_daily_loss: float = Field(-200.0, alias="MAX_DAILY_LOSS")

    # ------------------------------------------------------------------ Health
    health_port: int = Field(8080, alias="HEALTH_PORT")
    metrics_port: int = Field(9090, alias="METRICS_PORT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("json", alias="LOG_FORMAT")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
