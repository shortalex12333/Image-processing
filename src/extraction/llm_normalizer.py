"""
LLM normalization for extracting structured data from messy OCR text.
Uses OpenAI API with cost-conscious token management.
"""

import json
from typing import Any

import openai
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings, calculate_llm_cost
from src.extraction.cost_controller import SessionCostTracker
from src.logger import get_logger

logger = get_logger(__name__)


class LLMNormalizer:
    """Normalizes OCR text using LLM."""

    def __init__(self, cost_tracker: SessionCostTracker):
        self.cost_tracker = cost_tracker
        self.client = openai.OpenAI(api_key=settings.openai_api_key)

    async def normalize(
        self,
        ocr_text: str,
        model: str = "gpt-4.1-mini",
        max_tokens: int = 2000,
        temperature: float = 0.1
    ) -> dict:
        """
        Extract structured line items from OCR text using LLM.

        Args:
            ocr_text: Raw OCR text
            model: Model to use (gpt-4.1-mini or gpt-4.1)
            max_tokens: Maximum output tokens
            temperature: Sampling temperature

        Returns:
            Normalization result with extracted lines

        Example:
            >>> normalizer = LLMNormalizer(cost_tracker)
            >>> result = await normalizer.normalize(ocr_text, model="gpt-4.1-mini")
            >>> result
            {
                "lines": [
                    {
                        "quantity": 12.0,
                        "unit": "ea",
                        "description": "MTU Oil Filter",
                        "part_number": "MTU-OF-4568"
                    }
                ],
                "extraction_notes": "Clean extraction, high confidence",
                "model": "gpt-4.1-mini",
                "tokens": {"input": 1523, "output": 847},
                "cost": 0.0478
            }
        """
        # Clean and truncate OCR text
        cleaned_text = self._clean_ocr_text(ocr_text)

        # Build prompt
        prompt = self._build_prompt(cleaned_text, model)

        try:
            # Call OpenAI API with retry logic
            response = await self._call_openai_with_retry(
                model=model,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )

            # Extract data from response
            result = self._parse_response(response, model)

            logger.info("LLM normalization complete", extra={
                "model": model,
                "lines_extracted": len(result.get("lines", [])),
                "tokens": result["tokens"],
                "cost": result["cost"]
            })

            return result

        except Exception as e:
            logger.error("LLM normalization failed", extra={
                "model": model,
                "error": str(e)
            }, exc_info=True)
            raise

    def _clean_ocr_text(self, text: str) -> str:
        """
        Clean OCR text before sending to LLM.

        Args:
            text: Raw OCR text

        Returns:
            Cleaned text
        """
        # Remove excessive whitespace
        import re
        text = re.sub(r'\s+', ' ', text)

        # Remove non-printable characters
        text = re.sub(r'[^\x20-\x7E\n]', '', text)

        # Remove repeated characters (OCR errors)
        text = re.sub(r'(.)\1{4,}', r'\1\1\1', text)

        # Truncate if too long (leave room for prompt)
        MAX_OCR_LENGTH = 8000  # ~2000 tokens
        if len(text) > MAX_OCR_LENGTH:
            logger.warning("OCR text truncated", extra={
                "original_length": len(text),
                "truncated_length": MAX_OCR_LENGTH
            })
            text = text[:6000] + "\n\n[...TRUNCATED...]\n\n" + text[-2000:]

        return text.strip()

    def _build_prompt(self, ocr_text: str, model: str) -> str:
        """
        Build prompt for LLM normalization.

        Args:
            ocr_text: Cleaned OCR text
            model: Model being used

        Returns:
            Prompt text
        """
        if model == "gpt-4.1-mini":
            # Concise prompt for mini model
            prompt = f"""Extract line items from this packing slip OCR text.

Required fields: quantity, unit, description
Optional: part_number

Return JSON: {{"lines": [...], "extraction_notes": "..."}}

OCR Text:
{ocr_text}"""

        else:  # gpt-4.1 escalation
            # More detailed prompt for hard cases
            prompt = f"""You are an expert at extracting data from damaged or poorly scanned documents.

OCR Text (may contain errors):
{ocr_text}

Task: Extract line items. Be aggressive - infer reasonable values when unclear.

Guidelines:
1. If quantity is "?" or unclear, estimate from context
2. If unit missing, infer from description
3. Combine split lines if obvious (OCR sometimes breaks items across lines)
4. Flag uncertain extractions with "confidence": "low"

Return JSON:
{{"lines": [{{"quantity": float, "unit": str, "description": str, "part_number": str|null, "confidence": "high|medium|low"}}], "extraction_notes": "Issues encountered"}}"""

        return prompt

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def _call_openai_with_retry(
        self,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Any:
        """
        Call OpenAI API with retry logic.

        Args:
            model: Model name
            prompt: Prompt text
            max_tokens: Max output tokens
            temperature: Sampling temperature

        Returns:
            OpenAI response object

        Raises:
            openai.RateLimitError: If rate limited after retries
            openai.APIError: If API error after retries
        """
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
                temperature=temperature,
                max_tokens=max_tokens
            )
            return response

        except openai.RateLimitError:
            logger.warning("OpenAI rate limit hit, retrying...")
            raise  # Retry
        except openai.APIError as e:
            logger.error("OpenAI API error", extra={"error": str(e)})
            raise  # Retry

    def _parse_response(self, response: Any, model: str) -> dict:
        """
        Parse OpenAI response and record cost.

        Args:
            response: OpenAI response object
            model: Model used

        Returns:
            Parsed result with lines, tokens, and cost
        """
        # Extract usage
        usage = response.usage
        input_tokens = usage.prompt_tokens
        output_tokens = usage.completion_tokens

        # Calculate cost
        cost = calculate_llm_cost(model, input_tokens, output_tokens)

        # Record in cost tracker
        self.cost_tracker.record_llm_call(model, input_tokens, output_tokens, cost)

        # Parse JSON response
        content = response.choices[0].message.content
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM JSON response", extra={
                "model": model,
                "content": content[:500],
                "error": str(e)
            })
            raise

        # Validate and normalize lines
        lines = data.get("lines", [])
        normalized_lines = []

        for i, line in enumerate(lines, start=1):
            normalized = self._normalize_line(line, i)
            if normalized:
                normalized_lines.append(normalized)

        return {
            "lines": normalized_lines,
            "extraction_notes": data.get("extraction_notes", ""),
            "model": model,
            "tokens": {
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens
            },
            "cost": cost,
            "method": "llm"
        }

    def _normalize_line(self, line: dict, line_number: int) -> dict | None:
        """
        Normalize and validate LLM-extracted line.

        Args:
            line: Raw line data from LLM
            line_number: Line number

        Returns:
            Normalized line or None if invalid
        """
        # Extract fields
        quantity = line.get("quantity")
        unit = line.get("unit")
        description = line.get("description")
        part_number = line.get("part_number")
        confidence = line.get("confidence", "medium")

        # Validate required fields
        if not quantity or not description:
            logger.warning("LLM line missing required fields", extra={
                "line_number": line_number,
                "line": line
            })
            return None

        # Convert quantity to float
        try:
            quantity = float(quantity)
            if quantity <= 0:
                return None
        except (ValueError, TypeError):
            logger.warning("Invalid quantity from LLM", extra={
                "line_number": line_number,
                "quantity": quantity
            })
            return None

        # Default unit if missing
        if not unit:
            unit = "ea"

        # Normalize unit
        unit = unit.lower()
        unit_map = {"each": "ea", "pieces": "pcs", "pc": "pcs"}
        unit = unit_map.get(unit, unit)

        # Clean description
        description = str(description).strip()
        if len(description) < 5 or len(description) > 500:
            return None

        # Clean part number
        if part_number:
            part_number = str(part_number).strip().upper()

        return {
            "line_number": line_number,
            "quantity": quantity,
            "unit": unit,
            "description": description,
            "part_number": part_number,
            "confidence": confidence,
            "extracted_by": "llm"
        }

    async def classify_upload_type(self, image_url: str) -> str:
        """
        Classify upload type using gpt-4.1-nano.

        Args:
            image_url: Signed URL to image

        Returns:
            Upload type: "packing_slip", "shipping_label", "discrepancy_photo", "part_photo"
        """
        prompt = """Analyze this image and classify it:
- packing_slip: Contains line items, quantities, part numbers
- shipping_label: Address, tracking number, barcode
- discrepancy_photo: Damaged goods, missing items
- part_photo: Close-up of a single part/equipment

Return only: {"type": "packing_slip|shipping_label|discrepancy_photo|part_photo"}"""

        try:
            response = self.client.chat.completions.create(
                model=settings.llm_classification_model,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]}],
                response_format={"type": "json_object"},
                max_tokens=50,
                temperature=0.0
            )

            content = response.choices[0].message.content
            data = json.loads(content)
            upload_type = data.get("type", "packing_slip")

            logger.info("Upload type classified", extra={
                "type": upload_type,
                "model": settings.llm_classification_model
            })

            return upload_type

        except Exception as e:
            logger.warning("Upload type classification failed", extra={"error": str(e)})
            return "packing_slip"  # Default

    async def extract_shipping_label_metadata(self, image_url: str) -> dict:
        """
        Extract metadata from shipping label using gpt-4.1-nano.

        Args:
            image_url: Signed URL to shipping label image

        Returns:
            Extracted metadata

        Example:
        {
            "carrier": "FedEx",
            "tracking_number": "1234567890",
            "recipient_name": "MY Excellence",
            "recipient_address": "123 Marina Bay...",
            "ship_date": "2026-01-08",
            "delivery_date": "2026-01-10",
            "service_type": "Express"
        }
        """
        prompt = """Extract metadata from this shipping label.

Fields to extract:
- carrier: FedEx, UPS, DHL, USPS, etc.
- tracking_number: Full tracking number
- recipient_name: Delivery recipient
- recipient_address: Full address
- ship_date: Shipping date (YYYY-MM-DD)
- delivery_date: Expected delivery (YYYY-MM-DD)
- service_type: Ground, Express, Priority, etc.

Return JSON only. Use null for missing fields.
{"carrier": "...", "tracking_number": "...", ...}"""

        try:
            response = self.client.chat.completions.create(
                model=settings.llm_classification_model,  # gpt-4.1-nano
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]}],
                response_format={"type": "json_object"},
                max_tokens=300,
                temperature=0.0
            )

            content = response.choices[0].message.content
            metadata = json.loads(content)

            logger.info("Shipping label metadata extracted", extra={
                "carrier": metadata.get("carrier"),
                "tracking": metadata.get("tracking_number")
            })

            return metadata

        except Exception as e:
            logger.error("Shipping label extraction failed", extra={"error": str(e)})
            return {}
