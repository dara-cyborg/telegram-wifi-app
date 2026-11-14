from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str
    telegram_group_chat_id: str
    admin_telegram_id: int
    timezone: str = "Asia/Phnom_Penh"
    database_path: str = "./data/tracker.db"
    dev_mode: bool = False
    port: int = 8001
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
