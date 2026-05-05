# backend/config/__init__.py
# App settings loaded from .env

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "airlines_db"

    # Anthropic
    anthropic_api_key: str = ""

    # App
    app_env: str = "development"
    app_debug: bool = True

    model_config = {"env_file": ".env"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
