"""Application configuration using Pydantic Settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "Pralapin SMS"
    debug: bool = False

    # School / Receipt
    school_name: str = ""
    school_address: str = ""
    school_logo_url: str = ""  # optional; if set, shown on receipt instead of school name
    trust_logo_url: str = ""  # optional; logo at bottom of receipt
    trust_address: str = ""  # optional; address text at bottom of receipt

    # MongoDB
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "pralapin"

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # AWS S3
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    s3_bucket_photos: str = "pralapin-photos"
    s3_bucket_receipts: str = "pralapin-receipts"

    # Firebase (FCM)
    firebase_credentials_path: str = ""

    # CCTV / HLS
    cctv_base_url: str = ""
    school_hours_start: str = "08:00"
    school_hours_end: str = "18:00"


settings = Settings()
