"""
Configuration management for Image Processing Service.
Loads environment variables with validation.
"""

import os
from typing import Literal, Optional
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
    next_public_supabase_url: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    supabase_anon_key: Optional[str] = None

    # =============================================================================
    # OpenAI Configuration
    # =============================================================================
    openai_api_key: Optional[str] = None
    openai_org_id: Optional[str] = None

    # =============================================================================
    # OCR Configuration
    # =============================================================================
    ocr_engine: Literal["tesseract", "google_vision", "aws_textract"] = "tesseract"
    tesseract_cmd: str = "/usr/bin/tesseract"  # Docker/Linux default path

    # Google Vision (optional)
    google_cloud_project_id: Optional[str] = None
    google_application_credentials: Optional[str] = None

    # AWS Textract (optional)
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
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

    # Blur Detection (legacy - now part of DQS)
    blur_threshold: float = 100.0
    min_image_width: int = 800
    min_image_height: int = 600

    # Document Quality Score (DQS) Configuration
    dqs_threshold: float = 70.0  # Overall quality score threshold
    dqs_blur_weight: float = 0.4  # Blur contributes 40% to DQS
    dqs_glare_weight: float = 0.3  # Glare contributes 30% to DQS
    dqs_contrast_weight: float = 0.3  # Contrast contributes 30% to DQS
    glare_pixel_threshold: int = 250  # Brightness level (0-255) to consider as glare
    glare_percent_max: float = 5.0  # Maximum % of pixels that can be glare
    contrast_michelson_min: float = 0.7  # Minimum Michelson contrast ratio

    # =============================================================================
    # JWT & Authentication
    # =============================================================================
    jwt_secret: Optional[str] = None
    jwt_algorithm: str = "HS256"
    jwt_audience: str = "authenticated"

    # =============================================================================
    # Deployment Configuration
    # =============================================================================
    render_service_url: Optional[str] = None
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
    sentry_dsn: Optional[str] = None
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
