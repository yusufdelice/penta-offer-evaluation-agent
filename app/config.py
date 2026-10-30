from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal


class Settings(BaseSettings):
    """Application configuration and business rule threshold settings."""

    APP_NAME: str = "AI-Powered Offer Pre-Evaluation Agent API"
    VERSION: str = "1.0.0"

    # Business Rule Thresholds
    CRITICAL_MARGIN_THRESHOLD: float = 10.0
    HIGH_VALUE_THRESHOLD: float = 100000.0
    HIGH_DISCOUNT_THRESHOLD: float = 15.0
    STOCK_COVERAGE_THRESHOLD: float = 0.7

    # LLM Settings
    GROQ_API_KEY: str = ""
    LLM_MODE: Literal["mock", "groq"] = "mock"
    LLM_MODEL: str = "qwen/qwen3.8-27b"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
