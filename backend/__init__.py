"""Backend package — application settings loaded from the .env file."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Typed application settings read from environment variables / .env.

    Attributes:
        db_host: MySQL host address.
        db_port: MySQL port number.
        db_user: MySQL user name.
        db_password: MySQL password.
        db_name: Default database name.
        anthropic_api_key: API key for the Anthropic Claude service.
        app_env: Deployment environment ("development", "production", etc.).
        app_debug: Enable verbose logging and auto-reload.
    """

    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "airlines_db"

    anthropic_api_key: str = ""

    app_env: str = "development"
    app_debug: bool = True

    model_config = {"env_file": ".env"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached application settings singleton.

    Returns:
        Settings instance populated from environment variables and .env.
    """
    return Settings()
