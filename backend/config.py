"""Application settings loaded from the .env file via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Typed application settings read from environment variables / .env.

    Attributes:
        anthropic_api_key: API key for the Anthropic Claude service.
        db_host: MySQL host address.
        db_port: MySQL port number as a string.
        db_name: Default database name.
        db_user: MySQL user name.
        db_password: MySQL password.
        app_env: Deployment environment ("development", "production", etc.).
        app_port: Port the FastAPI server listens on.
        debug: Enable uvicorn auto-reload and verbose logging.
        rules_file: Path to the YAML business rules file.
        aws_region: AWS region for S3/CloudFront resources.
        aws_access_key_id: AWS access key ID.
        aws_secret_access_key: AWS secret access key.
        aws_s3_bucket_name: S3 bucket used for static frontend assets.
    """

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
    """Return the cached application settings singleton.

    Returns:
        Settings instance populated from environment variables and .env.
    """
    return Settings()
