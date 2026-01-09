# Image Processing Service
## Cloud_PMS - Receiving & Image Workflow Backend

**Version**: 1.0.0
**Status**: Development
**Deployment**: Render.com (Python/Docker)
**Database**: Supabase PostgreSQL
**Repository**: https://github.com/shortalex12333/Image-processing

---

## Overview

Backend microservice for processing images in the Cloud_PMS receiving workflow:

- **Packing slips** → Structured draft lines for verification
- **Shipping labels** → Metadata extraction & order matching
- **Discrepancy photos** → Damage/missing evidence
- **Part photos** → Inventory catalog images
- **Label PDFs** → QR code generation

### Key Principles

1. **Precision > Speed** - No guessing. Deterministic first, LLM only when needed.
2. **Checkbox = Truth** - Draft lines never become inventory without explicit verification.
3. **Cost Matters** - Cheap deterministic first, escalate only when necessary.
4. **Security Last** - Abuse protection and security as final milestone (not half-done early).

---

## Architecture

### Five Separate Pipelines

```
Section A: Receiving (packing slips)
    Input: PDF/Image packing slip
    Output: Draft lines for verification
    Cost: $0.03-0.15 per session

Section B: Shipping Label
    Input: Label image/PDF
    Output: Metadata + order match
    Cost: $0.02-0.04 per image

Section C: Discrepancy Photos
    Input: Photo of damage/missing
    Output: Photo attachment
    Cost: $0.00 (no processing)

Section D: Part Photos
    Input: Part image
    Output: Catalog attachment
    Cost: $0.00 (no processing)

Section E: Label Generation
    Input: Committed receiving data
    Output: QR code PDF labels
    Cost: $0.00 (generation only)
```

### Technology Stack

**Backend**:
- FastAPI 0.115.0 (Python web framework)
- Uvicorn (ASGI server)
- Pydantic 2.10.3 (validation)
- Supabase 2.12.0 (database client)

**Image Processing**:
- OpenCV (`opencv-python`) - Preprocessing
- Pillow (`pillow`) - Image handling
- Tesseract (`pytesseract`) - OCR
- pdfplumber - PDF text extraction

**AI/LLM**:
- OpenAI API (`openai==1.59.5`)
  - `gpt-4.1-mini` - Structure normalization (default)
  - `gpt-4.1-nano` - Classification (cheap)
  - `gpt-4.1` - Escalation for hard cases

**Utilities**:
- rapidfuzz - Fuzzy matching for reconciliation
- qrcode - Label QR code generation
- ReportLab - PDF generation

---

## Project Structure

```
Image-processing/
├── src/
│   ├── intake/              # Stage 1: Upload validation & storage
│   │   ├── validator.py          # File validation (type, size, blur)
│   │   ├── deduplicator.py       # SHA256 checking
│   │   ├── rate_limiter.py       # Upload rate enforcement
│   │   └── storage_manager.py    # Supabase storage operations
│   │
│   ├── ocr/                 # Stage 2: Text extraction
│   │   ├── preprocessor.py       # Image preprocessing (deskew, binarize)
│   │   ├── tesseract_ocr.py      # Local OCR
│   │   ├── cloud_ocr.py          # Cloud OCR (Google/AWS)
│   │   └── pdf_extractor.py      # PDF text extraction
│   │
│   ├── extraction/          # Stage 3: Structure detection & parsing
│   │   ├── table_detector.py     # Detect tables in OCR text
│   │   ├── row_parser.py         # Parse rows with regex
│   │   ├── llm_normalizer.py     # gpt-4.1-mini normalization
│   │   └── cost_controller.py    # LLM escalation decisions
│   │
│   ├── reconciliation/      # Stage 4: Match to existing data
│   │   ├── part_matcher.py       # Fuzzy match to pms_parts
│   │   ├── shopping_matcher.py   # Match to shopping list
│   │   ├── order_matcher.py      # Match to purchase orders
│   │   └── suggestion_ranker.py  # Rank & score suggestions
│   │
│   ├── commit/              # Stage 5: Create immutable records
│   │   ├── event_creator.py      # Create receiving_events
│   │   ├── inventory_updater.py  # Update stock levels
│   │   ├── finance_recorder.py   # Record costs
│   │   └── audit_logger.py       # Audit trail
│   │
│   ├── label_generation/    # Stage 6: Generate labels
│   │   ├── qr_generator.py       # QR code creation
│   │   ├── pdf_layout.py         # 4x6 label layout
│   │   └── batch_processor.py    # Bulk label generation
│   │
│   ├── middleware/          # Cross-cutting concerns
│   │   ├── auth.py               # JWT validation
│   │   ├── yacht_isolation.py    # Multi-tenant enforcement
│   │   ├── role_checker.py       # HOD/crew/service role checks
│   │   └── error_handler.py      # Standardized error responses
│   │
│   ├── handlers/            # Business logic per section
│   │   ├── receiving_handler.py  # Section A: Packing slips
│   │   ├── label_handler.py      # Section B: Shipping labels
│   │   ├── discrepancy_handler.py # Section C: Discrepancy photos
│   │   ├── part_photo_handler.py # Section D: Part photos
│   │   └── pdf_handler.py        # Section E: Label PDFs
│   │
│   ├── routes/              # FastAPI endpoints
│   │   ├── upload_routes.py      # POST /api/v1/images/upload
│   │   ├── session_routes.py     # Session management
│   │   ├── commit_routes.py      # POST /api/v1/receiving/sessions/{id}/commit
│   │   └── label_routes.py       # Label generation endpoints
│   │
│   ├── models/              # Pydantic schemas
│   │   ├── upload_models.py
│   │   ├── session_models.py
│   │   ├── draft_line_models.py
│   │   └── response_models.py
│   │
│   └── main.py              # FastAPI application entry point
│
├── schemas/                 # JSON schemas for API contracts
│   ├── upload_request.json
│   ├── upload_response.json
│   ├── draft_lines_response.json
│   ├── commit_request.json
│   └── error_response.json
│
├── tests/                   # Test suite
│   ├── test_deduplication.py
│   ├── test_rate_limit.py
│   ├── test_ocr_parse.py
│   ├── test_draft_generation.py
│   ├── test_reconciliation.py
│   └── test_commit_flow.py
│
├── fixtures/                # Test fixtures
│   ├── sample_packing_slip.pdf
│   ├── sample_shipping_label.jpg
│   ├── blurry_image.jpg
│   └── duplicate_image.jpg
│
├── docs/                    # Documentation
│   ├── 01_existing_system_map.md
│   ├── 02_pipeline_sections.md
│   ├── 03_end_to_end_flow.md
│   ├── 04_api_contracts.md
│   ├── 05_model_strategy.md
│   ├── 06_abuse_protection.md
│   └── 07_security.md
│
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container definition
├── render.yaml              # Render.com deployment config
├── .env.example             # Environment variables template
└── README.md                # This file
```

---

## Quick Start (Local Development)

### Prerequisites

- Python 3.11+
- Tesseract OCR installed (`brew install tesseract` on macOS)
- Supabase account & credentials
- OpenAI API key

### Setup

```bash
# Clone repository
git clone https://github.com/shortalex12333/Image-processing.git
cd Image-processing

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your credentials

# Run locally
uvicorn src.main:app --reload --port 8001

# API available at http://localhost:8001
# Docs at http://localhost:8001/docs
```

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_deduplication.py -v
```

---

## API Endpoints

### Core Endpoints

```
POST   /api/v1/images/upload               # Upload image/PDF
GET    /api/v1/images/{id}/status          # Check processing status
GET    /api/v1/images/{id}                 # Get image metadata

POST   /api/v1/receiving/sessions          # Create receiving session
GET    /api/v1/receiving/sessions/{id}     # Get session + draft lines
PATCH  /api/v1/receiving/sessions/{id}/lines/{line_id}/verify  # Verify line
POST   /api/v1/receiving/sessions/{id}/commit  # Commit session (HOD only)

POST   /api/v1/labels/generate              # Generate label PDF
```

See `docs/04_api_contracts.md` for complete API documentation.

---

## Environment Variables

```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxx

# OpenAI
OPENAI_API_KEY=sk-xxx
OPENAI_ORG_ID=org-xxx  # Optional

# OCR Configuration
OCR_ENGINE=tesseract  # or 'google_vision', 'aws_textract'
TESSERACT_CMD=/usr/local/bin/tesseract  # Path to tesseract binary

# Cost Control
MAX_LLM_CALLS_PER_SESSION=3
MAX_TOKEN_BUDGET_PER_SESSION=10000
LLM_COVERAGE_THRESHOLD=0.8  # Trigger LLM if coverage < 80%

# Storage
STORAGE_BUCKET_RECEIVING=pms-receiving-images
STORAGE_BUCKET_DISCREPANCY=pms-discrepancy-photos
STORAGE_BUCKET_LABELS=pms-label-pdfs
STORAGE_BUCKET_PARTS=pms-part-photos

# Rate Limiting
MAX_UPLOADS_PER_HOUR=50
MAX_FILE_SIZE_MB=15

# Deployment
RENDER_SERVICE_URL=https://image-processing-xxx.onrender.com
LOG_LEVEL=info
SENTRY_DSN=  # Optional error tracking
```

---

## Deployment (Render.com)

### Manual Deploy

```bash
# Push to GitHub
git push origin main

# Render will auto-deploy from main branch
# Or trigger manual deploy in Render dashboard
```

### Configuration

1. Create new Web Service on Render
2. Connect GitHub repository
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `uvicorn src.main:app --host 0.0.0.0 --port $PORT`
5. Add environment variables from `.env.example`
6. Deploy

### Health Check

```bash
curl https://your-service.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "components": {
    "database": "ok",
    "storage": "ok",
    "ocr": "ok",
    "llm": "ok"
  }
}
```

---

## Cost Estimates

### Per Receiving Session (Typical)

**Best case** (good OCR, no LLM):
- OCR (Tesseract): $0.00 (self-hosted)
- Heuristics: $0.00
- **Total**: $0.00-0.01

**Average case** (needs LLM normalization):
- OCR: $0.01-0.03
- gpt-4.1-mini: $0.02-0.10
- **Total**: $0.03-0.13

**Worst case** (escalation):
- OCR: $0.01-0.03
- gpt-4.1-mini: $0.05
- gpt-4.1: $0.05-0.20
- **Total**: $0.11-0.28

**Hard cap**: $0.50 per session (enforced)

### Monthly Estimates (100 receiving sessions)

- Best case: $0-10
- Average case: $3-13
- Worst case: $11-28

**Optimization**: 70-80% of sessions avoid LLM with good heuristics.

---

## Testing Strategy

### Unit Tests

- File validation (type, size, blur check)
- SHA256 deduplication
- Rate limit enforcement
- OCR extraction
- Table detection
- Row parsing
- LLM normalization (mocked)
- Fuzzy matching
- Draft line creation

### Integration Tests

- Upload → OCR → Draft (full pipeline)
- Commit → Inventory update
- Label PDF generation
- Error handling scenarios

### Fixtures

- `sample_packing_slip.pdf` - Clean, table-based
- `messy_packing_slip.jpg` - Low quality, needs LLM
- `shipping_label.jpg` - FedEx label
- `blurry_image.jpg` - Should fail blur check
- `duplicate_image.jpg` - For deduplication test

---

## Security

### Authentication

- All endpoints require JWT token
- Service role key for background jobs
- Yacht isolation enforced on all queries

### Authorization

- **crew**: Upload, verify own lines
- **hod**: Commit sessions, override matches
- **service_role**: Processing jobs, OCR writes

### Data Protection

- IP addresses stored for 90 days only
- Signed URLs with 1-hour expiry
- RLS policies enforce yacht-level isolation
- SHA256 hashing prevents duplicate storage costs

See `docs/07_security.md` for complete security documentation.

---

## Monitoring

### Key Metrics

- Upload success rate
- OCR success rate
- LLM invocation rate (target: < 30%)
- Average processing time
- Cost per session
- Error rate by type

### Logging

```python
logger.info("✅ Image uploaded", extra={
    'image_id': uuid,
    'yacht_id': yacht_id,
    'file_size_bytes': size,
    'is_duplicate': False
})

logger.warning("⚠️ LLM escalation triggered", extra={
    'session_id': uuid,
    'coverage': 0.65,
    'reason': 'low_coverage'
})

logger.error("❌ OCR failed", extra={
    'image_id': uuid,
    'error': str(e)
}, exc_info=True)
```

---

## Support & Contribution

### Reporting Issues

Open an issue on GitHub with:
- Image-processing version
- Error code (if applicable)
- Sample image (if not sensitive)
- Expected vs actual behavior

### Development

1. Fork repository
2. Create feature branch
3. Write tests
4. Submit pull request

---

## License

Proprietary - CelesteOS / Cloud_PMS

---

## Changelog

### v1.0.0 (2026-01-09)
- Initial release
- Section A: Receiving workflow
- Section B: Shipping label support
- Section C: Discrepancy photos
- Section D: Part photos
- Section E: Label PDF generation
- Tesseract OCR integration
- OpenAI LLM normalization
- Cost-controlled escalation
- Comprehensive test suite
- Render.com deployment

---

## Next Steps

1. **Complete implementation** (in progress)
2. **Deploy to Render** (pending API key)
3. **Frontend integration** (after backend stable)
4. **Production testing** (with real packing slips)
5. **Cost optimization** (refine heuristics to reduce LLM usage)

---

**Status**: 🚧 Under Development
**Contact**: CelesteOS Team
**Documentation**: See `/docs` folder for detailed specifications
