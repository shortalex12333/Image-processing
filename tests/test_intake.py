"""
Tests for intake layer (validation, deduplication, rate limiting).
"""

import pytest
import hashlib
from uuid import uuid4
from io import BytesIO
from fastapi import UploadFile

from src.intake.validator import FileValidator
from src.intake.deduplicator import Deduplicator
from src.intake.rate_limiter import RateLimiter


class TestFileValidator:
    """Tests for FileValidator."""

    @pytest.mark.asyncio
    async def test_validate_valid_image(self, sample_image_bytes):
        """Test validation of valid image."""
        validator = FileValidator("receiving")

        file = UploadFile(
            filename="test.png",
            file=BytesIO(sample_image_bytes)
        )

        result = await validator.validate(file)

        assert result["is_valid"] is True
        assert result["mime_type"] == "image/png"
        assert result["file_size"] > 0

    @pytest.mark.asyncio
    async def test_validate_oversized_file(self, sample_image_bytes):
        """Test validation rejects oversized files."""
        validator = FileValidator("receiving")
        validator.max_file_size = 100  # Very small limit

        file = UploadFile(
            filename="test.png",
            file=BytesIO(sample_image_bytes)
        )

        result = await validator.validate(file)

        assert result["is_valid"] is False
        assert "file_too_large" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_invalid_mime_type(self):
        """Test validation rejects invalid MIME types."""
        validator = FileValidator("receiving")

        # Create a text file
        file = UploadFile(
            filename="test.txt",
            file=BytesIO(b"This is not an image")
        )

        result = await validator.validate(file)

        assert result["is_valid"] is False
        assert "invalid_mime_type" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_pdf(self, sample_pdf_bytes):
        """Test validation of PDF files."""
        validator = FileValidator("receiving")

        file = UploadFile(
            filename="test.pdf",
            file=BytesIO(sample_pdf_bytes)
        )

        result = await validator.validate(file)

        assert result["is_valid"] is True
        assert result["mime_type"] == "application/pdf"


class TestDeduplicator:
    """Tests for Deduplicator."""

    def test_calculate_hash(self, sample_image_bytes):
        """Test SHA256 hash calculation."""
        deduplicator = Deduplicator()

        hash1 = deduplicator.calculate_hash(sample_image_bytes)
        hash2 = deduplicator.calculate_hash(sample_image_bytes)

        # Same content should produce same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA256 hex string length

    def test_calculate_hash_different_content(self, sample_image_bytes):
        """Test different content produces different hash."""
        deduplicator = Deduplicator()

        hash1 = deduplicator.calculate_hash(sample_image_bytes)
        hash2 = deduplicator.calculate_hash(sample_image_bytes + b"extra")

        assert hash1 != hash2

    @pytest.mark.asyncio
    async def test_check_duplicate_not_exists(self, yacht_id, sample_image_bytes, mock_supabase):
        """Test duplicate check when file doesn't exist."""
        deduplicator = Deduplicator()
        deduplicator.supabase = mock_supabase

        # Mock no results
        mock_supabase.execute.return_value.data = []

        is_duplicate, existing = await deduplicator.check_duplicate(
            sample_image_bytes,
            yacht_id
        )

        assert is_duplicate is False
        assert existing is None

    @pytest.mark.asyncio
    async def test_check_duplicate_exists(self, yacht_id, sample_image_bytes, mock_supabase):
        """Test duplicate check when file exists."""
        deduplicator = Deduplicator()
        deduplicator.supabase = mock_supabase

        # Mock existing file
        existing_file = {
            "image_id": str(uuid4()),
            "file_name": "existing.png",
            "storage_path": "path/to/existing.png"
        }
        mock_supabase.execute.return_value.data = [existing_file]

        is_duplicate, existing = await deduplicator.check_duplicate(
            sample_image_bytes,
            yacht_id
        )

        assert is_duplicate is True
        assert existing == existing_file


class TestRateLimiter:
    """Tests for RateLimiter."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_under_limit(self, yacht_id, user_id, mock_supabase):
        """Test rate limit check when under limit."""
        limiter = RateLimiter()
        limiter.supabase = mock_supabase

        # Mock 10 recent uploads (under 50 limit)
        mock_supabase.execute.return_value.data = [{"count": 10}]

        is_limited, count, retry_after = await limiter.check_rate_limit(yacht_id, user_id)

        assert is_limited is False
        assert count == 10
        assert retry_after is None

    @pytest.mark.asyncio
    async def test_check_rate_limit_over_limit(self, yacht_id, user_id, mock_supabase):
        """Test rate limit check when over limit."""
        limiter = RateLimiter()
        limiter.supabase = mock_supabase

        # Mock 60 recent uploads (over 50 limit)
        mock_supabase.execute.return_value.data = [{"count": 60}]

        is_limited, count, retry_after = await limiter.check_rate_limit(yacht_id, user_id)

        assert is_limited is True
        assert count == 60
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_check_rate_limit_at_limit(self, yacht_id, user_id, mock_supabase):
        """Test rate limit check when exactly at limit."""
        limiter = RateLimiter()
        limiter.supabase = mock_supabase

        # Mock 50 recent uploads (exactly at limit)
        mock_supabase.execute.return_value.data = [{"count": 50}]

        is_limited, count, retry_after = await limiter.check_rate_limit(yacht_id, user_id)

        assert is_limited is True
        assert count == 50
