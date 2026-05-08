"""Configuration via environment variables.

Risk thresholds come from values.yaml → Helm template → env block.
Adjust them in values.yaml / values.paper.yaml without rebuilding the image.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    # ------------------------------------------------------------------ NATS
    nats_url: str = Field("nats://nats:4222", alias="NATS_URL")

    # --------------------------------------------------------------- Account
    ibkr_account: str = Field("", alias="IBKR_ACCOUNT")
    ibkr_mode: str = Field("paper", alias="IBKR_MODE")

    # --------------------------------------------------- Risk thresholds
    # Daily P&L drop that triggers a halt (negative number, e.g. -500 = -$500)
    max_daily_loss: float = Field(-500.0, alias="MAX_DAILY_LOSS")

    # Portfolio drawdown from today's high-water mark (0.05 = 5%)
    max_drawdown_pct: float = Field(0.05, alias="MAX_DRAWDOWN_PCT")

    # Gross exposure cap in account currency
    max_gross_exposure: float = Field(1_000_000.0, alias="MAX_GROSS_EXPOSURE")

    # How many seconds without a heartbeat from the adapter before alerting
    heartbeat_timeout_s: float = Field(60.0, alias="HEARTBEAT_TIMEOUT_S")

    # How often the monitor re-evaluates risk state (seconds)
    reconcile_interval_s: float = Field(10.0, alias="RECONCILE_INTERVAL_S")

    # --------------------------------------------------------- Kill switch
    # Set to "false" in paper / dev to avoid accidentally scaling down pods
    kill_switch_enabled: bool = Field(True, alias="KILL_SWITCH_ENABLED")

    # Kubernetes namespace where strategy Deployments live
    k8s_namespace: str = Field("default", alias="K8S_NAMESPACE")

    # Helm release name — used to find strategy Deployments by label
    release_name: str = Field("ibkrtrader", alias="RELEASE_NAME")

    # ----------------------------------------------------------- Telegram
    telegram_enabled: bool = Field(False, alias="TELEGRAM_ENABLED")
    telegram_token: str = Field("", alias="TELEGRAM_TOKEN")
    telegram_chat_id: str = Field("", alias="TELEGRAM_CHAT_ID")

    # ------------------------------------------------ Leader election
    # Name of the Kubernetes Lease object used for leader election
    lease_name: str = Field("risk-monitor-leader", alias="LEASE_NAME")
    lease_duration_s: int = Field(15, alias="LEASE_DURATION_S")
    lease_renew_deadline_s: int = Field(10, alias="LEASE_RENEW_DEADLINE_S")
    lease_retry_period_s: int = Field(2, alias="LEASE_RETRY_PERIOD_S")

    # Pod identity injected by Kubernetes downward API
    pod_name: str = Field("risk-monitor-0", alias="POD_NAME")

    # --------------------------------------------------------------- Health
    health_port: int = Field(8080, alias="HEALTH_PORT")

    # --------------------------------------------------------------- Metrics
    metrics_port: int = Field(9090, alias="METRICS_PORT")

    # --------------------------------------------------------------- Logging
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("json", alias="LOG_FORMAT")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
