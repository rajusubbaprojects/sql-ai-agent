# App settings — loads all values from .env file
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_file": ".env", "extra": "ignore"}

    # Claude AI
    anthropic_api_key: str

    # MySQL Database
    db_host: str = "localhost"
    db_port: str = "3306"
    db_name: str
    db_user: str
    db_password: str

    # App
    app_env: str = "development"
    app_port: int = 8000
    debug: bool = True
    rules_file: str = "rules.yaml"

    # AWS (Phase 5)
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_s3_bucket_name: str = ""


@lru_cache()
def get_settings() -> Settings:
    return Settings()
