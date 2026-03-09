from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_env: str = "development"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database
    database_url: str = "postgresql+asyncpg://kalye:kalye_dev@localhost:5432/kalye"
    database_url_sync: str = "postgresql://kalye:kalye_dev@localhost:5432/kalye"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    s3_bucket_name: str = "kalye-images"

    # Auth
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # Maps
    mapbox_access_token: str = ""

    # AI Models
    hf_token: str = ""
    model_cache_dir: str = "/tmp/models"

    # Observability
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    prometheus_port: int = 9090

    # Feature Flags
    enable_vqa: bool = False
    enable_rag_chat: bool = True
    enable_auto_blur: bool = True

    # Cost Controls
    max_inference_jobs_per_hour: int = 1000
    cache_ttl_seconds: int = 3600


@lru_cache
def get_settings() -> Settings:
    return Settings()
