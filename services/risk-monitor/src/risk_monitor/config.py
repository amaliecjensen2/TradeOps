"""Konfiguration via miljøvariabler.

Risikogrænser kommer fra values.yaml til Helm template til env blok.
Juster dem i values.yaml / values.paper.yaml uden at genbygge image.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # NATS
    nats_url: str = Field("nats://nats:4222", alias="NATS_URL")

    # Konto
    ibkr_account: str = Field("", alias="IBKR_ACCOUNT")
    ibkr_mode: str = Field("paper", alias="IBKR_MODE")

    # Risikogrænser
    # Dagligt P&L fald der udløser en halt (negativt tal, fx 500 = $500)
    max_daily_loss: float = Field(-500.0, alias="MAX_DAILY_LOSS")

    # Portefølje drawdown fra dagens high water mark (0.05 = 5%)
    max_drawdown_pct: float = Field(0.05, alias="MAX_DRAWDOWN_PCT")

    # Loft for gross exponering i kontoens valuta
    max_gross_exposure: float = Field(1_000_000.0, alias="MAX_GROSS_EXPOSURE")

    # Hvor mange sekunder uden heartbeat fra adapteren før der alarmeres
    heartbeat_timeout_s: float = Field(60.0, alias="HEARTBEAT_TIMEOUT_S")

    # Hvor ofte monitoren reevaluerer risikotilstand (sekunder)
    reconcile_interval_s: float = Field(10.0, alias="RECONCILE_INTERVAL_S")

    # Kill switch
    # Sæt til "false" i paper / dev for at undgå utilsigtet nedskalering af pods
    kill_switch_enabled: bool = Field(True, alias="KILL_SWITCH_ENABLED")

    # Kubernetes namespace hvor strategi Deployments lever
    k8s_namespace: str = Field("default", alias="K8S_NAMESPACE")

    # Helm release navn, bruges til at finde strategi Deployments via label
    release_name: str = Field("ibkrtrader", alias="RELEASE_NAME")

    # Telegram
    telegram_enabled: bool = Field(False, alias="TELEGRAM_ENABLED")
    telegram_token: str = Field("", alias="TELEGRAM_TOKEN")
    telegram_chat_id: str = Field("", alias="TELEGRAM_CHAT_ID")

    # Leader election
    # Navn på Kubernetes Lease objektet brugt til leader election
    lease_name: str = Field("risk-monitor-leader", alias="LEASE_NAME")
    lease_duration_s: int = Field(15, alias="LEASE_DURATION_S")
    lease_renew_deadline_s: int = Field(10, alias="LEASE_RENEW_DEADLINE_S")
    lease_retry_period_s: int = Field(2, alias="LEASE_RETRY_PERIOD_S")

    # Pod identitet injiceret af Kubernetes downward API
    pod_name: str = Field("risk-monitor-0", alias="POD_NAME")

    # Health
    health_port: int = Field(8080, alias="HEALTH_PORT")

    # Metrics
    metrics_port: int = Field(9090, alias="METRICS_PORT")

    # Logging
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("json", alias="LOG_FORMAT")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
