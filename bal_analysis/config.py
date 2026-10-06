from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    """
    Application configuration settings.
    Loads values from environment variables or a .env file.
    Includes PostgreSQL, Redis, Processor, and FastAPI settings.
    """
    # Source DB (bala_billing)
    SOURCE_DB_HOST: str = "localhost"
    SOURCE_DB_PORT: int = 5432
    SOURCE_DB_USER: str = "postgres"
    SOURCE_DB_PASSWORD: str = "postgres"
    SOURCE_DB_NAME: str = "bala_billing"

    # Metrics DB (Analytics)
    METRICS_DB_HOST: str = "localhost"
    METRICS_DB_PORT: int = 5432
    METRICS_DB_USER: str = "postgres"
    METRICS_DB_PASSWORD: str = "postgres"
    METRICS_DB_NAME: str = "analytics_db"

    # Processor Configuration
    PROCESSOR_NAME: str = "cdr_analytics_processor"
    BATCH_SIZE: int = 1000
    LOOP_INTERVAL_SEC: int = 5

    # FastAPI Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8001

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
