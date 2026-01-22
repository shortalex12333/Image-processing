"""
OCR Factory - creates appropriate OCR engine based on configuration.

This factory allows swapping OCR engines without code changes.
Just update the OCR_ENGINE environment variable.

Supported engines:
- paddleocr: Local (free, 94% accuracy, 9s) - RECOMMENDED for packing slips
- google_vision: Cloud API ($1.50/1000 images, 80% accuracy, 400ms)
- surya: Self-hosted (free, 91% accuracy, 30s, requires 4GB RAM)
- tesseract: Local (free, 31% accuracy, 1s, low quality) - NOT RECOMMENDED

Usage:
    from src.ocr.ocr_factory import OCRFactory

    ocr = OCRFactory.get_ocr_engine()
    result = await ocr.extract_text(image_bytes)
    print(f"Used {result.engine_used} with {result.confidence:.1%} confidence")
"""

from typing import Optional
from src.ocr.base_ocr import BaseOCR
from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)


class OCRFactory:
    """
    Factory to create appropriate OCR engine based on feature flags.

    Uses singleton pattern to avoid reloading heavy models (Surya = 1.34GB).

    Auto-selects best available OCR engine based on enabled flags in config:
        - enable_paddleocr: 94% accuracy, free, needs 2GB RAM (Standard plan)
        - enable_google_vision: 80% accuracy, $1.50/1000, needs 512MB RAM (Starter plan)
        - enable_surya: 91% accuracy, free, needs 4GB RAM (Pro plan)
        - enable_tesseract: 31% accuracy, free, needs 512MB RAM (fallback)

    Toggle flags in .env based on your Render plan tier.
    """

    _instance: Optional[BaseOCR] = None

    @classmethod
    def get_ocr_engine(cls) -> BaseOCR:
        """
        Get best available OCR engine based on enabled feature flags.

        Selection priority (best to worst):
        1. PaddleOCR (if enabled) - Best accuracy for packing slips
        2. Surya (if enabled) - High accuracy, very slow
        3. Google Vision (if enabled) - Good accuracy, costs money
        4. AWS Textract (if enabled) - Good accuracy, costs money
        5. Tesseract (if enabled) - Poor accuracy, always free

        Returns:
            BaseOCR instance

        Raises:
            Exception: If no OCR engines are enabled or all fail to initialize
        """
        if cls._instance is None:
            cls._instance = cls._select_best_available_engine()

            logger.info(
                f"OCR engine initialized: {cls._instance.get_engine_name()}"
            )

        return cls._instance

    @classmethod
    def _select_best_available_engine(cls) -> BaseOCR:
        """
        Select and create the best available OCR engine based on feature flags.

        Returns:
            BaseOCR instance

        Raises:
            Exception: If no engines are enabled or all fail
        """
        # Try engines in priority order (best to worst)
        engines_to_try = [
            ("paddleocr", settings.enable_paddleocr, cls._create_paddleocr),
            ("surya", settings.enable_surya, cls._create_surya),
            ("google_vision", settings.enable_google_vision, cls._create_google_vision),
            ("aws_textract", settings.enable_aws_textract, cls._create_aws_textract),
            ("tesseract", settings.enable_tesseract, cls._create_tesseract),
        ]

        errors = []
        for engine_name, is_enabled, create_func in engines_to_try:
            if not is_enabled:
                logger.debug(f"OCR engine '{engine_name}' is disabled (feature flag)")
                continue

            try:
                logger.info(f"Attempting to initialize OCR engine: {engine_name}")
                engine = create_func()
                logger.info(f"✅ Successfully initialized: {engine_name}")
                return engine
            except Exception as e:
                error_msg = f"{engine_name}: {str(e)}"
                errors.append(error_msg)
                logger.warning(f"Failed to initialize {engine_name}: {e}")
                continue

        # If we get here, no engines worked
        raise Exception(
            f"No OCR engines available. Enable at least one engine in config. "
            f"Tried: {', '.join(errors)}"
        )

    @classmethod
    def _create_paddleocr(cls) -> BaseOCR:
        """
        Create PaddleOCR instance (RECOMMENDED).

        Advantages:
        - 94% accuracy on real packing slips
        - Handles complex table layouts
        - Free and open source
        - Lightweight (<10MB)

        Trade-offs:
        - Slower (9s vs 1s for Tesseract)
        - But accuracy is 3X better

        Returns:
            PaddleOCR_Engine instance

        Raises:
            Exception: If PaddleOCR not installed
        """
        from src.ocr.paddleocr_ocr import PaddleOCR_Engine
        return PaddleOCR_Engine()

    @classmethod
    def _create_google_vision(cls) -> BaseOCR:
        """
        Create Google Vision OCR instance.

        Raises:
            Exception: If API key not configured
        """
        from src.ocr.google_vision_ocr import GoogleVisionOCR

        if not settings.google_vision_api_key:
            raise Exception(
                "GOOGLE_VISION_API_KEY not configured. "
                "Set it in .env or switch to OCR_ENGINE=tesseract"
            )

        return GoogleVisionOCR()

    @classmethod
    def _create_surya(cls) -> BaseOCR:
        """
        Create Surya OCR instance.

        Raises:
            Exception: If Surya not installed or insufficient RAM
        """
        from src.ocr.surya_ocr import SuryaOCR

        # Check if we have enough RAM (Surya needs 4GB minimum)
        import psutil
        available_ram_gb = psutil.virtual_memory().available / (1024 ** 3)

        if available_ram_gb < 3.5:
            logger.warning(
                f"Low RAM detected ({available_ram_gb:.1f}GB available). "
                "Surya requires 4GB minimum. May crash!"
            )

        return SuryaOCR()

    @classmethod
    def _create_tesseract(cls) -> BaseOCR:
        """
        Create Tesseract OCR instance (fallback).

        Returns:
            TesseractOCR instance
        """
        from src.ocr.tesseract_ocr import TesseractOCR
        return TesseractOCR()

    @classmethod
    def _create_aws_textract(cls) -> BaseOCR:
        """
        Create AWS Textract OCR instance.

        Raises:
            Exception: If AWS credentials not configured
        """
        if not settings.aws_access_key_id or not settings.aws_secret_access_key:
            raise Exception(
                "AWS credentials not configured. "
                "Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env"
            )

        raise NotImplementedError(
            "AWS Textract OCR not yet implemented. "
            "Use enable_google_vision=true or enable_tesseract=true instead."
        )

    @classmethod
    def reset(cls):
        """
        Reset singleton (useful for testing or switching engines at runtime).

        Example:
            OCRFactory.reset()
            settings.ocr_engine = "surya"
            ocr = OCRFactory.get_ocr_engine()  # Now uses Surya
        """
        cls._instance = None
        logger.info("OCR engine factory reset")

    @classmethod
    async def health_check_all_engines(cls) -> dict:
        """
        Check health of all available OCR engines.

        Returns:
            Dict with engine names as keys, health status as values

        Example:
            {
                "google_vision": True,
                "surya": False,
                "tesseract": True
            }
        """
        from src.ocr.google_vision_ocr import GoogleVisionOCR
        from src.ocr.tesseract_ocr import TesseractOCR

        health = {}

        # Check Google Vision
        try:
            if settings.google_vision_api_key:
                gv = GoogleVisionOCR()
                health["google_vision"] = await gv.health_check()
            else:
                health["google_vision"] = False  # Not configured
        except:
            health["google_vision"] = False

        # Check Surya (only if installed)
        try:
            from src.ocr.surya_ocr import SuryaOCR
            surya = SuryaOCR()
            health["surya"] = await surya.health_check()
        except:
            health["surya"] = False  # Not installed or failed to load

        # Check Tesseract
        try:
            tess = TesseractOCR()
            health["tesseract"] = await tess.health_check()
        except:
            health["tesseract"] = False

        return health
