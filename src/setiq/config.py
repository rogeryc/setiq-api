from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    environment: str = "development"
    log_level: str = "INFO"

    # Superuser URL — used by dbmate for migrations and the seed script.
    database_url: str = "postgresql://setiq:setiq_dev@localhost:5432/setiq"
    # Non-superuser URL — used by the FastAPI runtime so RLS actually fires.
    app_database_url: str = "postgresql://setiq_app:setiq_dev_password@localhost:5432/setiq"
    redis_url: str = "redis://localhost:6379/0"

    jwt_secret: str = "dev_only_change_me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 60 * 8           # standard session = working day
    jwt_remember_me_minutes: int = 60 * 24 * 30  # "Recordarme" = 30 days

    # Meta App credentials (developers.facebook.com)
    meta_app_id: str = ""
    meta_app_secret: str = ""
    meta_webhook_verify_token: str = "dev_only_change_me"

    anthropic_api_key: str = ""


settings = Settings()
