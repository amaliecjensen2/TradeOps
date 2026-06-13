"""Konfiguration for risk gateway.

Globale grænser kommer fra values.yaml riskGateway.global.
Per strategi grænser injiceres via STRATEGY_LIMITS_JSON env var,
renderet af Helm strategy deployment templaten.
"""

import json

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # NATS
    nats_url: str = Field("nats://nats:4222", alias="NATS_URL")

    # Konto
    ibkr_account: str = Field("", alias="IBKR_ACCOUNT")
    ibkr_mode: str = Field("paper", alias="IBKR_MODE")

    # Globale risikogrænser
    max_account_drawdown_pct: float = Field(
        0.05, alias="MAX_ACCOUNT_DRAWDOWN_PCT")
    max_gross_exposure: float = Field(1_000_000.0, alias="MAX_GROSS_EXPOSURE")
    max_orders_per_second: int = Field(50, alias="MAX_ORDERS_PER_SECOND")
    # Kommasepareret liste af symboler der aldrig må handles
    restricted_symbols: str = Field("", alias="RESTRICTED_SYMBOLS")

    # Per strategi grænser (JSON map)
    # Format: {"hello": {"maxOrderNotional": 1000, "maxDailyLoss": 100, ...}}
    strategy_limits_json: str = Field("{}", alias="STRATEGY_LIMITS_JSON")

    # Server
    port: int = Field(8080, alias="PORT")

    # Logging
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("json", alias="LOG_FORMAT")

    @property
    def restricted_symbols_set(self) -> set[str]:
        return {s.strip().upper() for s in self.restricted_symbols.split(",") if s.strip()}

    @property
    def strategy_limits(self) -> dict:
        try:
            return json.loads(self.strategy_limits_json)
        except Exception:
            return {}


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
