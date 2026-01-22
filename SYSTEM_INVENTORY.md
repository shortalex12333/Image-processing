# System Inventory
**Date**: 2026-01-22
**Status**: Feature development frozen for handover
**Repository**: https://github.com/shortalex12333/Image-processing

---

## What This System Is

An **OCR + document processing microservice** for a yacht parts management system (PMS). It processes images of packing slips, shipping labels, and part photos uploaded by yacht crew, extracting structured data for inventory tracking.

**Not**: A standalone application. This is a backend API service that requires:
- A separate frontend (not in this repository)
- Supabase PostgreSQL database (external service)
- OpenAI API (external service) for LLM normalization

---

## Core Functionality

### 1. Image Upload Pipeline
**Status**: Implemented, tested locally, not yet verified in production

**Flow**:
```
Upload → Validation → Deduplication → Storage → Database Record
```

**Components**:
- `src/intake/validator.py` - File type, size, quality checks (DQS)
- `src/intake/deduplicator.py` - SHA256-based duplicate detection
- `src/intake/rate_limiter.py` - 50 uploads/hour limit per yacht
- `src/intake/storage_manager.py` - Supabase storage upload

**Critical Validation Checks**:
- File types: JPEG, PNG, HEIC, PDF
- Max size: 15 MB
- Min dimensions: 800x600 px (configurable)
- Document Quality Score (DQS): blur + glare + contrast threshold 70/100

### 2. OCR Processing (Multiple Engines)
**Status**: Factory pattern implemented, local Docker tested, production untested

**Engines Available**:
1. **PaddleOCR** - 94% accuracy, ~500MB RAM, 9s processing
2. **Google Vision** - 80% accuracy, $1.50/1000 images, 400ms processing
3. **Tesseract** - 31% accuracy, minimal RAM, 1s processing (fallback only)
4. **Surya** - 91% accuracy, ~4GB RAM, 30s processing (not production-ready)

**Feature Flag System** (added this session):
```python
# src/config.py
enable_google_vision: bool = False
enable_tesseract: bool = True
enable_paddleocr: bool = False
enable_surya: bool = False
```

**Factory Auto-Selection** (`src/ocr/ocr_factory.py`):
- Tries engines in priority order (PaddleOCR > Surya > Google > Tesseract)
- Only loads engines with `enable_*=true`
- Critical for RAM-constrained deployments

### 3. Document Entity Extraction
**Status**: Code exists, not tested

**Pipeline**:
```
OCR Text → Table Detection → Row Parsing → LLM Normalization → Reconciliation
```

**Components**:
- `src/extraction/table_detector.py` - Detect line-item tables
- `src/extraction/row_parser.py` - Deterministic regex parsing
- `src/extraction/llm_normalizer.py` - OpenAI GPT-4.1-mini for messy text
- `src/extraction/cost_controller.py` - LLM escalation logic (cost control)

**LLM Models** (configurable):
- `gpt-4.1-nano` - Classification ($0.10/1M tokens)
- `gpt-4.1-mini` - Normalization ($15/1M tokens) - default
- `gpt-4.1` - Escalation for hard cases ($75/1M tokens)

### 4. Parts Reconciliation
**Status**: Code exists, not tested

**Components**:
- `src/reconciliation/part_matcher.py` - Fuzzy match to `pms_parts` table
- `src/reconciliation/shopping_matcher.py` - Match to shopping lists
- `src/reconciliation/order_matcher.py` - Match to purchase orders
- `src/reconciliation/suggestion_ranker.py` - Score and rank matches

### 5. Authentication
**Status**: Implemented and tested locally, production untested

**Method**: Supabase JWT validation (changed from manual JWT in this session)

**Critical Change** (commits 87275e4, fc559c1):
- **Before**: Manual JWT decode with `jwt.decode(token, settings.jwt_secret, ...)`
- **After**: Supabase client validation with `supabase.auth.get_user(token)`
- **Why**: Eliminates JWT_SECRET synchronization issues

**Auth Context**:
```python
class AuthContext:
    user_id: UUID
    yacht_id: UUID
    role: str  # "crew", "chief_engineer", "captain", "manager"
    email: str
```

**User Metadata Required**:
- Users MUST have `yacht_id` in Supabase user_metadata
- Set during signup or via admin API
- Without it, authentication fails with 403

---

## Database Schema

### Primary Table: `pms_image_uploads`

**Critical Column Name Issue** (fixed in commits 351b1a9, 9b9dce2):
- ❌ Migration created: `image_id` (UUID, primary key)
- ✅ Code expects: `id` (UUID, primary key)
- **Resolution**: Code fixed to use `id` everywhere

**Schema** (37 columns total):
```sql
CREATE TABLE pms_image_uploads (
  -- Identity
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  yacht_id uuid NOT NULL,
  uploaded_by uuid NOT NULL,

  -- File metadata
  file_name text NOT NULL,
  mime_type text,
  file_size_bytes bigint,
  sha256_hash text,  -- For deduplication
  storage_bucket text,
  storage_path text,

  -- Image properties
  width integer,
  height integer,
  blur_score float,

  -- OCR results
  ocr_raw_text text,
  ocr_confidence float,
  ocr_engine text,  -- "paddleocr", "google_vision", etc.
  ocr_processing_time_ms integer,
  ocr_line_count integer,
  ocr_word_count integer,

  -- Extracted entities
  extracted_entities jsonb,  -- {order_number, tracking, supplier, etc.}

  -- Status tracking
  validation_stage text,  -- "validated", "failed", "pending"
  extraction_status text,

  -- Timestamps
  uploaded_at timestamptz DEFAULT now(),
  ocr_completed_at timestamptz,
  processed_at timestamptz,
  deleted_at timestamptz
);

-- Critical indexes
CREATE INDEX idx_pms_image_uploads_yacht_id ON pms_image_uploads(yacht_id);
CREATE UNIQUE INDEX idx_pms_image_uploads_yacht_sha256
  ON pms_image_uploads(yacht_id, sha256_hash)
  WHERE sha256_hash IS NOT NULL;
```

**RLS Status**: NOT ENABLED
- Table has no RLS policies
- All queries must manually filter by `yacht_id`
- Code currently uses service role key (bypasses RLS)

### Other Tables (Referenced but Not Managed)

These tables are assumed to exist in the PMS database but are NOT created by this service:

- `pms_parts` - Parts catalog for reconciliation
- `pms_work_orders` - Work orders
- `pms_equipment` - Equipment registry
- `pms_shopping_lists` - Active shopping lists
- `pms_purchase_orders` - PO records

**Risk**: This service has no migration control over these tables.

---

## Migrations

### Applied Migrations

1. **`20260109_atomic_operations.sql`**
   - Purpose: Atomic transaction helpers
   - Status: Applied (assumed)

2. **`20260122_add_ocr_fields.sql`**
   - Purpose: Add OCR result columns
   - Status: Applied (assumed)

3. **`20260122_fix_image_uploads_schema.sql`**
   - Purpose: Complete schema with all 37 columns
   - Status: **NOT APPLIED TO PRODUCTION**
   - Reason: Uses `image_id` but code expects `id`
   - Action Required: Rewrite migration or verify production schema

**Critical Issue**: Production database schema unknown. Code was fixed to match whatever exists, but migration is out of sync.

---

## API Endpoints

### Core Routes (`src/routes/`)

#### Upload Endpoint
```
POST /api/v1/images/upload
```
**Handler**: `receiving_handler.py::process_upload()`
**Auth**: Required (JWT)
**Input**:
- `files`: File[] (max 10 files)
- `upload_type`: "receiving" | "shipping_label" | "discrepancy" | "part_photo" | "finance"
- `session_id`: UUID (optional)

**Output**:
```json
{
  "status": "success",
  "images": [{
    "image_id": "uuid",
    "file_name": "7.png",
    "is_duplicate": false,
    "processing_status": "queued",
    "storage_path": "path/to/image.png"
  }]
}
```

**Status**: Implemented, tested locally, production untested

#### Other Endpoints (Code Exists, Not Tested)
- `GET /api/v1/images/{id}/status` - Check processing status
- `POST /api/v1/receiving/sessions` - Create receiving session
- `GET /api/v1/receiving/sessions/{id}` - Get session + draft lines
- `POST /api/v1/receiving/sessions/{id}/commit` - Commit (HOD only)
- `POST /api/v1/labels/generate` - Generate label PDF

---

## Configuration

### Environment Variables

**Required (Service Won't Start Without These)**:
```bash
NEXT_PUBLIC_SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGci...
```

**OCR Feature Flags** (added this session):
```bash
ENABLE_GOOGLE_VISION=true   # Recommended for 512MB RAM plans
ENABLE_TESSERACT=true       # Fallback
ENABLE_PADDLEOCR=false      # Needs 2GB RAM minimum
ENABLE_SURYA=false          # Needs 4GB RAM
ENABLE_AWS_TEXTRACT=false   # Not implemented
```

**OCR API Keys** (if cloud engines enabled):
```bash
GOOGLE_VISION_API_KEY=AIzaSyC...
```

**Optional**:
```bash
OPENAI_API_KEY=sk-proj-...       # For LLM normalization
MAX_UPLOADS_PER_HOUR=50          # Rate limit
MAX_FILE_SIZE_MB=15              # Upload size limit
DQS_THRESHOLD=70.0               # Document quality score
MIN_IMAGE_WIDTH=800              # Min dimensions
MIN_IMAGE_HEIGHT=600
```

### Configuration Files

- `.env.example` - Template (59 variables)
- `src/config.py` - Settings class with Pydantic validation
- `render.yaml` - Render.com deployment config
- `requirements.txt` - Python dependencies (42 packages)
- `Dockerfile` - Container definition

---

## Deployment

### Production Environment

**Host**: Render.com
**URL**: https://image-processing-givq.onrender.com
**Service ID**: `srv-d5gou9qdbo4c73dg61u0`
**Plan**: Starter (512 MB RAM, $7/month)
**Region**: Oregon
**Auto-deploy**: Enabled (branch: main)

### Deployment Status

**Last Deployed Commit**: Unknown (auto-deploy may or may not be working)

**Recent Commits** (not verified in production):
- `3af9ce7` - Fixed `render.yaml` repo field (may enable auto-deploy)
- `9b9dce2` - Fixed database column names (`id` vs `image_id`)
- `fc559c1` - Fixed OCR factory usage in handler
- `34915aa` - Added OCR feature flags

**Critical Issue**: Auto-deploy configuration uncertain. GitHub webhook status unknown.

### Health Check

```bash
curl https://image-processing-givq.onrender.com/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "environment": "production"
}
```

**Last Known Status** (from local testing only):
- Local Docker: ✅ Working
- Production Render: ❓ Unknown

---

## Testing

### Test Coverage

**Unit Tests**: None exist
**Integration Tests**: None exist
**E2E Tests**: None exist

**Manual Testing Performed This Session**:
- Local Docker container with feature flags: ✅ Passed
- Supabase authentication: ✅ Passed
- Google Vision OCR: ✅ Passed (tested API key directly)
- Database writes: ✅ Passed (created duplicate record)
- Production deployment: ❌ Not tested

### Test Files Created (Not Committed)

```
test_local_docker.sh       # Docker build + run script
test_local_auth.py         # Authentication test
.env.local                 # Local test environment
```

**Location**: `/Users/celeste7/Documents/Image-processing/`

---

## Known Issues

### Critical Issues

1. **Production Deployment Unverified**
   - Code pushed to GitHub
   - Auto-deploy status unknown
   - Last production test: Never
   - Risk: Production may be broken

2. **Database Schema Mismatch**
   - Migration uses `image_id`
   - Code uses `id`
   - Production schema unknown
   - Migration `20260122_fix_image_uploads_schema.sql` never applied

3. **No RLS Policies**
   - `pms_image_uploads` table has no RLS
   - Code uses service role key (bypasses RLS anyway)
   - Manual `yacht_id` filtering in every query
   - Risk: Human error could expose yacht data

4. **Auto-Deploy Configuration Uncertain**
   - `render.yaml` has `repo` field (added this session)
   - GitHub webhook status unknown
   - Manual deploys may be required
   - No CI/CD pipeline

### Medium Issues

5. **No User Metadata Migration**
   - Authentication requires `yacht_id` in user_metadata
   - No script to set this for existing users
   - Users without metadata get 403 errors

6. **OCR Engine RAM Requirements Not Enforced**
   - PaddleOCR needs 500MB but service has 512MB total
   - No memory guards or health checks
   - Will cause 502 errors if wrong engine enabled

7. **Test Files at Root Level**
   - 100+ test scripts/docs in repository root
   - Not in `.gitignore`
   - Makes repository hard to navigate

8. **LLM Pipeline Untested**
   - Entire extraction/reconciliation pipeline exists
   - Zero testing done
   - Unknown if it works at all

### Minor Issues

9. **Duplicate Documentation**
   - 59 markdown files at root
   - Many redundant or from previous sessions
   - No clear "source of truth" document

10. **No Monitoring or Alerts**
    - No error tracking (Sentry DSN optional)
    - No performance monitoring
    - No cost tracking for LLM usage
    - No alerting if service down

---

## Dependencies

### Python Packages (42 total)

**Core** (5):
- `fastapi==0.115.0` - Web framework
- `uvicorn==0.32.1` - ASGI server
- `pydantic==2.10.3` - Data validation
- `supabase==2.12.0` - Database client
- `python-multipart==0.0.20` - File upload handling

**OCR Engines** (6):
- `paddleocr==2.9.2` - Primary OCR (94% accuracy)
- `pytesseract==0.3.13` - Fallback OCR
- `surya-ocr==0.7.0` - High-quality OCR (not used)
- `opencv-python==4.10.0.84` - Image preprocessing
- `pillow==11.0.0` - Image handling
- `pdfplumber==0.11.4` - PDF text extraction

**AI/LLM** (1):
- `openai==1.59.5` - GPT normalization

**Utilities** (30):
- `rapidfuzz` - Fuzzy string matching
- `qrcode` - QR code generation
- `reportlab` - PDF generation
- ... (27 more transitive dependencies)

---

## File Structure Reality Check

### What Exists vs README

**README Claims** (outdated):
```
Image-processing/
├── src/
│   ├── intake/
│   ├── ocr/
│   ├── extraction/
│   ├── reconciliation/
│   ├── commit/
│   ├── label_generation/
│   ├── middleware/
│   ├── handlers/
│   ├── routes/
│   └── models/
├── tests/
├── fixtures/
└── docs/
```

**Actual Reality**:
```
Image-processing/
├── src/                   ✅ Exists (60 Python files)
├── migrations/            ✅ Exists (3 files, out of sync)
├── tests/                 ✅ Exists (25 test files, never run)
├── fixtures/              ❌ Missing
├── docs/                  ❌ Missing
├── schemas/               ❌ Missing
├── [59 .md files]         ⚠️ Clutter at root level
├── [100+ test scripts]    ⚠️ Never committed
└── [Various JSON dumps]   ⚠️ OCR test results
```

---

## Security

### Authentication Method

**Current**: Supabase client JWT validation
- Method: `supabase.auth.get_user(token)`
- No JWT_SECRET needed
- Validates signature internally
- Requires user metadata: `yacht_id`, `role`

**Previous** (before this session):
- Manual JWT decode with `PyJWT`
- Required `JWT_SECRET` environment variable
- Prone to configuration mismatches

### Authorization

**Role-Based Access** (not enforced):
- `crew` - Can upload
- `chief_engineer`, `captain`, `manager` (HOD) - Can commit sessions
- `service_role` - Background jobs

**Implementation**:
```python
def is_hod(auth: AuthContext) -> bool:
    return auth.role in ["chief_engineer", "captain", "manager"]
```

**Critical**: Role enforcement not tested in production.

### Data Isolation

**Yacht Isolation** (manual, not RLS):
- Every query manually filters by `yacht_id`
- Uses service role key (no RLS enforcement)
- No RLS policies exist on any table

**Deduplication**:
- SHA256 hash per file
- Unique constraint: `(yacht_id, sha256_hash)`
- Prevents duplicate storage per yacht

### Secrets

**Stored in Render Environment Variables**:
- `SUPABASE_SERVICE_ROLE_KEY` - Full database access
- `GOOGLE_VISION_API_KEY` - OCR API access
- `OPENAI_API_KEY` - LLM API access

**Never Stored**:
- User passwords (handled by Supabase)
- JWT secrets (no longer needed)

---

## Cost Analysis

### Current Configuration (Starter Plan + Google Vision)

**Infrastructure**:
- Render Starter: $7/month
- Supabase Free Tier: $0/month

**Per-Image Costs** (with Google Vision):
- OCR: $0.0015 per image ($1.50 per 1000)
- LLM (if triggered): $0.02-0.15 per session
- Storage: Negligible

**Monthly Cost Estimate** (5000 images):
- Render: $7
- Google Vision: $7.50
- LLM (30% of sessions): ~$5
- **Total**: ~$20/month

### Alternative: Standard Plan + PaddleOCR

**Infrastructure**:
- Render Standard: $25/month (2GB RAM)
- Supabase Free Tier: $0/month

**Per-Image Costs**:
- OCR: $0 (self-hosted)
- LLM: $0.02-0.15 per session
- **Total**: $25-30/month (flat)

**Break-even**: ~12,000 images/month

---

## What Works

1. ✅ Local Docker testing environment
2. ✅ Supabase client authentication
3. ✅ OCR factory with feature flags
4. ✅ Google Vision OCR integration
5. ✅ Database writes (basic)
6. ✅ Deduplication logic
7. ✅ File validation (type, size, quality)
8. ✅ Rate limiting logic
9. ✅ Health check endpoint

---

## What Doesn't Work

1. ❌ Production deployment (untested)
2. ❌ RLS policies (don't exist)
3. ❌ LLM extraction pipeline (untested)
4. ❌ Reconciliation logic (untested)
5. ❌ Commit flow (untested)
6. ❌ Label generation (untested)
7. ❌ Auto-deploy (configuration uncertain)
8. ❌ Monitoring/alerting (not configured)
9. ❌ Test suite (exists but never run)
10. ❌ User metadata setup (no migration tool)

---

## What Is Uncertain

1. ❓ Production database schema (matches code? uses `id` or `image_id`?)
2. ❓ GitHub webhook status (exists? working?)
3. ❓ Render auto-deploy (actually triggering?)
4. ❓ Environment variables in Render (all set correctly?)
5. ❓ OpenAI LLM models (do `gpt-4.1-*` models exist?)
6. ❓ Other PMS tables (do they exist? correct schema?)
7. ❓ Frontend integration (exists? calls this API?)

---

## Critical Files Inventory

### Source Code (60 files)

**Core Entry Points**:
- `src/main.py` - FastAPI application
- `src/config.py` - Configuration management

**Handlers** (5):
- `src/handlers/receiving_handler.py` - **Primary handler**
- `src/handlers/label_handler.py`
- `src/handlers/photo_handler.py`
- `src/handlers/document_handler.py`
- `src/handlers/label_generation_handler.py`

**Critical Modules**:
- `src/middleware/auth.py` - Authentication (changed this session)
- `src/ocr/ocr_factory.py` - OCR engine selection (added this session)
- `src/intake/deduplicator.py` - Duplicate detection (fixed this session)
- `src/intake/rate_limiter.py` - Rate limiting (fixed this session)
- `src/database.py` - Supabase client initialization

### Configuration (4 files)

- `render.yaml` - Render deployment (updated this session)
- `.env.example` - Environment template (updated this session)
- `requirements.txt` - Dependencies (42 packages)
- `Dockerfile` - Container definition

### Migrations (3 files)

- `20260109_atomic_operations.sql` - Status unknown
- `20260122_add_ocr_fields.sql` - Status unknown
- `20260122_fix_image_uploads_schema.sql` - **NOT APPLIED, OUT OF SYNC**

### Documentation (59 files)

**Root level markdown chaos - needs consolidation**

Most Important:
- `README.md` - Project overview (outdated)
- `LOCAL_TESTING_SUCCESS.md` - This session's test results
- `OCR_SCALING_GUIDE.md` - Feature flags guide
- `RENDER_AUTO_DEPLOY_SETUP.md` - Auto-deploy troubleshooting

---

## Commit History Summary

**Last 10 Commits**:
1. `3af9ce7` - Fix render.yaml repo field
2. `9b9dce2` - Fix database column names
3. `fc559c1` - Fix OCR factory usage
4. `34915aa` - Add OCR feature flags
5. `32fa49b` - Force redeploy
6. `87275e4` - Supabase client auth
7. `96754af` - Handover document
8. `351b1a9` - Fix database schema
9. `3d2aefb` - Re-enable autoDeploy
10. `f0ff13f` - Toggle autoDeploy

**Pattern**: Many "force redeploy" commits suggest auto-deploy has been problematic.

---

## Summary

### Production Ready
- None (nothing verified in production)

### Locally Tested
- Image upload + validation
- Supabase authentication
- OCR factory with Google Vision
- Deduplication logic
- Rate limiting logic

### Code Exists But Untested
- LLM extraction pipeline
- Parts reconciliation
- Commit workflow
- Label generation
- Session management

### Missing Entirely
- RLS policies
- Monitoring/alerts
- User metadata setup tool
- Test suite execution
- CI/CD pipeline
- Production verification

---

**End of Inventory**
