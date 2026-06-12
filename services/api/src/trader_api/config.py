"""Config foil for trader api.
samler nats, logging
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
# basesettings gør at værdier automatisk kan læses fra enviroment variables


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", case_sensitive=False)

    nats_url: str = Field("nats://nats:4222", alias="NATS_URL")

    ibkr_account: str = Field("", alias="IBKR_ACCOUNT")
    ibkr_mode: str = Field("paper", alias="IBKR_MODE")

    port: int = Field(8000, alias="PORT")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("json", alias="LOG_FORMAT")


# singleton, setting bliver kun oprettet en gang, sikrer hele appen bruger samme config
_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
