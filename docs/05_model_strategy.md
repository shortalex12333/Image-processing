# Model Strategy & Cost Control
## Image Processing Service - LLM Selection & Escalation Logic

**Version**: 1.0.0
**Last Updated**: 2026-01-09
**Owner**: Engineering

---

## Table of Contents

1. [Philosophy: Deterministic First, AI Second](#philosophy)
2. [Model Selection Matrix](#model-selection)
3. [Cost Structure & Budget](#cost-structure)
4. [Escalation Decision Logic](#escalation-logic)
5. [Token Budget Management](#token-management)
6. [Prompt Engineering Patterns](#prompt-patterns)
7. [Performance Metrics & Monitoring](#metrics)
8. [Failure Handling & Degradation](#failure-handling)

---

## Philosophy: Deterministic First, AI Second {#philosophy}

### Core Principle

**"Use the cheapest tool that works"**

```
Priority Order:
1. Deterministic (regex, heuristics, rules)      → $0.00
2. OCR (Tesseract self-hosted)                   → $0.00
3. gpt-4.1-nano (classification, routing)        → $0.0001-0.0005
4. gpt-4.1-mini (normalization, extraction)      → $0.02-0.10
5. gpt-4.1 (escalation for hard cases)           → $0.05-0.20
```

### Why This Matters

**Cost at scale:**
- 100 receiving sessions/month
- Average 3 images per session (300 images)
- If we use LLM for every image: **$300-600/month**
- With deterministic-first approach: **$30-120/month**

**Target distribution:**
- 70% solved by deterministic + OCR only ($0)
- 25% need gpt-4.1-mini ($0.02-0.10)
- 5% need gpt-4.1 escalation ($0.05-0.20)

**Result:** 80-90% cost reduction while maintaining quality

---

## Model Selection Matrix {#model-selection}

### When to Use Each Model

| Task | Model | Cost/Call | Why This Model | Fallback |
|------|-------|-----------|----------------|----------|
| **Classification** (upload type detection) | gpt-4.1-nano | $0.0001-0.0005 | Fast, cheap, high accuracy for simple routing | Rules-based heuristics |
| **Normalization** (OCR cleanup) | gpt-4.1-mini | $0.02-0.10 | Structured output, good for tabular data | Return raw OCR |
| **Extraction** (hard cases) | gpt-4.1 | $0.05-0.20 | Complex reasoning, handles edge cases | Mark as manual_review |
| **Metadata extraction** (shipping labels) | gpt-4.1-nano | $0.0001-0.0005 | Simple key-value extraction | Regex patterns |
| **Description generation** (part photos) | None | $0.00 | Not implemented in MVP | Future: gpt-4.1-mini |

---

## Section A: Receiving Workflow Models

### Task 1: Upload Type Classification

**Goal:** Determine if image is packing slip, shipping label, discrepancy photo, or part photo

**Deterministic first:**
```python
# File name heuristics
if "packing" in filename.lower() or "slip" in filename.lower():
    return "receiving"
if "label" in filename.lower() or "fedex" in filename.lower():
    return "shipping_label"
if "damage" in filename.lower() or "discrepancy" in filename.lower():
    return "discrepancy"
```

**LLM fallback (gpt-4.1-nano):**
```python
if upload_type == "unknown":
    prompt = """Analyze this image and classify it:
    - packing_slip: Contains line items, quantities, part numbers
    - shipping_label: Address, tracking number, barcode
    - discrepancy_photo: Damaged goods, missing items
    - part_photo: Close-up of a single part/equipment

    Return only: {"type": "packing_slip|shipping_label|discrepancy_photo|part_photo"}"""

    response = openai.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_url}}
        ]}],
        max_tokens=50  # Only need classification
    )
```

**Cost:** $0.0001-0.0005 per image
**Invocation rate:** 10-20% (most obvious from filename/user selection)

---

### Task 2: OCR Text Extraction

**Goal:** Extract text from packing slip/shipping label

**Primary: Tesseract OCR (self-hosted)**
```python
# NO LLM - Use Tesseract
preprocessed = preprocess_image(image)  # Deskew, binarize, contrast
ocr_result = pytesseract.image_to_data(preprocessed, output_type=Output.DICT)

# Extract text + bounding boxes
text = " ".join(ocr_result['text'])
confidence = calculate_average_confidence(ocr_result)
```

**Cost:** $0.00 (self-hosted)
**Fallback:** Google Vision API ($0.001-0.003/image) if Tesseract confidence < 60%

**When NOT to use LLM for OCR:**
- ❌ Don't use GPT-4V/Claude for raw text extraction (expensive, overkill)
- ✓ Use LLM AFTER OCR for structure normalization only

---

### Task 3: Structure Detection (Table Parsing)

**Goal:** Identify rows in packing slip, extract columns

**Deterministic first (regex + heuristics):**
```python
# Pattern matching for common formats
patterns = [
    # Format 1: Qty | Unit | Description | Part#
    r'(\d+\.?\d*)\s+(ea|box|case)\s+([A-Za-z0-9\s,]+)\s+([A-Z0-9-]+)',

    # Format 2: Part# - Description (Qty)
    r'([A-Z0-9-]+)\s*-\s*([A-Za-z0-9\s,]+)\s*\((\d+\.?\d*)\s*(ea|box)\)',

    # Format 3: Tabular with OCR bounding boxes
    # Use x-coordinate alignment to detect columns
]

lines_extracted = []
for line in ocr_text.split('\n'):
    for pattern in patterns:
        match = re.match(pattern, line)
        if match:
            lines_extracted.append({
                "quantity": match.group(1),
                "unit": match.group(2),
                "description": match.group(3),
                "part_number": match.group(4)
            })
```

**Coverage calculation:**
```python
coverage = len(lines_extracted) / total_text_lines
if coverage >= 0.8:
    # SUCCESS - No LLM needed
    return lines_extracted
```

**Cost:** $0.00
**Success rate:** 60-70% for clean PDFs, 40-50% for images

---

### Task 4: LLM Normalization (Conditional)

**Goal:** Extract structured data from messy OCR text

**Trigger conditions:**
```python
needs_llm = (
    coverage < 0.8 OR
    table_confidence < 0.7 OR
    user_flag_manual_review
)
```

**Model:** gpt-4.1-mini

**Why gpt-4.1-mini:**
- Structured output via JSON mode
- Good at normalization tasks
- 10x cheaper than gpt-4.1
- Sufficient reasoning for tabular data

**Prompt pattern:**
```python
prompt = f"""You are normalizing OCR text from a packing slip into structured JSON.

OCR Text:
{ocr_text}

Task: Extract line items with these fields:
- quantity (number, required)
- unit (ea, box, case, pcs, lbs, kg, g, ft, m, gal, L)
- description (string, required)
- part_number (string, optional)

Rules:
1. One object per line item
2. Ignore headers, footers, totals
3. If quantity unclear, use null
4. Preserve original description exactly
5. Return empty array if no line items found

Return JSON only:
{{"lines": [...]}}
"""

response = openai.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"},
    temperature=0.1,  # Low temperature for consistency
    max_tokens=2000   # Typical packing slip ~100-200 lines
)
```

**Cost:** $0.02-0.10 per image (depends on OCR text length)
**Invocation rate target:** < 30% of images

---

### Task 5: LLM Escalation (Hard Cases)

**Goal:** Handle cases where gpt-4.1-mini fails or low confidence

**Trigger conditions:**
```python
needs_escalation = (
    llm_attempt_1_failed OR
    llm_confidence < 0.6 OR
    llm_returned_empty AND ocr_confidence > 0.7  # LLM gave up but OCR saw text
)
```

**Model:** gpt-4.1

**Why gpt-4.1:**
- More powerful reasoning for ambiguous cases
- Better at handling damaged/poor quality OCR
- Last resort before marking as manual_review

**Prompt pattern (enhanced):**
```python
prompt = f"""You are an expert at extracting data from damaged or poorly scanned documents.

OCR Text (may contain errors):
{ocr_text}

Context:
- Document type: Packing slip / receiving note
- Previous extraction attempts failed
- OCR confidence: {ocr_confidence}
- Known issues: {detected_issues}  # e.g., "vertical text", "water damage", "faded"

Task: Extract line items. Be aggressive - infer reasonable values when unclear.

Guidelines:
1. If quantity is "?" or unclear, estimate from context (e.g., "box of filters" → 1 box)
2. If unit missing, infer from description (e.g., "5 filters" → 5 ea)
3. Combine split lines if obvious (OCR sometimes breaks one item across multiple lines)
4. Flag uncertain extractions with "confidence": "low"

Return JSON:
{{"lines": [...], "extraction_notes": "Issues encountered"}}
"""

response = openai.chat.completions.create(
    model="gpt-4.1",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"},
    temperature=0.2,  # Slightly higher for creative problem-solving
    max_tokens=3000
)
```

**Cost:** $0.05-0.20 per image
**Invocation rate target:** < 5% of images
**Hard cap:** 1 escalation per session

---

## Section B: Shipping Label Metadata Extraction

### Task: Extract Carrier, Tracking, Address

**Model:** gpt-4.1-nano (cheap, sufficient for key-value extraction)

**Prompt pattern:**
```python
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
{"carrier": "...", "tracking_number": "...", ...}
"""

response = openai.chat.completions.create(
    model="gpt-4.1-nano",
    messages=[{"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": label_image_url}}
    ]}],
    response_format={"type": "json_object"},
    max_tokens=300
)
```

**Cost:** $0.0001-0.0005 per label
**Invocation rate:** 100% (no deterministic alternative for carrier label formats)

**Why not gpt-4.1-mini:**
- Shipping labels have standard formats
- Key-value extraction is simple task
- gpt-4.1-nano sufficient accuracy (95%+)
- 100x cost reduction vs gpt-4.1-mini

---

## Section C & D: Discrepancy/Part Photos

**No LLM in MVP**

These are pure attachment features:
1. Validate image (not blurry, appropriate content)
2. Store in appropriate bucket
3. Link to entity (fault, work order, part)

**Future enhancement (post-MVP):**
- gpt-4.1-mini for damage assessment ("light scratches", "severe dent", "box crushed")
- gpt-4.1-mini for part photo tagging ("MTU oil filter", "stainless bolt", "gasket")

---

## Section E: Label Generation

**No LLM** - Purely deterministic:
1. Query committed receiving event
2. Generate QR code (Python `qrcode` library)
3. Layout PDF with ReportLab
4. Return PDF

**Cost:** $0.00

---

## Cost Structure & Budget {#cost-structure}

### Per-Image Cost Breakdown

| Pipeline Stage | Model | Typical Cost | Max Cost | Frequency |
|----------------|-------|--------------|----------|-----------|
| Classification | gpt-4.1-nano | $0.0003 | $0.001 | 10-20% |
| OCR | Tesseract | $0.00 | $0.003* | 100% |
| Structure detection | Deterministic | $0.00 | $0.00 | 100% |
| Normalization | gpt-4.1-mini | $0.05 | $0.15 | 20-30% |
| Escalation | gpt-4.1 | $0.10 | $0.30 | < 5% |

*Google Vision fallback if Tesseract fails

### Per-Session Cost Estimates

**Session = 1-5 images for a single receiving event**

**Best case (clean PDF packing slip):**
- OCR: $0.00 (Tesseract)
- Structure detection: $0.00 (regex success)
- **Total: $0.00**

**Average case (typical image packing slip):**
- OCR: $0.00 (Tesseract)
- Structure detection: $0.00 (regex partial)
- LLM normalization (gpt-4.1-mini): $0.05
- **Total: $0.05**

**Worst case (poor quality, escalation):**
- OCR: $0.003 (Google Vision fallback)
- Structure detection: $0.00
- LLM normalization (gpt-4.1-mini): $0.10
- LLM escalation (gpt-4.1): $0.15
- **Total: $0.253**

**Hard cap per session: $0.50** (enforced in code)

### Monthly Cost Projections

**Scenario 1: Small yacht (50 sessions/month)**
- 70% best case: 35 × $0.00 = $0
- 25% average: 12 × $0.05 = $0.60
- 5% worst: 3 × $0.25 = $0.75
- **Total: $1.35/month**

**Scenario 2: Medium yacht (100 sessions/month)**
- 70% best case: 70 × $0.00 = $0
- 25% average: 25 × $0.05 = $1.25
- 5% worst: 5 × $0.25 = $1.25
- **Total: $2.50/month**

**Scenario 3: Large yacht (200 sessions/month)**
- 70% best case: 140 × $0.00 = $0
- 25% average: 50 × $0.05 = $2.50
- 5% worst: 10 × $0.25 = $2.50
- **Total: $5.00/month**

**Cost efficiency:** $0.01-0.05 per receiving session vs manual data entry (30min × $25/hr = $12.50)

---

## Escalation Decision Logic {#escalation-logic}

### Decision Tree

```python
class CostController:
    def decide_next_action(self, session_state):
        """Determine if we should escalate to LLM or return current results"""

        # Stage 1: Check deterministic success
        if session_state.coverage >= 0.8 and session_state.table_confidence >= 0.8:
            return Decision(action="return_results", reason="deterministic_success")

        # Stage 2: Check LLM budget
        if session_state.llm_calls >= MAX_LLM_CALLS_PER_SESSION:
            return Decision(
                action="return_partial",
                reason="llm_budget_exceeded",
                manual_review_required=True
            )

        if session_state.total_cost >= MAX_COST_PER_SESSION:
            return Decision(
                action="return_partial",
                reason="cost_budget_exceeded",
                manual_review_required=True
            )

        # Stage 3: Decide normalization vs escalation
        if session_state.llm_attempts == 0:
            # First attempt - use gpt-4.1-mini
            return Decision(
                action="invoke_llm",
                model="gpt-4.1-mini",
                reason="low_coverage",
                max_tokens=2000,
                temperature=0.1
            )

        elif session_state.llm_attempts == 1 and session_state.last_llm_confidence < 0.6:
            # Second attempt - escalate to gpt-4.1
            return Decision(
                action="invoke_llm",
                model="gpt-4.1",
                reason="escalation_low_confidence",
                max_tokens=3000,
                temperature=0.2
            )

        else:
            # Give up - return what we have
            return Decision(
                action="return_partial",
                reason="max_attempts_reached",
                manual_review_required=True
            )
```

### Budget Enforcement

```python
# Global limits (per session)
MAX_LLM_CALLS_PER_SESSION = 3
MAX_COST_PER_SESSION = 0.50  # USD
MAX_TOKEN_BUDGET_PER_SESSION = 10000

# Per-image limits
MAX_LLM_CALLS_PER_IMAGE = 2  # mini + escalation
MAX_COST_PER_IMAGE = 0.30

# Tracking
class SessionCostTracker:
    def __init__(self, session_id):
        self.session_id = session_id
        self.llm_calls = 0
        self.total_tokens = 0
        self.total_cost = 0.0
        self.model_usage = {}  # {model: {calls, tokens, cost}}

    def record_llm_call(self, model, input_tokens, output_tokens, cost):
        self.llm_calls += 1
        self.total_tokens += input_tokens + output_tokens
        self.total_cost += cost

        if model not in self.model_usage:
            self.model_usage[model] = {"calls": 0, "tokens": 0, "cost": 0.0}

        self.model_usage[model]["calls"] += 1
        self.model_usage[model]["tokens"] += input_tokens + output_tokens
        self.model_usage[model]["cost"] += cost

        # Log metrics
        logger.info("LLM call recorded", extra={
            "session_id": self.session_id,
            "model": model,
            "tokens": input_tokens + output_tokens,
            "cost": cost,
            "total_cost": self.total_cost
        })

        # Alert if approaching limits
        if self.total_cost > 0.4:  # 80% of $0.50 cap
            logger.warning("Session approaching cost cap", extra={
                "session_id": self.session_id,
                "total_cost": self.total_cost,
                "cap": MAX_COST_PER_SESSION
            })
```

---

## Token Budget Management {#token-management}

### Token Estimation

**OCR text length → Token count:**
```python
# Rule of thumb: ~4 characters per token for English
estimated_tokens = len(ocr_text) / 4

# More accurate: Use tiktoken library
import tiktoken
encoder = tiktoken.encoding_for_model("gpt-4")
actual_tokens = len(encoder.encode(ocr_text))
```

**Typical packing slip:**
- OCR text: 2,000-5,000 characters
- Tokens: 500-1,250 input tokens
- Prompt overhead: ~200 tokens
- Output: ~500-1,000 tokens (JSON array)
- **Total: ~1,200-2,450 tokens per call**

### Token Optimization Strategies

**1. Truncate OCR text if too long**
```python
MAX_OCR_TEXT_LENGTH = 8000  # characters (~2000 tokens)

if len(ocr_text) > MAX_OCR_TEXT_LENGTH:
    # Intelligent truncation - keep beginning and end
    truncated = ocr_text[:6000] + "\n\n[...TRUNCATED...]\n\n" + ocr_text[-2000:]
    logger.warning("OCR text truncated", extra={
        "original_length": len(ocr_text),
        "truncated_length": len(truncated)
    })
else:
    truncated = ocr_text
```

**2. Remove non-essential OCR artifacts**
```python
# Clean OCR text before sending to LLM
def clean_ocr_text(text):
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)

    # Remove common OCR artifacts
    text = re.sub(r'[^\x20-\x7E\n]', '', text)  # Non-printable chars

    # Remove repeated characters (OCR errors)
    text = re.sub(r'(.)\1{4,}', r'\1\1\1', text)

    return text.strip()
```

**3. Use focused prompts**
```python
# ❌ BAD - Verbose prompt wastes tokens
prompt = """You are a helpful AI assistant specialized in extracting structured data from documents. Your task is to carefully analyze the following text, which was extracted from a packing slip using OCR technology. Please extract all line items that represent products or parts being received. For each line item, you should extract the following information if available: quantity (the number of units), unit of measurement (such as each, box, case, etc.), a description of the item, and optionally the part number if one is present. Please return your response in JSON format..."""

# ✓ GOOD - Concise, direct
prompt = """Extract line items from this packing slip OCR text.

Required fields: quantity, unit, description
Optional: part_number

Return JSON: {"lines": [...]}"""
```

**4. Cap max_tokens on output**
```python
# Estimate output tokens needed
estimated_lines = len(ocr_text.split('\n')) / 2  # ~2 lines per item
estimated_output_tokens = estimated_lines * 50  # ~50 tokens per JSON object

max_tokens = min(
    int(estimated_output_tokens * 1.5),  # 50% buffer
    3000  # Hard cap
)
```

### Cost Calculation

**Model pricing (as of 2026-01-09):**
```python
PRICING = {
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

def calculate_cost(model, input_tokens, output_tokens):
    pricing = PRICING[model]
    input_cost = input_tokens * pricing["input"]
    output_cost = output_tokens * pricing["output"]
    return input_cost + output_cost

# Example:
# gpt-4.1-mini with 1500 input, 800 output
cost = calculate_cost("gpt-4.1-mini", 1500, 800)
# = (1500 * 0.000015) + (800 * 0.000030)
# = 0.0225 + 0.024 = $0.0465
```

---

## Prompt Engineering Patterns {#prompt-patterns}

### Pattern 1: Structured Output (JSON Mode)

**Always use JSON mode for structured extraction**

```python
response = openai.chat.completions.create(
    model="gpt-4.1-mini",
    messages=[{"role": "user", "content": prompt}],
    response_format={"type": "json_object"},  # ← CRITICAL
    temperature=0.1
)
```

**Why:**
- Guarantees valid JSON (no parsing errors)
- More consistent output format
- Slightly cheaper (model doesn't generate markdown formatting)

**JSON schema in prompt:**
```python
prompt = f"""Extract data and return this exact JSON structure:

{{
  "lines": [
    {{
      "line_number": 1,
      "quantity": 12.0,
      "unit": "ea",
      "description": "MTU Oil Filter",
      "part_number": "MTU-OF-4568",
      "confidence": "high"
    }}
  ],
  "extraction_notes": "Any issues encountered"
}}

OCR Text:
{ocr_text}
"""
```

---

### Pattern 2: Few-Shot Examples

**For ambiguous formats, provide 2-3 examples**

```python
prompt = f"""Extract line items from packing slip OCR text.

Example Input:
"12 ea MTU Oil Filter (MTU-OF-4568)
5 box Air Filter Elements - Part# MTU-AF-4567"

Example Output:
{{
  "lines": [
    {{"quantity": 12.0, "unit": "ea", "description": "MTU Oil Filter", "part_number": "MTU-OF-4568"}},
    {{"quantity": 5.0, "unit": "box", "description": "Air Filter Elements", "part_number": "MTU-AF-4567"}}
  ]
}}

Now extract from this OCR text:
{ocr_text}
"""
```

**Trade-off:**
- ✓ Improves accuracy by 10-15%
- ✗ Adds ~100-200 tokens to every request
- **Use when:** Format is ambiguous or failure rate > 20%
- **Skip when:** Format is standard and success rate > 90%

---

### Pattern 3: Chain-of-Thought (Escalation Only)

**For gpt-4.1 escalation, allow reasoning**

```python
prompt = f"""Extract line items from this damaged/poor quality OCR text.

Think step-by-step:
1. Identify where line items start/end (look for patterns)
2. For each line, extract quantity, unit, description
3. If values unclear, use context to infer reasonable values
4. Flag uncertain extractions

OCR Text:
{ocr_text}

Return JSON:
{{
  "reasoning": "Step-by-step analysis...",
  "lines": [...],
  "extraction_notes": "Issues encountered"
}}
"""
```

**Why only for escalation:**
- Chain-of-thought adds ~200-500 tokens to output
- gpt-4.1-mini doesn't benefit much from CoT (over-engineered)
- gpt-4.1 uses reasoning to solve hard cases where mini failed

---

### Pattern 4: Temperature Settings

```python
# Classification tasks (discrete choices)
temperature=0.0  # Deterministic, same result every time

# Normalization tasks (structured extraction)
temperature=0.1  # Mostly deterministic, slight variation OK

# Escalation tasks (creative problem-solving)
temperature=0.2  # Allow more exploration for hard cases

# ❌ NEVER use temperature > 0.3 for production extraction
# High temperature = inconsistent results, hallucinations
```

---

### Pattern 5: Confidence Scoring

**Ask model to self-assess**

```python
prompt = f"""Extract line items. For each item, assess confidence:
- "high": Clear quantity, unit, description
- "medium": Some ambiguity but reasonable inference
- "low": Guessing or unclear

Return JSON with confidence field:
{{"lines": [{{"...fields...", "confidence": "high|medium|low"}}]}}

OCR Text:
{ocr_text}
"""
```

**Use confidence scores to:**
- Decide if escalation needed (< 60% average confidence → escalate)
- Flag items for manual review (low confidence items highlighted in UI)
- Track model accuracy over time

---

## Performance Metrics & Monitoring {#metrics}

### Key Metrics to Track

**1. LLM Invocation Rate**
```python
llm_invocation_rate = (sessions_with_llm_calls / total_sessions) * 100
# Target: < 30%
```

**2. Cost Per Session**
```python
avg_cost_per_session = total_llm_cost / total_sessions
# Target: < $0.10
```

**3. Model Distribution**
```python
model_usage = {
    "gpt-4.1-nano": nano_calls / total_llm_calls,
    "gpt-4.1-mini": mini_calls / total_llm_calls,
    "gpt-4.1": gpt4_calls / total_llm_calls
}
# Target: 10% nano, 25% mini, 5% gpt-4.1 (30% total)
```

**4. Manual Review Rate**
```python
manual_review_rate = (sessions_flagged_manual / total_sessions) * 100
# Target: < 10%
```

**5. Extraction Accuracy**
```python
# Measured against user corrections
accuracy = (correct_extractions / total_extractions) * 100
# Target: > 95%
```

### Logging

**Log every LLM call:**
```python
logger.info("LLM call", extra={
    "session_id": session_id,
    "image_id": image_id,
    "model": "gpt-4.1-mini",
    "input_tokens": 1523,
    "output_tokens": 847,
    "cost": 0.0478,
    "latency_ms": 3421,
    "coverage_before": 0.65,
    "coverage_after": 0.92,
    "reason": "low_coverage"
})
```

**Track escalations:**
```python
logger.warning("LLM escalation", extra={
    "session_id": session_id,
    "from_model": "gpt-4.1-mini",
    "to_model": "gpt-4.1",
    "reason": "low_confidence",
    "mini_confidence": 0.52,
    "cost_before": 0.05,
    "cost_after": 0.18
})
```

**Alert on budget exceeded:**
```python
if total_cost > MAX_COST_PER_SESSION:
    logger.error("Session cost cap exceeded", extra={
        "session_id": session_id,
        "total_cost": total_cost,
        "cap": MAX_COST_PER_SESSION,
        "llm_calls": llm_calls,
        "models_used": list(model_usage.keys())
    })
```

### Dashboards (Future)

**Cost dashboard:**
- Daily/weekly/monthly LLM spend
- Cost per session trend
- Model distribution pie chart
- Most expensive sessions (outliers)

**Performance dashboard:**
- LLM invocation rate
- Extraction accuracy
- Manual review rate
- OCR success rate (Tesseract vs fallback)

---

## Failure Handling & Degradation {#failure-handling}

### OpenAI API Failure

**Retry logic:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def call_openai_with_retry(model, messages, **kwargs):
    try:
        response = openai.chat.completions.create(
            model=model,
            messages=messages,
            **kwargs
        )
        return response
    except openai.RateLimitError:
        logger.warning("OpenAI rate limit hit, retrying...")
        raise  # Retry
    except openai.APIError as e:
        logger.error("OpenAI API error", extra={"error": str(e)})
        raise  # Retry
```

**Graceful degradation:**
```python
try:
    llm_result = call_openai_with_retry(model, messages)
except Exception as e:
    logger.error("LLM call failed after retries", extra={
        "session_id": session_id,
        "model": model,
        "error": str(e)
    })

    # Degrade to partial results
    return {
        "status": "partial_success",
        "lines": deterministic_lines,  # Return what we have
        "manual_review_required": True,
        "error": "LLM service unavailable"
    }
```

---

### Rate Limiting

**OpenAI rate limits (typical):**
- gpt-4.1-mini: 10,000 requests/min, 2M tokens/min
- gpt-4.1: 500 requests/min, 300K tokens/min

**Our limits:**
- 50 uploads per hour per yacht
- Max 3 LLM calls per session
- Max 100 concurrent sessions processing

**Rate limit handling:**
```python
if response.status_code == 429:  # Too Many Requests
    retry_after = int(response.headers.get("Retry-After", 60))
    logger.warning("Rate limited by OpenAI", extra={
        "retry_after": retry_after,
        "model": model
    })
    time.sleep(retry_after)
    # Retry
```

---

### Model Deprecation

**Plan for model updates:**
```python
# Environment variable for model selection
NORMALIZATION_MODEL = os.getenv("LLM_NORMALIZATION_MODEL", "gpt-4.1-mini")
ESCALATION_MODEL = os.getenv("LLM_ESCALATION_MODEL", "gpt-4.1")
CLASSIFICATION_MODEL = os.getenv("LLM_CLASSIFICATION_MODEL", "gpt-4.1-nano")

# Easy migration if OpenAI deprecates models
# Just update env var: LLM_NORMALIZATION_MODEL=gpt-4o-mini
```

**Test suite with real data:**
- Maintain 50+ sample packing slips (various formats)
- Run regression tests when switching models
- Measure accuracy delta before production switch

---

## Summary: Model Strategy Checklist

### ✓ Design Principles
- [x] Deterministic first, AI second
- [x] Use cheapest model that works
- [x] Hard budget caps enforced in code
- [x] Graceful degradation on failure

### ✓ Model Selection
- [x] gpt-4.1-nano for classification & metadata ($0.0001-0.0005)
- [x] Tesseract OCR for text extraction ($0.00)
- [x] gpt-4.1-mini for normalization ($0.02-0.10)
- [x] gpt-4.1 for escalation only ($0.05-0.20)

### ✓ Cost Control
- [x] Target: 70% sessions use $0 LLM
- [x] Average cost: $0.05 per session
- [x] Hard cap: $0.50 per session
- [x] Per-image cap: $0.30

### ✓ Quality Assurance
- [x] JSON mode for structured output
- [x] Confidence scoring for auto-flagging
- [x] Manual review fallback
- [x] Retry logic for API failures

### ✓ Monitoring
- [x] Log every LLM call (cost, tokens, latency)
- [x] Track invocation rate (target < 30%)
- [x] Alert on budget exceeded
- [x] Measure accuracy vs user corrections

---

**Next:** [Section 06: Abuse Protection](./06_abuse_protection.md)
**Previous:** [Section 04: API Contracts](./04_api_contracts.md)

---

**Document Status**: ✅ Complete
**Review Status**: Pending stakeholder review
**Implementation Status**: Design phase
