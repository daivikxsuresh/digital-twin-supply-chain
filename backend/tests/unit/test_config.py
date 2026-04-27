from app.config import settings


def test_settings_loads():
    assert settings.app_name == "Digital Twin Supply Chain"
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.kafka_bootstrap_servers != ""
    assert settings.secret_key != ""
    assert settings.access_token_expire_minutes == 15
    assert settings.refresh_token_expire_days == 7


def test_settings_defaults():
    assert settings.db_pool_min_size == 5
    assert settings.db_pool_max_size == 20
    assert settings.kpi_dashboard_cache_ttl == 300
    assert settings.kpi_live_cache_ttl == 60
