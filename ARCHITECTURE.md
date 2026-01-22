# Architecture Documentation

**Date**: 2026-01-22
**Status**: Honest assessment of what exists vs what's aspirational

---

## System Overview

**What This System Actually Is**:
A FastAPI backend service that receives uploaded images (packing slips, receipts), runs OCR, extracts structured data, and stores results in Supabase PostgreSQL.

**What This System Is NOT**:
- NOT a full document management system
- NOT tested in production with real users
- NOT equipped with monitoring or alerting
- NOT using Row Level Security (RLS) at database level
- NOT connected to any frontend (API-only)

---

## Architecture Diagram

```
┌─────────────┐
│   Client    │ (Postman, cURL, or future frontend)
│  (untested) │
└──────┬──────┘
       │ HTTP POST /api/v1/images/upload
       │ Authorization: Bearer <JWT>
       ▼
┌─────────────────────────────────────────────────┐
│           FastAPI Backend (Python)              │
│         Deployed on Render (Starter Plan)       │
│                512 MB RAM, 0.5 CPU              │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌──────────────┐                              │
│  │ Auth Middleware │ ◄─── Supabase JWT        │
│  └──────┬────────┘       Validation            │
│         │                                       │
│         ▼                                       │
│  ┌──────────────┐                              │
│  │ Rate Limiter  │ ◄─── 50 uploads/hour        │
│  └──────┬────────┘                             │
│         │                                       │
│         ▼                                       │
│  ┌──────────────┐                              │
│  │  Validator    │ ◄─── File type, size, DQS   │
│  └──────┬────────┘                             │
│         │                                       │
│         ▼                                       │
│  ┌──────────────┐                              │
│  │ Deduplicator  │ ◄─── SHA256 hash check      │
│  └──────┬────────┘                             │
│         │                                       │
│         ▼                                       │
│  ┌──────────────┐       ┌──────────────┐      │
│  │Storage Upload│────►  │ Supabase     │      │
│  │  (Handler)   │       │ Storage      │      │
│  └──────┬────────┘       └──────────────┘      │
│         │                                       │
│         ▼                                       │
│  ┌──────────────┐                              │
│  │ OCR Factory   │ ◄─── Feature flags          │
│  │ (auto-select) │                             │
│  └──────┬────────┘                             │
│         │                                       │
│    ┌────┴────┬─────────┬──────────┐           │
│    ▼         ▼         ▼          ▼           │
│ ┌─────┐  ┌─────┐  ┌─────┐   ┌────────┐       │
│ │Paddle│  │Tesser│  │Google│   │ Surya  │       │
│ │ OCR │  │ act  │  │Vision│   │  OCR   │       │
│ └─────┘  └─────┘  └─────┘   └────────┘       │
│  94%      31%       80%        91%             │
│ 500MB    50MB     Cloud      4GB               │
│                                                 │
│         ▼                                       │
│  ┌──────────────┐                              │
│  │Entity Extract│ ◄─── order_number, tracking  │
│  │ (STUBBED)    │       supplier, parts        │
│  └──────┬────────┘                             │
│         │                                       │
│         ▼                                       │
│  ┌──────────────┐       ┌──────────────┐      │
│  │Save to DB    │────►  │ Supabase     │      │
│  │              │       │ PostgreSQL   │      │
│  └──────────────┘       └──────────────┘      │
│                                                 │
└─────────────────────────────────────────────────┘
                           │
                           ▼
                ┌──────────────────┐
                │ pms_image_uploads│
                │   37 columns     │
                │  (no RLS yet)    │
                └──────────────────┘
```

---

## Data Flow (Happy Path)

### Request: POST /api/v1/images/upload

**Step 1: Authentication** ✅ **WIRED**
```python
# src/middleware/auth.py
token = request.headers.get("Authorization").replace("Bearer ", "")
user = supabase.auth.get_user(token)  # Validates with Supabase
yacht_id = user.user_metadata["yacht_id"]  # MUST exist
```

**What happens if yacht_id missing?** → 403 Forbidden

---

**Step 2: Rate Limiting** ✅ **WIRED** (but slow)
```python
# src/intake/rate_limiter.py
count = supabase.table("pms_image_uploads")
    .select("id", count="exact")
    .eq("yacht_id", yacht_id)
    .gte("uploaded_at", one_hour_ago)
    .execute()

if count >= 50:
    raise RateLimitExceeded
```

**Known Issue**: Uses database query count instead of cached counter (slow at scale)

---

**Step 3: Validation** ✅ **WIRED**
```python
# src/intake/validator.py
- File type whitelist: jpg, png, heic, pdf
- Max size: 15 MB
- Min dimensions: 800x600
- Document Quality Score (DQS): blur + glare + contrast
- DQS threshold: 70.0 (configurable)
```

**What happens if validation fails?** → 400 Bad Request with specific error

---

**Step 4: Deduplication** ✅ **WIRED**
```python
# src/intake/deduplicator.py
sha256 = hashlib.sha256(file_content).hexdigest()

existing = supabase.table("pms_image_uploads")
    .select("*")
    .eq("yacht_id", yacht_id)
    .eq("sha256_hash", sha256)
    .maybeSingle()
    .execute()

if existing.data:
    return existing.data  # Don't upload again
```

**Database Constraint**: Unique index on `(yacht_id, sha256_hash)`

---

**Step 5: Storage Upload** ✅ **WIRED**
```python
# src/handlers/receiving_handler.py
storage_path = f"{yacht_id}/{timestamp}_{filename}"

supabase.storage.from_("image-uploads").upload(
    storage_path,
    file_content,
    file_options={"content-type": mime_type}
)

# Returns public URL (if bucket is public) or signed URL
```

**Supabase Bucket**: `image-uploads` (created manually)

---

**Step 6: Database Record** ✅ **WIRED**
```python
# Insert initial record
record = {
    "yacht_id": yacht_id,
    "uploaded_by": user_id,
    "file_name": filename,
    "mime_type": mime_type,
    "file_size_bytes": file_size,
    "sha256_hash": sha256,
    "storage_path": storage_path,
    "width": width,
    "height": height,
    "blur_score": blur_score,
    "validation_stage": "validated",
    "processing_status": "queued",
    "uploaded_at": now,
}

result = supabase.table("pms_image_uploads").insert(record).execute()
image_id = result.data[0]["id"]
```

**Table**: `pms_image_uploads` (37 columns, no RLS)

---

**Step 7: OCR Processing** ✅ **WIRED** (auto-selection)
```python
# src/ocr/ocr_factory.py
ocr_engine = OCRFactory.get_ocr_engine()  # Auto-selects based on feature flags

# Priority order:
# 1. PaddleOCR (94% accuracy, 500MB RAM) - disabled on Starter plan
# 2. Surya (91% accuracy, 4GB RAM) - disabled on Starter plan
# 3. Google Vision (80% accuracy, cloud API) - enabled if API key set
# 4. AWS Textract (not implemented)
# 5. Tesseract (31% accuracy, 50MB RAM) - fallback only

ocr_result = ocr_engine.process_image(file_content)
```

**Current Deployment**: Only Tesseract enabled (Starter plan = 512MB RAM)

**What happens if no OCR engine available?** → 500 Internal Server Error

---

**Step 8: Entity Extraction** ⚠️ **STUBBED**
```python
# src/extraction/entity_extractor.py
# EXISTS but NOT WIRED in receiving_handler.py

# What it SHOULD extract:
extracted_entities = {
    "order_number": "40674",
    "supplier": "Mechanical Equipment Inc",
    "tracking_numbers": ["1Z260AT50346207055"],
    "part_codes": ["O2Y"],
    "date": "2019-04-15"
}
```

**Status**: Code exists, not integrated, not tested

---

**Step 9: Save OCR Results** ✅ **WIRED**
```python
# src/handlers/receiving_handler.py
supabase.table("pms_image_uploads").update({
    "ocr_raw_text": ocr_result.text,
    "ocr_confidence": ocr_result.confidence,
    "ocr_engine": ocr_result.engine,
    "ocr_processing_time_ms": ocr_result.processing_time_ms,
    "ocr_line_count": len(ocr_result.lines),
    "ocr_word_count": ocr_result.word_count,
    "ocr_completed_at": now,
    "validation_stage": "completed",
    "processing_status": "completed"
}).eq("id", image_id).execute()
```

**Audit Trail**: All OCR results are logged (but can be modified/deleted - no immutability)

---

**Step 10: Response** ✅ **WIRED**
```json
{
  "status": "success",
  "images": [
    {
      "image_id": "uuid",
      "file_name": "packing_slip.png",
      "storage_path": "yacht-id/timestamp_packing_slip.png",
      "processing_status": "completed",
      "ocr_engine": "tesseract",
      "ocr_confidence": 0.31,
      "uploaded_at": "2026-01-22T10:30:00Z"
    }
  ]
}
```

---

## API Contract

### Endpoint: POST /api/v1/images/upload

**Authentication**: Required (JWT Bearer token)

**Headers**:
```
Authorization: Bearer <jwt_token>
Content-Type: multipart/form-data
```

**Request Body**:
```
files: <file> (required, one or multiple)
upload_type: "receiving" | "photo" (optional, default: "receiving")
```

**Success Response (200)**:
```json
{
  "status": "success",
  "images": [
    {
      "image_id": "uuid",
      "file_name": "string",
      "storage_path": "string",
      "processing_status": "completed" | "queued" | "processing" | "failed",
      "ocr_engine": "paddleocr" | "tesseract" | "google_vision" | "surya",
      "ocr_confidence": 0.0-1.0,
      "uploaded_at": "ISO8601 timestamp"
    }
  ]
}
```

**Error Responses**:

| Code | Reason | Body |
|------|--------|------|
| 400 | File validation failed | `{"detail": "File too large"}` |
| 400 | No files provided | `{"detail": "No files provided"}` |
| 401 | Missing/invalid JWT | `{"detail": "Invalid token"}` |
| 403 | User not associated with yacht | `{"detail": "User not associated with any yacht"}` |
| 413 | File too large | `{"detail": "File exceeds 15 MB limit"}` |
| 415 | Unsupported file type | `{"detail": "Unsupported file type"}` |
| 429 | Rate limit exceeded | `{"detail": "Rate limit exceeded: 50 uploads/hour"}` |
| 500 | OCR engine failure | `{"detail": "OCR processing failed"}` |
| 500 | Database error | `{"detail": "Database operation failed"}` |

---

### Endpoint: GET /health

**Authentication**: NOT required (public)

**Success Response (200)**:
```json
{
  "status": "healthy"
}
```

---

## Database Schema

### Table: pms_image_uploads

**37 Columns** (as of 2026-01-22):

| Column | Type | Purpose | Populated? |
|--------|------|---------|-----------|
| `id` | uuid | Primary key | ✅ Auto |
| `yacht_id` | uuid | Tenant isolation | ✅ From JWT |
| `uploaded_by` | uuid | User who uploaded | ✅ From JWT |
| `file_name` | text | Original filename | ✅ From upload |
| `mime_type` | text | image/png, application/pdf | ✅ From upload |
| `file_size_bytes` | bigint | File size | ✅ From upload |
| `sha256_hash` | text | Deduplication hash | ✅ Calculated |
| `storage_path` | text | Supabase storage path | ✅ Generated |
| `width` | integer | Image width in pixels | ✅ From validation |
| `height` | integer | Image height in pixels | ✅ From validation |
| `blur_score` | float | Blur detection (0-1) | ✅ From validation |
| `validation_stage` | text | validated/failed | ✅ From validation |
| `processing_status` | text | queued/processing/completed/failed | ✅ Lifecycle |
| `ocr_raw_text` | text | Raw OCR output | ✅ From OCR |
| `ocr_confidence` | float | OCR confidence (0-1) | ✅ From OCR |
| `ocr_engine` | text | paddleocr/tesseract/etc | ✅ From OCR |
| `ocr_processing_time_ms` | integer | OCR time in ms | ✅ From OCR |
| `ocr_line_count` | integer | Number of text lines | ✅ From OCR |
| `ocr_word_count` | integer | Number of words | ✅ From OCR |
| `ocr_completed_at` | timestamp | When OCR finished | ✅ From OCR |
| `extracted_entities` | jsonb | Structured data | ❌ Stubbed |
| `metadata` | jsonb | Additional metadata | ✅ Optional |
| `uploaded_at` | timestamp | Upload timestamp | ✅ Auto |
| `processed_at` | timestamp | Processing timestamp | ✅ Auto |
| `created_at` | timestamp | Record creation | ✅ Auto |
| `updated_at` | timestamp | Last update | ✅ Auto |
| ... (11 more legacy columns) | | | ❌ Unused |

**Indexes**:
- `idx_pms_image_uploads_yacht_id` on `yacht_id` ✅
- `idx_pms_image_uploads_yacht_sha256` on `(yacht_id, sha256_hash)` UNIQUE ✅
- `idx_pms_image_uploads_processing_status` on `processing_status` ❌ NOT CREATED
- `idx_pms_image_uploads_ocr_text` GIN full-text search ❌ NOT CREATED

**RLS Policies**: ❌ **NONE** (HIGH SECURITY RISK)

---

## Deployment Architecture

### Hosting: Render.com

**Plan**: Starter ($7/month)
- 512 MB RAM
- 0.5 CPU
- 30 GB disk
- Auto-deploy from GitHub (via webhook)

**Service URL**: https://pipeline-core.int.celeste7.ai

**Health Check**: GET /health

**Auto-Deploy**:
- Push to `main` branch → GitHub webhook → Render builds → Deploys automatically
- Build time: ~5 minutes (Docker build)
- Cold start: ~30 seconds (model loading)

**Environment Variables** (24 total):
```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://vzsohavtuotocgrfkfyd.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<secret>

# OCR Feature Flags
ENABLE_GOOGLE_VISION=true
ENABLE_TESSERACT=true
ENABLE_PADDLEOCR=false  # Disabled (not enough RAM)
ENABLE_SURYA=false      # Disabled (needs 4GB RAM)
ENABLE_AWS_TEXTRACT=false

# OCR API Keys
GOOGLE_VISION_API_KEY=<secret>
OPENAI_API_KEY=<secret>  # Not used yet

# Application
ENVIRONMENT=production
LOG_LEVEL=info
PORT=8001

# Legacy
JWT_SECRET=<secret>  # Not used (Supabase handles JWT)
```

---

## What's Wired vs What's Stubbed

### ✅ Fully Wired (Tested Locally)

1. **Authentication** - Supabase JWT validation via `supabase.auth.get_user(token)`
2. **Rate Limiting** - 50 uploads/hour per yacht (database query)
3. **File Validation** - Type, size, dimensions, DQS
4. **Deduplication** - SHA256 hash check with unique constraint
5. **Storage Upload** - Supabase storage bucket
6. **Database Insert** - pms_image_uploads record creation
7. **OCR Factory** - Auto-selects best available OCR engine
8. **Tesseract OCR** - Fallback OCR (31% accuracy)
9. **Google Vision OCR** - Cloud OCR (80% accuracy, if API key set)
10. **PaddleOCR** - High accuracy OCR (94%, but disabled on Starter plan)
11. **Surya OCR** - High accuracy OCR (91%, but disabled on Starter plan)
12. **OCR Results Saving** - Updates database with OCR output
13. **Health Check** - GET /health endpoint

### ⚠️ Stubbed (Code Exists, Not Integrated)

1. **Entity Extraction** - `entity_extractor.py` exists but not called in receiving_handler.py
2. **Document Classification** - `document_classifier.py` exists but not used
3. **Order Matching** - `order_matcher_by_number.py` exists but no data to match against
4. **Part Matching** - `part_matcher.py` exists but no parts database
5. **Shopping List Matching** - `shopping_matcher.py` exists but no shopping lists
6. **Reconciliation** - Entire reconciliation module exists but no integration

### ❌ Not Implemented

1. **Row Level Security (RLS)** - No database-level tenant isolation
2. **Audit Logging** - No immutable audit trail
3. **Monitoring** - No Sentry, no metrics, no alerting
4. **Error Tracking** - No error aggregation or analysis
5. **Performance Monitoring** - No latency tracking or profiling
6. **User Feedback Loop** - No way to report bad OCR results
7. **Webhook Notifications** - No async processing notifications
8. **Batch Processing** - No bulk upload support
9. **Image Preprocessing** - No enhancement before OCR
10. **PDF Multi-Page** - PDFs are processed as single page
11. **Table Extraction** - No structured table detection
12. **LLM Normalization** - `llm_normalizer.py` exists but not wired
13. **Cost Controller** - `cost_controller.py` exists but not used

---

## Known Gaps and Debt

### Critical (Must Fix Before Production)

1. **No RLS Policies** - Any authenticated user can query all yacht data if they know the yacht_id
   - **Impact**: Data breach risk
   - **Fix**: Enable RLS, add `yacht_id` policies

2. **No Production Testing** - Service has never been tested with real users in production
   - **Impact**: Unknown behavior under load, unknown edge cases
   - **Fix**: Manual testing with real JWT, real uploads

3. **No Monitoring** - No visibility into errors, performance, or usage
   - **Impact**: Blind to failures, can't diagnose issues
   - **Fix**: Add Sentry, add Render metrics integration

4. **Database Schema Mismatch** - Migration exists but not applied
   - **Impact**: Code expects columns that may not exist
   - **Fix**: Apply `migrations/20260122_fix_image_uploads_schema.sql`

### High (Important but Not Blocking)

5. **Entity Extraction Not Wired** - OCR works but structured data not extracted
   - **Impact**: Raw OCR text only, no order numbers or tracking numbers
   - **Fix**: Wire `entity_extractor.py` into `receiving_handler.py`

6. **Rate Limiter Uses DB Query** - Slow at scale, not cached
   - **Impact**: Performance degradation with high traffic
   - **Fix**: Use Redis or in-memory cache

7. **No Immutable Audit Trail** - OCR results can be modified or deleted
   - **Impact**: Can't prove what OCR returned
   - **Fix**: Add `updated_at` tracking or separate audit table

8. **OCR Accuracy on Starter Plan** - Only Tesseract enabled (31% accuracy)
   - **Impact**: Poor OCR results, user frustration
   - **Fix**: Upgrade to Standard plan ($25/month) to enable PaddleOCR (94%)

### Medium (Nice to Have)

9. **No Webhook Notifications** - Synchronous processing only (slow)
   - **Impact**: API calls take 30+ seconds (waiting for OCR)
   - **Fix**: Add async processing with webhooks

10. **No Batch Upload** - One file at a time only
    - **Impact**: Slow for bulk uploads
    - **Fix**: Add batch endpoint

11. **No Image Preprocessing** - OCR runs on raw images
    - **Impact**: Suboptimal OCR results on low-quality images
    - **Fix**: Add preprocessing pipeline (deskew, denoise, enhance)

12. **No Error Retry Logic** - Failed uploads are lost
    - **Impact**: User must manually retry
    - **Fix**: Add retry queue with exponential backoff

### Low (Future Enhancements)

13. **No User Feedback Loop** - Can't report bad OCR
14. **No Analytics Dashboard** - Can't see usage patterns
15. **No Cost Tracking** - Don't know Google Vision API costs
16. **No Table Extraction** - Can't extract line items from tables
17. **No Multi-Page PDF** - Only first page of PDF is processed

---

## Security Model

### Current State: Manual Filtering Only

**Authentication**: ✅ Supabase JWT validation
**Authorization**: ⚠️ Manual `yacht_id` filtering in code
**Data Isolation**: ❌ No database-level enforcement (RLS not enabled)

**How It Works Now**:
```python
# Every query MUST manually filter by yacht_id
result = supabase.table("pms_image_uploads") \
    .select("*") \
    .eq("yacht_id", yacht_id) \  # ← Manual filtering
    .execute()
```

**Risk**: If a developer forgets to add `.eq("yacht_id", yacht_id)`, data leaks.

**How It SHOULD Work** (with RLS):
```sql
ALTER TABLE pms_image_uploads ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Yacht isolation"
  ON pms_image_uploads
  USING (yacht_id = (current_setting('app.current_yacht_id')::uuid));
```

With RLS, even if code forgets to filter, database blocks cross-yacht queries.

**Status**: See `SECURITY_INVARIANTS.md` for full security requirements.

---

## Performance Characteristics

### Expected Latency (Starter Plan, 512 MB RAM, 0.5 CPU)

| Operation | Time | Notes |
|-----------|------|-------|
| Auth validation | 100ms | Supabase API call |
| Rate limit check | 50ms | Database query (should be cached) |
| File validation | 10ms | Local processing |
| Deduplication check | 50ms | Database query |
| Storage upload | 500ms | Supabase storage API |
| Database insert | 100ms | PostgreSQL insert |
| **Tesseract OCR** | **2-5s** | CPU-bound, single-threaded |
| **Google Vision OCR** | **300ms** | Cloud API (if enabled) |
| **PaddleOCR** | **30s** | Disabled (not enough RAM) |
| **Surya OCR** | **30s** | Disabled (not enough RAM) |
| Database update | 100ms | PostgreSQL update |
| **Total (Tesseract)** | **3-6s** | Current deployment |
| **Total (Google Vision)** | **1-2s** | If API key configured |

### Cold Start

First request after deploy or idle timeout:
- Model loading: 10-30 seconds
- Subsequent requests: Normal latency

### Throughput

**Starter Plan**: ~1 request per 5 seconds = 12 uploads/minute = 720 uploads/hour

**Bottleneck**: Single CPU, OCR processing

**Rate Limit**: 50 uploads/hour per yacht (protects against abuse)

### Scaling Options

| Plan | RAM | CPU | OCR Engine | Accuracy | Latency | Cost |
|------|-----|-----|------------|----------|---------|------|
| **Starter (current)** | 512 MB | 0.5 | Tesseract only | 31% | 5s | $7/mo |
| **Standard** | 2 GB | 1 | PaddleOCR | 94% | 30s | $25/mo |
| **Pro** | 4 GB | 2 | Surya OCR | 91% | 15s | $85/mo |
| **Pro + Google Vision** | 4 GB | 2 | Google Vision | 80% | 1s | $85/mo + API costs |

**Recommendation**: Upgrade to Standard plan ($25/mo) to enable PaddleOCR (94% accuracy).

---

## Monitoring and Observability

### Current State: ❌ None

**Logging**: stdout only (Render dashboard)
**Metrics**: None
**Alerting**: None
**Error Tracking**: None
**Performance Monitoring**: None

### What Should Exist

1. **Sentry** - Error tracking and aggregation
2. **Render Metrics** - CPU, memory, request rate
3. **Database Metrics** - Query performance, slow queries
4. **Custom Metrics** - OCR accuracy, processing time, failure rate
5. **Alerts** - High error rate, high latency, out of memory

### How to Add

```python
# src/main.py
import sentry_sdk

sentry_sdk.init(
    dsn=settings.sentry_dsn,
    environment=settings.environment,
    traces_sample_rate=0.1,
)
```

---

## Testing Coverage

### Unit Tests

**Location**: `tests/test_*.py`
**Count**: 29 test files, ~200 test cases
**Coverage**: Unknown (no coverage report)

**What's Tested**:
- OCR imports
- Tesseract OCR basic functionality
- Google Vision OCR basic functionality
- OCR factory selection logic
- File validation logic
- Database connection
- RLS policy queries (but RLS not enabled)
- Entity extraction logic (but not integrated)
- Order matching logic (but no data)
- API routes (but no real auth)

**What's NOT Tested**:
- Real authentication with JWT
- Real uploads to Supabase storage
- Real database writes
- Rate limiting under load
- Deduplication with concurrent uploads
- Error scenarios (OOM, network failures)
- Production behavior

### Integration Tests

**Status**: ❌ None exist

### E2E Tests

**Status**: ❌ None exist

### Load Tests

**Status**: ❌ None exist

### What Should Be Tested

See `HANDOVER.md` for detailed testing checklist.

---

## Dependencies

### Python Packages (42 total)

**Key Dependencies**:
- `fastapi==0.115.12` - Web framework
- `uvicorn==0.34.0` - ASGI server
- `supabase==2.12.0` - Database and storage client
- `paddleocr==2.9.3` - OCR engine (94% accuracy)
- `pytesseract==0.3.13` - OCR engine (31% accuracy)
- `google-cloud-vision==3.9.1` - Cloud OCR (80% accuracy)
- `surya-ocr==0.7.6` - OCR engine (91% accuracy)
- `pillow==11.1.0` - Image processing
- `numpy==2.2.3` - Array operations
- `pydantic==2.10.6` - Data validation
- `python-multipart==0.0.20` - File upload support

**Full List**: See `requirements.txt`

### System Dependencies

- Python 3.11
- Tesseract OCR binary (installed via Dockerfile)
- libGL.so (for OpenCV, installed via Dockerfile)

### External Services

1. **Supabase** (PostgreSQL + Storage + Auth)
   - URL: `https://vzsohavtuotocgrfkfyd.supabase.co`
   - Project: `vzsohavtuotocgrfkfyd`
   - Region: Unknown
   - Plan: Free tier (currently)

2. **Google Cloud Vision API** (optional)
   - Requires `GOOGLE_VISION_API_KEY`
   - Cost: $1.50 per 1000 images
   - Accuracy: 80%

3. **Render.com** (hosting)
   - Service: `image-processing`
   - Region: Oregon
   - Plan: Starter ($7/month)

---

## Configuration Management

### Environment Variables (24 total)

**Required for Service to Start**:
```bash
NEXT_PUBLIC_SUPABASE_URL=<required>
SUPABASE_SERVICE_ROLE_KEY=<required>
```

**Optional (Defaults Provided)**:
```bash
ENVIRONMENT=production
LOG_LEVEL=info
PORT=8001

ENABLE_GOOGLE_VISION=false
ENABLE_TESSERACT=true
ENABLE_PADDLEOCR=false
ENABLE_SURYA=false
ENABLE_AWS_TEXTRACT=false

GOOGLE_VISION_API_KEY=<optional>
OPENAI_API_KEY=<optional>

JWT_SECRET=<legacy, not used>
```

**Configuration Files**:
- `render.yaml` - Render deployment config
- `.env.example` - Example environment variables
- `Dockerfile` - Container build instructions

**Feature Flags**:
- Controlled via environment variables (`ENABLE_*`)
- No runtime toggling (requires redeploy)

---

## Deployment Process

### Automatic (Current Setup)

1. Developer pushes to `main` branch
2. GitHub webhook notifies Render
3. Render pulls latest code
4. Render builds Docker image (~5 minutes)
5. Render deploys new container
6. Health check passes → Live
7. Old container shut down

**Zero Downtime**: Yes (Render handles gracefully)

**Rollback**: Manual (redeploy previous commit)

### Manual (Alternative)

```bash
# Build locally
docker build -t image-processing .

# Test locally
docker run -p 8001:8001 --env-file .env.local image-processing

# Push to GitHub
git push origin main

# Render auto-deploys
```

---

## Error Scenarios and Recovery

### Scenario: OCR Engine OOM (Out of Memory)

**When**: PaddleOCR enabled on Starter plan (512 MB RAM)
**Symptom**: 502 Bad Gateway, container crashes
**Recovery**: Disable PaddleOCR, enable Tesseract only
**Prevention**: Upgrade to Standard plan (2 GB RAM)

### Scenario: Supabase Connection Failure

**When**: Network issue, service key rotated
**Symptom**: 500 errors, "Could not authenticate"
**Recovery**: Check Supabase dashboard, verify service key
**Prevention**: Add retry logic, add monitoring

### Scenario: Rate Limit Exceeded

**When**: User uploads 51+ files in 1 hour
**Symptom**: 429 error
**Recovery**: Wait 1 hour or increase limit
**Prevention**: Communicate limit to users

### Scenario: Storage Bucket Full

**When**: Storage quota exceeded
**Symptom**: Upload fails with storage error
**Recovery**: Delete old files or upgrade Supabase plan
**Prevention**: Monitor storage usage

### Scenario: JWT Validation Fails

**When**: Token expired, user metadata missing yacht_id
**Symptom**: 401 or 403 error
**Recovery**: User must re-login, admin must set yacht_id
**Prevention**: Clear error messages

---

## Future Architecture (Aspirational)

### What This Could Become

```
┌─────────────┐
│   Frontend   │ (Next.js, React)
│  (not built) │
└──────┬───────┘
       │
       ▼
┌──────────────┐       ┌──────────────┐
│  API Gateway │◄─────►│   Auth       │
│  (FastAPI)   │       │  (Supabase)  │
└──────┬───────┘       └──────────────┘
       │
       ├───────────────┬──────────────┬─────────────┐
       ▼               ▼              ▼             ▼
┌──────────┐   ┌──────────┐   ┌──────────┐  ┌──────────┐
│  Upload  │   │   OCR    │   │ Reconcile│  │  Export  │
│  Service │   │  Service │   │  Service │  │  Service │
└────┬─────┘   └────┬─────┘   └────┬─────┘  └────┬─────┘
     │              │              │             │
     └──────────────┴──────────────┴─────────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │  PostgreSQL + RLS   │
         │  (Supabase)         │
         └─────────────────────┘
```

**Key Differences**:
- Microservices architecture (separate services for each concern)
- Async processing (webhook-driven)
- Message queue (Redis or RabbitMQ)
- Caching layer (Redis)
- CDN for static assets
- Multiple OCR workers (horizontal scaling)
- Monitoring and alerting (Sentry, DataDog)
- CI/CD pipeline (automated testing before deploy)

**When to Migrate**: When traffic exceeds 1000 uploads/day or team size exceeds 3 engineers.

---

## Summary

### What Works

✅ Basic upload and OCR pipeline
✅ Authentication via Supabase JWT
✅ Multi-tenant data isolation (manual filtering)
✅ File validation and deduplication
✅ Auto-deploy from GitHub
✅ Feature flags for OCR engines

### What Doesn't Work

❌ No RLS policies (security risk)
❌ Entity extraction not wired (no structured data)
❌ Reconciliation not wired (no matching)
❌ No monitoring (blind to errors)
❌ Poor OCR accuracy on Starter plan (31%)
❌ No production testing (unknown behavior)

### What to Fix First

1. **Test in production** (manual verification)
2. **Enable RLS** (critical security fix)
3. **Upgrade to Standard plan** (enable PaddleOCR for 94% accuracy)
4. **Wire entity extraction** (get structured data)
5. **Add monitoring** (Sentry for errors)

See `HANDOVER.md` for detailed action plan.

---

**End of Architecture Documentation**
