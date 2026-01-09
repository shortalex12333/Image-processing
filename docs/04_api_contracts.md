# API Contracts
## Stable endpoint specifications for Image Processing Service

**Date**: 2026-01-09
**Version**: 1.0.0
**Base URL**: `https://image-processing-service.onrender.com/api/v1`

---

## Authentication

All endpoints require JWT authentication via `Authorization` header:

```
Authorization: Bearer <jwt_token>
```

JWT payload must contain:
```json
{
  "sub": "user_uuid",
  "yacht_id": "yacht_uuid",
  "role": "crew" | "hod" | "service_role"
}
```

---

## Common Error Response

All errors follow this schema:

```json
{
  "status": "error",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "message": "Upload rate limit exceeded: 50 uploads in last hour",
  "details": {
    "current_count": 52,
    "limit": 50,
    "retry_after_seconds": 1800
  },
  "timestamp": "2026-01-09T15:30:00Z",
  "request_id": "req_abc123"
}
```

### Standard Error Codes

```
# Upload errors (400)
INVALID_FILE_TYPE
FILE_TOO_LARGE
IMAGE_TOO_SMALL
IMAGE_BLURRY
DUPLICATE_IMAGE

# Rate limiting (429)
RATE_LIMIT_EXCEEDED

# Authentication (401)
INVALID_TOKEN
TOKEN_EXPIRED
MISSING_TOKEN

# Authorization (403)
INSUFFICIENT_PERMISSIONS
YACHT_ISOLATION_VIOLATION
INVALID_SESSION_STATE

# Not found (404)
SESSION_NOT_FOUND
IMAGE_NOT_FOUND
DRAFT_LINE_NOT_FOUND

# Processing errors (500)
OCR_FAILED
STORAGE_UPLOAD_FAILED
LLM_TIMEOUT
INTERNAL_ERROR
```

---

## 1. Upload Image/PDF

**Endpoint**: `POST /api/v1/images/upload`

**Purpose**: Upload image or PDF for processing

**Content-Type**: `multipart/form-data`

**Request Body**:
```
upload_type: string (required) - "receiving" | "shipping_label" | "discrepancy" | "part_photo"
files: File[] (required) - One or more files
session_id: string (optional) - Existing session UUID (for adding to session)
metadata: JSON (optional) - Additional metadata
```

**Request Example**:
```bash
curl -X POST https://api.example.com/api/v1/images/upload \
  -H "Authorization: Bearer <token>" \
  -F "upload_type=receiving" \
  -F "files=@packing_slip.pdf" \
  -F "files=@packing_slip_page2.jpg" \
  -F "session_id=uuid-here"
```

**Response 202 Accepted**:
```json
{
  "status": "success",
  "images": [
    {
      "image_id": "550e8400-e29b-41d4-a716-446655440000",
      "file_name": "packing_slip.pdf",
      "file_size_bytes": 245000,
      "mime_type": "application/pdf",
      "is_duplicate": false,
      "processing_status": "queued",
      "storage_path": "pms-receiving-images/yacht-uuid/image-uuid.pdf"
    }
  ],
  "session_id": null,
  "processing_eta_seconds": 30,
  "next_steps": {
    "action": "poll_status",
    "poll_url": "/api/v1/images/550e8400-e29b-41d4-a716-446655440000/status",
    "poll_interval_seconds": 3
  }
}
```

**Response 200 OK (Duplicate)**:
```json
{
  "status": "success",
  "images": [
    {
      "image_id": "existing-uuid",
      "file_name": "packing_slip.pdf",
      "is_duplicate": true,
      "existing_image_id": "existing-uuid",
      "processing_status": "completed",
      "message": "Image already exists, returning existing record"
    }
  ]
}
```

**Validation Rules**:
- Max 10 files per request
- Max 15MB per file
- Allowed MIME types: `image/jpeg`, `image/png`, `image/heic`, `application/pdf`
- Min resolution: 800x600 for images
- Blur check: variance of Laplacian > 100

**Rate Limit**: 50 uploads per hour per user per yacht

---

## 2. Get Image Status

**Endpoint**: `GET /api/v1/images/{image_id}/status`

**Purpose**: Poll processing status

**Response 200 OK (Processing)**:
```json
{
  "status": "processing",
  "image_id": "uuid",
  "validation_stage": "validated",
  "extraction_status": "processing",
  "progress": {
    "stage": "ocr",
    "percent_complete": 45,
    "estimated_remaining_seconds": 15
  },
  "metadata": {
    "queued_at": "2026-01-09T15:30:00Z",
    "started_at": "2026-01-09T15:30:02Z"
  }
}
```

**Response 200 OK (Completed)**:
```json
{
  "status": "completed",
  "image_id": "uuid",
  "validation_stage": "processed",
  "extraction_status": "completed",
  "session_id": "uuid",
  "result": {
    "draft_lines_created": 12,
    "matched_lines": 10,
    "unmatched_lines": 2,
    "processing_time_ms": 3400,
    "ocr_method": "tesseract",
    "llm_used": false,
    "cost_usd": 0.00
  },
  "next_steps": {
    "action": "view_session",
    "url": "/api/v1/receiving/sessions/uuid"
  }
}
```

**Response 200 OK (Failed)**:
```json
{
  "status": "failed",
  "image_id": "uuid",
  "extraction_status": "failed",
  "error": {
    "error_code": "OCR_FAILED",
    "message": "Failed to extract text after 3 attempts",
    "details": {
      "attempts": 3,
      "last_error": "Tesseract timeout"
    }
  },
  "next_steps": {
    "action": "retry_upload",
    "suggestion": "Try uploading a clearer image or PDF"
  }
}
```

---

## 3. Create Receiving Session

**Endpoint**: `POST /api/v1/receiving/sessions`

**Purpose**: Manually create empty receiving session

**Request Body**:
```json
{
  "metadata": {
    "supplier": "Marine Supply Co",
    "expected_delivery_date": "2026-01-09",
    "order_reference": "PO-2026-001"
  }
}
```

**Response 201 Created**:
```json
{
  "status": "success",
  "session_id": "uuid",
  "session_number": "RCV-2026-001",
  "session_status": "draft",
  "created_by": "user-uuid",
  "created_at": "2026-01-09T15:30:00Z",
  "metadata": {
    "supplier": "Marine Supply Co"
  }
}
```

---

## 4. Get Receiving Session

**Endpoint**: `GET /api/v1/receiving/sessions/{session_id}`

**Purpose**: Get session with all draft lines and suggestions

**Response 200 OK**:
```json
{
  "status": "success",
  "session": {
    "session_id": "uuid",
    "session_number": "RCV-2026-001",
    "status": "draft",
    "created_by": "user-uuid",
    "created_at": "2026-01-09T15:30:00Z",
    "images": [
      {
        "image_id": "uuid",
        "file_name": "packing_slip.pdf",
        "image_role": "packing_slip",
        "uploaded_at": "2026-01-09T15:30:00Z"
      }
    ],
    "draft_lines": [
      {
        "draft_line_id": "uuid",
        "line_number": 1,
        "quantity": 12.0,
        "unit": "ea",
        "description": "MTU Oil Filter Element",
        "extracted_part_number": "MTU-OF-4568",
        "is_verified": false,
        "verified_by": null,
        "verified_at": null,
        "source_image_id": "uuid",
        "suggested_part": {
          "part_id": "uuid",
          "part_number": "MTU-OF-4568",
          "part_name": "MTU Oil Filter Element",
          "manufacturer": "MTU",
          "confidence": 0.95,
          "match_reason": "exact_part_number",
          "current_stock": 8,
          "bin_location": "A-12-3"
        },
        "alternative_suggestions": [
          {
            "part_id": "uuid2",
            "part_number": "MTU-OF-4569",
            "part_name": "MTU Oil Filter (Alternative)",
            "confidence": 0.72,
            "match_reason": "fuzzy_description"
          }
        ],
        "shopping_list_match": {
          "item_id": "uuid",
          "quantity_requested": 12,
          "quantity_approved": 12,
          "status": "approved"
        },
        "has_discrepancy": false,
        "discrepancy_type": null,
        "discrepancy_photos": []
      }
    ],
    "summary": {
      "total_lines": 12,
      "verified_lines": 0,
      "matched_lines": 10,
      "unmatched_lines": 2,
      "lines_with_discrepancies": 0,
      "ready_to_commit": false
    }
  }
}
```

---

## 5. Verify Draft Line

**Endpoint**: `PATCH /api/v1/receiving/sessions/{session_id}/lines/{line_id}/verify`

**Purpose**: Mark draft line as verified (checkbox checked)

**Request Body**:
```json
{
  "verified": true,
  "matched_part_id": "uuid",
  "quantity_override": null,
  "notes": "Verified quantity and part match"
}
```

**Response 200 OK**:
```json
{
  "status": "success",
  "draft_line": {
    "draft_line_id": "uuid",
    "is_verified": true,
    "verified_by": "user-uuid",
    "verified_at": "2026-01-09T15:35:00Z",
    "matched_part_id": "uuid",
    "quantity": 12.0
  },
  "session_summary": {
    "verified_lines": 1,
    "total_lines": 12,
    "ready_to_commit": false
  }
}
```

---

## 6. Update Draft Line Match

**Endpoint**: `PATCH /api/v1/receiving/sessions/{session_id}/lines/{line_id}/match`

**Purpose**: Change which part the line matches to

**Request Body**:
```json
{
  "part_id": "different-uuid",
  "match_reason": "user_override"
}
```

**Response 200 OK**:
```json
{
  "status": "success",
  "draft_line": {
    "draft_line_id": "uuid",
    "matched_part_id": "different-uuid",
    "match_confidence": 1.0,
    "match_reason": "user_override"
  }
}
```

---

## 7. Mark Draft Line Discrepancy

**Endpoint**: `POST /api/v1/receiving/sessions/{session_id}/lines/{line_id}/discrepancy`

**Purpose**: Flag line as damaged/missing/incorrect

**Request Body**:
```json
{
  "discrepancy_type": "damaged",
  "notes": "Box crushed during shipping, items inside broken",
  "affected_quantity": 2.0
}
```

**Response 200 OK**:
```json
{
  "status": "success",
  "draft_line": {
    "draft_line_id": "uuid",
    "has_discrepancy": true,
    "discrepancy_type": "damaged",
    "affected_quantity": 2.0
  },
  "next_steps": {
    "action": "upload_discrepancy_photo",
    "required": true,
    "url": "/api/v1/images/upload",
    "params": {
      "upload_type": "discrepancy",
      "session_id": "session-uuid",
      "line_id": "line-uuid"
    }
  }
}
```

**Discrepancy Types**:
- `damaged` - Items damaged during shipping
- `incorrect` - Wrong items received
- `missing` - Items missing from shipment
- `quantity_mismatch` - Received different quantity than listed

---

## 8. Commit Receiving Session

**Endpoint**: `POST /api/v1/receiving/sessions/{session_id}/commit`

**Purpose**: Create immutable receiving records and update inventory

**Role Required**: **HOD**

**Request Body**:
```json
{
  "commit_notes": "All items verified and ready for inventory",
  "auto_generate_labels": true
}
```

**Response 200 OK**:
```json
{
  "status": "success",
  "receiving_event": {
    "event_id": "uuid",
    "event_number": "RCV-EVT-2026-001",
    "session_id": "session-uuid",
    "received_at": "2026-01-09T15:40:00Z",
    "received_by": "user-uuid",
    "total_lines": 12,
    "lines_committed": 10,
    "lines_with_discrepancies": 2
  },
  "inventory_updates": {
    "parts_updated": 10,
    "total_quantity_added": 87.0,
    "transactions_created": 10
  },
  "finance_transactions": {
    "transactions_created": 10,
    "total_cost_usd": 486.50
  },
  "shopping_list_updates": {
    "items_fulfilled": 8,
    "items_partially_fulfilled": 2
  },
  "labels": {
    "auto_generated": true,
    "label_pdf_id": "uuid",
    "pdf_url": "https://storage.../signed-url...",
    "label_count": 10,
    "expires_at": "2026-01-09T16:40:00Z"
  },
  "audit": {
    "audit_log_id": "uuid",
    "signature": "sha256:abc123..."
  }
}
```

**Validation Rules**:
- Session must be in `draft`, `reconciling`, or `verifying` state
- At least 1 line must be verified
- All discrepancies must have photos attached
- User must have HOD role
- Session must belong to user's yacht

**Response 403 Forbidden (Non-HOD)**:
```json
{
  "status": "error",
  "error_code": "INSUFFICIENT_PERMISSIONS",
  "message": "Only HOD can commit receiving sessions",
  "details": {
    "required_role": "hod",
    "user_role": "crew"
  }
}
```

---

## 9. Generate Labels

**Endpoint**: `POST /api/v1/receiving/events/{event_id}/generate-labels`

**Purpose**: Generate QR code label PDF for committed receiving event

**Request Body**:
```json
{
  "label_per_unit": false,
  "include_bin_location": true,
  "label_format": "4x6"
}
```

**Response 200 OK**:
```json
{
  "status": "success",
  "label_pdf_id": "uuid",
  "pdf_url": "https://storage.../signed-url...",
  "label_count": 12,
  "file_size_bytes": 245000,
  "expires_at": "2026-01-09T16:40:00Z",
  "metadata": {
    "format": "4x6",
    "labels_per_unit": false,
    "generated_at": "2026-01-09T15:40:00Z",
    "generated_by": "user-uuid"
  }
}
```

**Label Formats**:
- `4x6` - Standard shipping label size (default)
- `2x4` - Small label
- `letter` - 8.5x11" page with multiple labels

---

## 10. Attach Discrepancy Photo

**Endpoint**: `POST /api/v1/images/upload`

**Purpose**: Upload photo of damaged/missing items

**Content-Type**: `multipart/form-data`

**Request Body**:
```
upload_type: "discrepancy"
files: File (required)
session_id: string (required)
line_id: string (required)
discrepancy_type: "damaged" | "incorrect" | "missing"
notes: string (optional)
```

**Response 200 OK**:
```json
{
  "status": "success",
  "images": [
    {
      "image_id": "uuid",
      "file_name": "damaged_item.jpg",
      "is_duplicate": false,
      "attached_to": {
        "entity_type": "receiving_draft_line",
        "entity_id": "line-uuid"
      },
      "discrepancy_type": "damaged"
    }
  ]
}
```

---

## 11. Attach Part Photo

**Endpoint**: `POST /api/v1/images/upload`

**Purpose**: Upload photo of part for catalog

**Content-Type**: `multipart/form-data`

**Request Body**:
```
upload_type: "part_photo"
files: File (required)
part_id: string (required)
set_as_primary: boolean (optional, default: false)
```

**Response 200 OK**:
```json
{
  "status": "success",
  "images": [
    {
      "image_id": "uuid",
      "file_name": "mtu_filter.jpg",
      "is_duplicate": false,
      "attached_to": {
        "entity_type": "part",
        "entity_id": "part-uuid",
        "part_number": "MTU-OF-4568"
      },
      "image_role": "primary_photo",
      "is_primary": true
    }
  ]
}
```

---

## 12. Process Shipping Label

**Endpoint**: `POST /api/v1/images/upload`

**Purpose**: Extract metadata from shipping label

**Content-Type**: `multipart/form-data`

**Request Body**:
```
upload_type: "shipping_label"
files: File (required)
```

**Response 200 OK**:
```json
{
  "status": "success",
  "images": [
    {
      "image_id": "uuid",
      "file_name": "fedex_label.jpg",
      "processing_status": "completed",
      "extracted_metadata": {
        "document_type": "shipping_label",
        "classification_confidence": 0.98,
        "carrier": "FedEx",
        "tracking_number": "1234567890",
        "supplier_name": "Marine Supply Co",
        "po_number": "PO-2026-001",
        "ship_to_address": "...",
        "ship_from_address": "..."
      },
      "suggested_orders": [
        {
          "order_id": "uuid",
          "order_number": "PO-2026-001",
          "supplier": "Marine Supply Co",
          "confidence": 0.95,
          "match_reason": "exact_po_match"
        }
      ],
      "auto_attached": true,
      "attached_to": {
        "entity_type": "order",
        "entity_id": "order-uuid"
      }
    }
  ]
}
```

---

## 13. Health Check

**Endpoint**: `GET /health`

**Purpose**: Check service health

**Authentication**: Not required

**Response 200 OK**:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-01-09T15:30:00Z",
  "components": {
    "database": "ok",
    "storage": "ok",
    "ocr": "ok",
    "llm": "ok"
  },
  "uptime_seconds": 86400
}
```

**Response 503 Service Unavailable**:
```json
{
  "status": "unhealthy",
  "version": "1.0.0",
  "timestamp": "2026-01-09T15:30:00Z",
  "components": {
    "database": "ok",
    "storage": "ok",
    "ocr": "failed",
    "llm": "degraded"
  },
  "errors": [
    "OCR service unavailable: Tesseract binary not found",
    "LLM service degraded: High latency (5s avg)"
  ]
}
```

---

## Webhooks (Future)

### Webhook: Processing Complete

**Event**: `image.processing.completed`

**Payload**:
```json
{
  "event": "image.processing.completed",
  "event_id": "evt_abc123",
  "timestamp": "2026-01-09T15:30:00Z",
  "data": {
    "image_id": "uuid",
    "session_id": "uuid",
    "processing_status": "completed",
    "draft_lines_created": 12
  }
}
```

### Webhook: Session Committed

**Event**: `receiving.session.committed`

**Payload**:
```json
{
  "event": "receiving.session.committed",
  "event_id": "evt_abc124",
  "timestamp": "2026-01-09T15:40:00Z",
  "data": {
    "session_id": "uuid",
    "receiving_event_id": "uuid",
    "event_number": "RCV-EVT-2026-001",
    "lines_committed": 10,
    "inventory_updated": true
  }
}
```

---

## Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| POST /images/upload | 50 requests | 1 hour |
| GET /images/{id}/status | 300 requests | 5 minutes |
| PATCH /lines/{id}/verify | 100 requests | 1 minute |
| POST /sessions/{id}/commit | 10 requests | 1 minute |

**Rate Limit Headers**:
```
X-RateLimit-Limit: 50
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1704814200
```

---

## Pagination (List Endpoints)

**Request**:
```
GET /api/v1/receiving/sessions?limit=20&offset=0&status=draft
```

**Response**:
```json
{
  "status": "success",
  "data": [...],
  "pagination": {
    "total": 150,
    "limit": 20,
    "offset": 0,
    "has_more": true
  }
}
```

---

## Versioning

API version is included in URL path: `/api/v1/...`

**Breaking changes** will increment major version: `/api/v2/...`

**Non-breaking changes** (new fields, new optional parameters) do not increment version.

---

## JSON Schemas

See `/schemas` directory for complete JSON schemas:

- `schemas/upload_request.json`
- `schemas/upload_response.json`
- `schemas/session_response.json`
- `schemas/draft_line.json`
- `schemas/commit_request.json`
- `schemas/commit_response.json`
- `schemas/error_response.json`

These can be used for request/response validation and generating client SDKs.

---

**Next**: See `05_model_strategy.md` for LLM usage and cost control strategy.
