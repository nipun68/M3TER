"""
Application configuration and environment variables.
"""
from __future__ import annotations
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env")


class Settings:
    ENV: str = os.getenv("ENVIRONMENT", "development")
    PORT: int = int(os.getenv("PORT", "8000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/m3ter_db")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "m3ter_default_jwt_secret_key_minimum_32_characters_for_hs256")
    STRIPE_SECRET_KEY: Optional[str] = os.getenv("STRIPE_SECRET_KEY", None)
    STRIPE_WEBHOOK_SECRET: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET", None)
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL", None)

    # Metering buffer configuration
    METER_BATCH_SIZE: int = int(os.getenv("METER_BATCH_SIZE", "100"))
    METER_FLUSH_INTERVAL_SECONDS: float = float(os.getenv("METER_FLUSH_INTERVAL", "5.0"))
    ENTITLEMENT_CACHE_TTL_SECONDS: float = float(os.getenv("ENTITLEMENT_CACHE_TTL", "30.0"))
    LIFECYCLE_INTERVAL_SECONDS: float = float(os.getenv("LIFECYCLE_INTERVAL", "60.0"))


settings = Settings()
