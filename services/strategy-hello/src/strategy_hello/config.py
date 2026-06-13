"""Strategi konfiguration, indlæst fra env vars + ConfigMap mount.

Helm strategy deployment templaten mounter strategiens ConfigMap
ved /config/strategy.yaml og sætter CONFIG_PATH til den sti.
Værdier i YAMLen overstyrer env var defaults.
"""

from __future__ import annotations

import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # Identitet
    strategy_name: str = Field("hello", alias="STRATEGY_NAME")
    client_id: int = Field(11, alias="IBKR_CLIENT_ID")
    ibkr_account: str = Field("", alias="IBKR_ACCOUNT")

    # Forbindelse
    nats_url: str = Field("nats://nats:4222", alias="NATS_URL")
    risk_gateway_url: str = Field(
        "http://ibkrtrader-risk-gateway:8080", alias="RISK_GATEWAY_URL")

    # Strategi parametre
    # Disse kan også sættes via ConfigMap (values.yaml strategies[].config)
    universe: list[str] = Field(["AAPL"], alias="UNIVERSE")
    # kort MA vindue (bars)
    fast_period: int = Field(5,  alias="FAST_PERIOD")
    slow_period: int = Field(20, alias="SLOW_PERIOD")   # langt MA vindue (bars)
    trade_qty: float = Field(1.0, alias="TRADE_QTY")    # shares pr signal

    # Health
    health_port: int = Field(8080, alias="HEALTH_PORT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("json", alias="LOG_FORMAT")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
