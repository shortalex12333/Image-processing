"""
Configuration management for Image Processing Service.
Loads environment variables with validation.
"""

import os
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # =============================================================================
    # Supabase Configuration
    # =============================================================================
    next_public_supabase_url: str
    supabase_service_role_key: str
    supabase_anon_key: str

    # =============================================================================
    # OpenAI Configuration
    # =============================================================================
    openai_api_key: str
    openai_org_id: str | None = None

    # =============================================================================
    # OCR Configuration
    # =============================================================================
    ocr_engine: Literal["tesseract", "google_vision", "aws_textract"] = "tesseract"
    tesseract_cmd: str = "/usr/local/bin/tesseract"

    # Google Vision (optional)
    google_cloud_project_id: str | None = None
    google_application_credentials: str | None = None

    # AWS Textract (optional)
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"

    # =============================================================================
    # LLM Model Selection
    # =============================================================================
    llm_classification_model: str = "gpt-4.1-nano"
    llm_normalization_model: str = "gpt-4.1-mini"
    llm_escalation_model: str = "gpt-4.1"

    # =============================================================================
    # Cost Control & Budget Limits
    # =============================================================================
    max_llm_calls_per_session: int = 3
    max_token_budget_per_session: int = 10000
    max_cost_per_session: float = 0.50
    max_cost_per_image: float = 0.30
    llm_coverage_threshold: float = 0.8

    # =============================================================================
    # Storage Configuration
    # =============================================================================
    storage_bucket_receiving: str = "pms-receiving-images"
    storage_bucket_discrepancy: str = "pms-discrepancy-photos"
    storage_bucket_labels: str = "pms-label-pdfs"
    storage_bucket_parts: str = "pms-part-photos"
    storage_bucket_finance: str = "pms-finance-documents"

    # =============================================================================
    # Rate Limiting & Upload Constraints
    # =============================================================================
    max_uploads_per_hour: int = 50
    max_file_size_mb: int = 15
    max_files_per_upload: int = 10
    upload_rate_limit_window_seconds: int = 3600

    # Blur Detection
    blur_threshold: float = 100.0
    min_image_width: int = 800
    min_image_height: int = 600

    # =============================================================================
    # JWT & Authentication
    # =============================================================================
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_audience: str = "authenticated"

    # =============================================================================
    # Deployment Configuration
    # =============================================================================
    render_service_url: str | None = None
    port: int = 8001
    log_level: Literal["debug", "info", "warning", "error"] = "info"
    environment: Literal["development", "staging", "production"] = "development"

    # =============================================================================
    # Feature Flags
    # =============================================================================
    enable_cloud_ocr_fallback: bool = True
    enable_llm_escalation: bool = True
    enable_auto_part_creation: bool = False
    enable_cost_alerts: bool = True

    # =============================================================================
    # Monitoring & Observability
    # =============================================================================
    sentry_dsn: str | None = None
    sentry_environment: str = "development"
    sentry_traces_sample_rate: float = 0.1

    # =============================================================================
    # Computed Properties
    # =============================================================================
    @property
    def max_file_size_bytes(self) -> int:
        """Convert max file size from MB to bytes."""
        return self.max_file_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"


# Global settings instance
settings = Settings()


# Model pricing configuration
MODEL_PRICING = {
    "gpt-4.1-nano": {
        "input": 0.00010 / 1000,   # $0.10 per 1M tokens
        "output": 0.00020 / 1000   # $0.20 per 1M tokens
    },
    "gpt-4.1-mini": {
        "input": 0.015 / 1000,     # $15 per 1M tokens
        "output": 0.030 / 1000     # $30 per 1M tokens
    },
    "gpt-4.1": {
        "input": 0.075 / 1000,     # $75 per 1M tokens
        "output": 0.150 / 1000     # $150 per 1M tokens
    }
}


def calculate_llm_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Calculate cost for an LLM API call.

    Args:
        model: Model name (gpt-4.1-nano, gpt-4.1-mini, gpt-4.1)
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD

    Example:
        >>> calculate_llm_cost("gpt-4.1-mini", 1500, 800)
        0.0465
    """
    if model not in MODEL_PRICING:
        raise ValueError(f"Unknown model: {model}")

    pricing = MODEL_PRICING[model]
    input_cost = input_tokens * pricing["input"]
    output_cost = output_tokens * pricing["output"]
    return input_cost + output_cost
