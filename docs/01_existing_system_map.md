# Cloud_PMS Existing System Map
## Understanding the document ingestion pipeline (for reuse patterns)

**Date**: 2026-01-09
**Branch**: universal_v1
**Purpose**: Map existing extraction patterns to reuse for image processing

---

## System Overview

Cloud_PMS has a mature **5-stage extraction pipeline** for processing text documents:

```
Text Input → Clean → Regex → Controller → AI (conditional) → Merge → Output
```

This pipeline is located in: `/apps/api/extraction/`

---

## Architecture Breakdown

### 1. Module Structure

```
apps/api/
├── extraction/              # Core extraction pipeline
│   ├── orchestrator.py          # Main coordinator
│   ├── text_cleaner.py          # Stage 0: Normalization
│   ├── regex_extractor.py       # Stage 1: Deterministic extraction
│   ├── coverage_controller.py   # Stage 2: Decision making
│   ├── ai_extractor_openai.py   # Stage 3: AI (escalation)
│   ├── entity_merger.py         # Stage 4: Merge & validate
│   └── extraction_config.py     # Configuration
│
├── handlers/                # Business logic handlers
│   ├── work_order_mutation_handlers.py
│   ├── inventory_handlers.py
│   ├── handover_handlers.py
│   └── manual_handlers.py
│
├── routes/                  # API endpoints (FastAPI)
│   └── p0_actions_routes.py
│
├── middleware/              # Auth & validation
│   └── auth.py
│
├── action_router/           # Request routing & validation
│   ├── validators.py            # JWT & yacht isolation
│   ├── registry.py
│   └── dispatchers/
│
└── integrations/            # External services (n8n, etc.)
```

### 2. Key Design Patterns

#### Pattern A: **Cost-Conscious Escalation**

```python
# Stage 1: Cheap deterministic (regex + gazetteer)
regex_entities, covered_spans = regex_extractor.extract(text)

# Stage 2: Coverage decision
decision = controller.decide(cleaned, regex_entities, text)

# Stage 3: AI only if needed
if decision.needs_ai:
    ai_entities = ai_extractor.extract(text, decision.uncovered_spans)
```

**Key insight**: AI is invoked only when coverage is insufficient. Typical AI invocation rate: 15-30%.

#### Pattern B: **Metrics Tracking**

```python
@dataclass
class ExtractionMetrics:
    total_ms: float
    clean_ms: float
    regex_ms: float
    controller_ms: float
    ai_ms: float
    merge_ms: float
    needs_ai: bool
    coverage: float
    ai_invocations: int
    total_requests: int
```

**Key insight**: Every stage is timed. Cost per request is trackable.

#### Pattern C: **Provenance Tracking**

```python
entities_provenance = {
    'part_number': [
        {
            'text': 'MTU-123',
            'source': 'regex',           # or 'gazetteer' or 'ai'
            'confidence': 0.95,
            'span': (10, 17)
        }
    ]
}
```

**Key insight**: Know where each entity came from. Downstream validation can trust regex more than AI.

#### Pattern D: **Deterministic Response Shape**

```python
{
    'schema_version': '0.2.2',
    'entities': {
        'part_number': ['MTU-123', 'KOH-456'],
        'manufacturer': ['MTU', 'Kohler']
    },
    'entities_provenance': {...},
    'unknown_term': ['unknown1', 'unknown2'],
    'metadata': {
        'needs_ai': False,
        'coverage': 0.92,
        'latency_ms': {...}
    }
}
```

**Key insight**: No "confidence" in the main response. Either extracted or not. Provenance is metadata.

---

## 3. Authentication & Authorization

### JWT Validation

```python
from action_router.validators import validate_jwt

jwt_result = validate_jwt(authorization_header)
if not jwt_result.valid:
    raise HTTPException(status_code=401, detail=jwt_result.error.message)

user_context = jwt_result.context  # Contains: yacht_id, user_id, role
```

### Yacht Isolation

```python
from action_router.validators import validate_yacht_isolation

isolation_result = validate_yacht_isolation(yacht_id, user_context['yacht_id'])
if not isolation_result.valid:
    raise HTTPException(status_code=403, detail=isolation_result.error.message)
```

**Key insight**: All database queries are yacht-scoped. Multi-tenant at the query level.

---

## 4. Error Handling Patterns

### Error Codes (deterministic, actionable)

```python
{
    "status": "error",
    "error_code": "ENTITY_NOT_FOUND",      # or VALIDATION_ERROR, INTERNAL_ERROR, etc.
    "message": "Fault with ID 123 not found",
    "details": {...}
}
```

### Common Error Codes

- `ENTITY_NOT_FOUND` - Resource doesn't exist
- `VALIDATION_ERROR` - Input validation failed
- `INVALID_ENTITY_TYPE` - Enum validation failed
- `INTERNAL_ERROR` - Unexpected error (logged, but not exposed)
- `UNAUTHORIZED` - Auth failed
- `FORBIDDEN` - Lacks permission

**Key insight**: Errors are structured. No raw exception messages to client.

---

## 5. Logging Patterns

```python
import logging

logger = logging.getLogger(__name__)

# Success
logger.info("✅ Work order created", extra={
    'work_order_id': wo_id,
    'fault_id': fault_id,
    'user_id': user_id
})

# Warning
logger.warning("⚠️ AI extractor unavailable, using deterministic only")

# Error
logger.error("❌ Failed to process image", extra={
    'image_id': image_id,
    'error': str(e)
}, exc_info=True)
```

**Key insight**: Structured logging with context. Use emoji for visual scanning in logs.

---

## 6. Database Patterns (Supabase)

### Client Initialization

```python
from supabase import create_client

supabase = create_client(
    os.getenv("NEXT_PUBLIC_SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_ROLE_KEY")  # Backend uses service_role
)
```

### Query Pattern

```python
# SELECT with RLS enforcement
result = supabase.table('pms_faults') \
    .select('*') \
    .eq('yacht_id', yacht_id) \
    .eq('id', fault_id) \
    .execute()

if not result.data:
    return {"status": "error", "error_code": "ENTITY_NOT_FOUND"}

fault = result.data[0]
```

### INSERT Pattern

```python
# INSERT with return
result = supabase.table('pms_work_orders').insert({
    'yacht_id': yacht_id,
    'fault_id': fault_id,
    'title': 'Fix MTU engine',
    'created_by': user_id
}).execute()

work_order = result.data[0]
```

**Key insight**: Service role bypasses RLS but queries still filter by yacht_id. Defense in depth.

---

## 7. Request/Response Models (Pydantic)

```python
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional

class ActionExecuteRequest(BaseModel):
    """Standardized request for all actions."""
    action: str = Field(..., description="Action name")
    context: Dict[str, Any] = Field(..., description="Yacht ID, user ID, role")
    payload: Dict[str, Any] = Field(..., description="Action-specific parameters")

class ActionExecuteResponse(BaseModel):
    """Standardized response."""
    status: str  # 'success' or 'error'
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    message: Optional[str] = None
```

**Key insight**: Standardize shapes. All actions follow same envelope.

---

## 8. Dependencies & Stack

**From `requirements.txt`:**

```
fastapi==0.115.0          # Web framework
uvicorn==0.32.1           # ASGI server
pydantic==2.10.3          # Request/response validation
supabase==2.12.0          # Database client
openai==1.59.5            # AI extraction (escalation only)
pytest==7.4.4             # Testing
```

**Deployment**: Render.com (Python/Docker)

---

## 9. What We Can Reuse for Image Processing

### ✅ Reuse directly:

1. **Folder structure**: `/src/intake`, `/src/ocr`, `/src/extraction`, `/src/reconciliation`, `/src/commit`
2. **Auth patterns**: JWT validation, yacht isolation
3. **Error handling**: Error codes, structured responses
4. **Logging patterns**: Structured logging with context
5. **Pydantic models**: Request/response standardization
6. **Supabase patterns**: Service role queries
7. **FastAPI routing**: Router structure
8. **Metrics tracking**: Timing, invocation rates
9. **Health checks**: Component availability
10. **Cost escalation**: Cheap first, AI only when needed

### 🔄 Adapt for images:

1. **Text cleaner** → **Image validator** (file type, size, dimensions)
2. **Regex extractor** → **OCR + heuristics** (Tesseract or cheap OCR)
3. **Coverage controller** → **Quality assessment** (OCR confidence, table detection)
4. **AI extractor** → **LLM normalization** (extract structured rows from OCR text)
5. **Entity merger** → **Draft line creator** (merge OCR + heuristics into draft_lines)

### ⚠️ New for images:

1. **SHA256 deduplication** (before storage write)
2. **Storage bucket coordination** (DB insert → storage upload)
3. **OCR stage** (extract text from images)
4. **Table detection** (identify tables in packing slips)
5. **Draft line workflow** (OCR → draft → checkbox → commit)
6. **Label PDF generation** (QR codes, receiving labels)
7. **Image-specific abuse protection** (rate limits, file validation)

---

## 10. Critical Differences: Documents vs Images

| Aspect | Document Ingestion | Image Processing |
|--------|-------------------|------------------|
| **Input** | Text (already extracted) | Binary image files |
| **First stage** | Text cleaning | File validation + OCR |
| **Deduplication** | Content hash | SHA256 hash |
| **Storage** | Reference only | Actual file upload |
| **Output** | Extracted entities | Draft lines for verification |
| **Workflow** | Single-pass extraction | Multi-stage (draft → verify → commit) |
| **Commit** | Immediate | Checkbox required |
| **Cost** | Mostly regex, some AI | OCR + optional AI normalization |

**Key difference**: Images require human verification (checkbox = truth). Documents can be ingested automatically.

---

## Summary: Patterns to Follow

1. **5-stage pipeline**: Intake → OCR → Extract → Assess → Normalize (conditional)
2. **Cost optimization**: Deterministic first, escalate only when needed
3. **Metrics tracking**: Time every stage, track AI invocation rate
4. **Provenance**: Know where each data point came from
5. **Error codes**: Actionable, deterministic error responses
6. **Yacht isolation**: Multi-tenant at query level
7. **Logging**: Structured with context
8. **Pydantic models**: Standardize request/response shapes
9. **Health checks**: Component availability monitoring
10. **Defense in depth**: Service role + explicit yacht_id filtering

---

## Files Examined

- `/apps/api/extraction/orchestrator.py` (main pipeline)
- `/apps/api/extraction/regex_extractor.py` (deterministic extraction)
- `/apps/api/extraction/coverage_controller.py` (decision logic)
- `/apps/api/extraction/ai_extractor_openai.py` (AI escalation)
- `/apps/api/routes/p0_actions_routes.py` (API structure)
- `/apps/api/requirements.txt` (dependencies)
- `/.env.example` (configuration)

---

**Next**: Design image pipeline sections (A-E) in `02_pipeline_sections.md`
