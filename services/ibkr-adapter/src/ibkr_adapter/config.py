"""Configuration loaded from environment variables.

All settings have sane defaults for paper trading against a local cluster.
In Kubernetes they are overridden via the ibkr-adapter Deployment env block
(rendered from values.yaml by ibkr-adapter.yaml template).
"""

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # ------------------------------------------------------------------ IBKR
    ibgw_host: str = Field("ibkrtrader-gateway-paper", alias="IBGW_HOST")
    ibgw_port: int = Field(4004, alias="IBGW_PORT")
    ibkr_client_id: int = Field(1, alias="IBKR_CLIENT_ID")
    ibkr_account: str = Field("", alias="IBKR_ACCOUNT")

    # Comma-separated tickers to stream realtime market data for (e.g. "NVDA,AAPL").
    # Bars/ticks are published to marketdata.realtime.<SYMBOL> for strategies.
    universe: str = Field("", alias="UNIVERSE")

    # Reconnect settings
    reconnect_interval_s: float = Field(10.0, alias="RECONNECT_INTERVAL_S")
    max_reconnect_attempts: int = Field(
        0, alias="MAX_RECONNECT_ATTEMPTS")  # 0 = infinite

    # ------------------------------------------------------------------ NATS
    nats_url: str = Field("nats://nats:4222", alias="NATS_URL")

    # ----------------------------------------------------------------- Health
    health_port: int = Field(8080, alias="HEALTH_PORT")

    # --------------------------------------------------------------- Metrics
    metrics_port: int = Field(9090, alias="METRICS_PORT")

    # --------------------------------------------------------------- Logging
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("json", alias="LOG_FORMAT")  # json | console

    @field_validator("ibkr_client_id")
    @classmethod
    def client_id_range(cls, v: int) -> int:
        if not (1 <= v <= 32767):
            raise ValueError("ibkr_client_id must be between 1 and 32767")
        return v

    @property
    def universe_list(self) -> list[str]:
        return [s.strip().upper() for s in self.universe.split(",") if s.strip()]


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
