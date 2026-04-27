from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    app_name: str = "Digital Twin Supply Chain"
    environment: str = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://dtuser:dtpassword@localhost:5432/digitaltwin"
    db_pool_min_size: int = 5
    db_pool_max_size: int = 20

    # Kafka
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_consumer_group: str = "digital-twin-consumers"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth
    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # KPI cache TTLs (seconds)
    kpi_dashboard_cache_ttl: int = 300
    kpi_live_cache_ttl: int = 60

    # Twin
    twin_snapshot_interval_seconds: int = 300

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
