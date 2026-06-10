"""Strategi konfiguration, indlæst fra env vars + ConfigMap mount."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # Identitet
    strategy_name: str = Field("nvidia", alias="STRATEGY_NAME")
    client_id: int = Field(12, alias="IBKR_CLIENT_ID")
    ibkr_account: str = Field("", alias="IBKR_ACCOUNT")

    # Forbindelse
    nats_url: str = Field("nats://nats:4222", alias="NATS_URL")
    risk_gateway_url: str = Field(
        "http://ibkrtrader-risk-gateway:8080", alias="RISK_GATEWAY_URL")

    # Strategi parametre
    universe: list[str] = Field(["NVDA"], alias="UNIVERSE")
    trade_qty: float = Field(1.0, alias="TRADE_QTY")  # shares at købe

    # Risiko
    max_daily_loss: float = Field(-500.0, alias="MAX_DAILY_LOSS")

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
