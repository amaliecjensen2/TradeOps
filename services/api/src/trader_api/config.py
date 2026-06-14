"""Konfiguration for trader-api.

Læser indstillinger fra environment variables (Helm chartet sætter dem på podden).
BaseSettings fra pydantic-settings mapper hver env var til et felt automatisk.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    nats_url: str = Field("nats://nats:4222", alias="NATS_URL")

    ibkr_account: str = Field("", alias="IBKR_ACCOUNT")
    ibkr_mode: str = Field("paper", alias="IBKR_MODE")

    port: int = Field(8000, alias="PORT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("json", alias="LOG_FORMAT")


# Singleton: Settings instantieres kun første gang og genbruges derefter,
# så hele appen ser samme config (og vi undgår at læse env vars gentagne gange).
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
