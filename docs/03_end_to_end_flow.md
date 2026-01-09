# End-to-End Flow: Section A (Receiving)
## Complete workflow from upload to commit

**Date**: 2026-01-09
**Purpose**: Define the full receiving workflow with all decision points
**Section**: A - Packing Slip / Receiving Note Processing

---

## Overview: The Full Journey

```
User uploads packing slip
    ↓
[1] Upload Service: Intake & Storage
    ↓
[2] Processing Worker: OCR → Extract → Normalize
    ↓
[3] Reconciliation Service: Match suggestions
    ↓
[4] Frontend: User verifies draft lines (checkbox)
    ↓
[5] Commit Service: Create receiving events + inventory
    ↓
[6] Label Generator: Generate QR labels (optional)
    ↓
Done: Inventory updated, audit trail complete
```

---

## Stage-by-Stage Flow

### Stage 1: Upload & Intake

**Endpoint**: `POST /api/v1/images/upload`

**Request**:
```json
{
  "upload_type": "receiving",
  "files": [/* FormData file objects */],
  "session_id": null  // or existing session UUID
}
```

**Process**:

```
1. Validate JWT token
   ↓ Extract: user_id, yacht_id, role
   ↓ Check: user is authenticated

2. Validate files
   FOR EACH file:
      ↓ Check MIME type (jpg, png, pdf, heic)
      ↓ Check size (< 15MB)
      ↓ Check dimensions (min 800x600 for images)
      ↓ Blur check (variance of Laplacian > threshold)
      ↓ Compute SHA256 hash

3. Deduplication check
   FOR EACH file:
      ↓ Query: pms_image_uploads WHERE sha256_hash=X AND yacht_id=Y
      IF exists:
         ↓ Return: {is_duplicate: true, existing_image_id: UUID}
         ↓ SKIP storage upload (cost savings)
      ELSE:
         ↓ Continue to step 4

4. Rate limit check
   ↓ Query: COUNT(*) FROM pms_image_uploads
      WHERE yacht_id=X AND uploaded_by=Y
      AND uploaded_at > NOW() - INTERVAL '1 hour'
   IF count >= 50:
      ↓ Return: {error_code: 'RATE_LIMIT_EXCEEDED'}
      ↓ BLOCK upload

5. Create DB record FIRST
   ↓ INSERT INTO pms_image_uploads:
      - yacht_id, uploaded_by, upload_ip_address
      - storage_bucket='pms-receiving-images'
      - storage_path='{yacht_id}/{image_id}.{ext}'
      - file_name, mime_type, file_size_bytes, sha256_hash
      - validation_stage='uploaded'
   ↓ Get: image_id

6. Upload to storage bucket
   ↓ Upload to: pms-receiving-images/{yacht_id}/{image_id}.{ext}
   IF upload fails:
      ↓ Mark: validation_stage='failed', validation_errors='storage_upload_failed'
   ELSE:
      ↓ Mark: validation_stage='validated'

7. Queue processing job
   ↓ Enqueue: {image_id, upload_type='receiving'}
   ↓ Return: {status: 'queued', image_id, processing_eta_seconds: 30}
```

**Response**:
```json
{
  "status": "success",
  "images": [
    {
      "image_id": "uuid",
      "file_name": "packing_slip.jpg",
      "is_duplicate": false,
      "processing_status": "queued"
    }
  ],
  "session_id": null,
  "next_steps": {
    "action": "poll_processing_status",
    "url": "/api/v1/images/{image_id}/status"
  }
}
```

**Error codes**:
- `RATE_LIMIT_EXCEEDED` - User uploaded 50+ images in last hour
- `DUPLICATE_IMAGE` - Image already exists (returns existing_image_id)
- `INVALID_FILE_TYPE` - File type not allowed
- `FILE_TOO_LARGE` - Exceeds 15MB limit
- `IMAGE_TOO_SMALL` - Resolution below 800x600
- `IMAGE_BLURRY` - Failed blur check
- `STORAGE_UPLOAD_FAILED` - Bucket write failed

---

### Stage 2: OCR & Structure Detection

**Triggered by**: Processing worker (background job)

**Process**:

```
1. Fetch image from storage
   ↓ Download: pms-receiving-images/{yacht_id}/{image_id}.{ext}
   ↓ Load into memory

2. Preprocessing (if image, not PDF)
   ↓ Deskew (detect rotation, correct)
   ↓ Binarize (convert to black/white for better OCR)
   ↓ Contrast adjustment
   ↓ Noise reduction

3. OCR Extraction
   IF Tesseract OCR:
      ↓ Run: pytesseract.image_to_string(image, config='--psm 6')
      ↓ Also get: pytesseract.image_to_data() for bounding boxes
   ELSE IF Cloud OCR (Google Vision):
      ↓ Call: vision.text_detection(image)
      ↓ Parse: response.text_annotations

   ↓ Store: ocr_raw_text in pms_image_uploads
   ↓ Update: validation_stage='validated'

4. Table Detection (Heuristics)
   ↓ Look for patterns:
      - Multiple columns of numbers
      - Repeated structure (qty, unit, description)
      - Header keywords: "quantity", "description", "item", "part"

   ↓ Use OpenCV line detection:
      - Detect horizontal/vertical lines
      - Identify table grid

   ↓ Calculate: table_confidence (0-1)

5. Row Extraction (Deterministic)
   IF table_confidence > 0.7:
      ↓ Use table parsing:
         - Split by detected rows
         - Map columns to fields (qty, unit, desc, part_number)
      ↓ Parse with regex:
         - Qty: \d+(\.\d+)?
         - Unit: (ea|box|case|pcs|lbs|kg|etc)
         - Part number: [A-Z0-9-]{5,20}

   ↓ Calculate: coverage = (parsed_rows / total_rows)

   ↓ Store: extracted_data JSON in pms_image_uploads
   ↓ Update: extraction_status='completed'
```

**Metrics tracked**:
```python
{
  "ocr_duration_ms": 1200,
  "preprocessing_duration_ms": 300,
  "table_detected": true,
  "table_confidence": 0.85,
  "rows_detected": 12,
  "rows_parsed": 10,
  "coverage": 0.83
}
```

---

### Stage 3: LLM Normalization (Conditional)

**Trigger**: `coverage < 0.8 OR table_confidence < 0.7`

**Process**:

```
1. Check if LLM needed
   IF coverage >= 0.8 AND table_confidence >= 0.7:
      ↓ SKIP LLM (cost savings)
      ↓ Go to Stage 4
   ELSE:
      ↓ Continue to LLM normalization

2. Prepare prompt
   ↓ Template: "Normalize this OCR text into structured line items.
      Extract for each row:
      - quantity (numeric)
      - unit (ea, box, case, etc)
      - description (string)
      - part_number (if present)

      Return JSON array only. If a row is unclear, include it with best guess."

   ↓ Combine: [prompt] + [ocr_raw_text] + [parsed_rows if any]

3. Call gpt-4.1-mini
   ↓ Request:
      model: "gpt-4.1-mini"
      messages: [{role: "user", content: prompt}]
      response_format: {type: "json_object"}
      max_tokens: 2000

   ↓ Parse response
   ↓ Validate schema (pydantic)

4. Fallback: Escalate to gpt-4.1
   IF gpt-4.1-mini fails OR confidence < 0.6:
      ↓ Try gpt-4.1 (stronger model)
      ↓ Same prompt, better reasoning

   IF still fails:
      ↓ Mark: extraction_status='failed'
      ↓ Store: validation_errors='llm_extraction_failed'
      ↓ Return partial results + manual_match_required=true

5. Cost tracking
   ↓ Increment: llm_calls_count
   ↓ Track: input_tokens, output_tokens, cost_usd
   ↓ Check hard cap: max 3 LLM calls per session
```

**LLM Response Format**:
```json
{
  "line_items": [
    {
      "line_number": 1,
      "quantity": 12.0,
      "unit": "ea",
      "description": "MTU Oil Filter Element",
      "part_number": "MTU-OF-4568"
    },
    {
      "line_number": 2,
      "quantity": 6.0,
      "unit": "box",
      "description": "Kohler Spark Plugs",
      "part_number": null
    }
  ],
  "confidence": 0.85,
  "notes": "Line 5 unclear, included as 'Unknown Item'"
}
```

---

### Stage 4: Reconciliation & Draft Creation

**Process**:

```
1. Create or fetch receiving session
   IF session_id provided:
      ↓ Fetch existing session
      ↓ Verify: status='draft' (can't add to committed sessions)
   ELSE:
      ↓ CREATE pms_receiving_session:
         - yacht_id, uploaded_by
         - session_number = generate_receiving_session_number()
         - status='draft'
      ↓ Get: session_id

2. For each extracted line item:

   A) Fuzzy match to pms_parts
      ↓ Use rapidfuzz on description
      ↓ Score: similarity(line.description, part.name)
      ↓ Filter: score > 0.8
      ↓ Also check: exact match on part_number if present
      ↓ Return top 3 matches

   B) Check pms_shopping_list_items
      ↓ Query: WHERE yacht_id=X AND status='approved'
      ↓ Match on: part_id OR description
      ↓ Prioritize: items with quantity_requested > quantity_received

   C) Check pms_purchase_order_items
      ↓ Query: Recent orders (last 90 days)
      ↓ Match on: part_id OR description
      ↓ Look for: expected deliveries

   D) Generate suggestion confidence
      IF exact part_number match:
         ↓ confidence = 0.95
      ELSE IF fuzzy description match > 0.9:
         ↓ confidence = fuzzy_score
      ELSE IF on shopping list:
         ↓ confidence = 0.85
      ELSE:
         ↓ confidence = 0.0 (no match)

3. Create draft lines
   FOR EACH line_item:
      ↓ INSERT INTO pms_receiving_draft_lines:
         - session_id
         - line_number
         - quantity, unit, description
         - extracted_part_number (if present)
         - suggested_part_id (best match, or null)
         - match_confidence
         - source_image_id
         - is_verified=false
      ↓ Store suggestions JSON:
         {
           "suggestions": [
             {part_id, part_number, part_name, confidence, source}
           ]
         }

4. Link images to session
   ↓ INSERT INTO pms_entity_images:
      - entity_type='receiving_session'
      - entity_id=session_id
      - image_id=uploaded_image_id
      - image_role='packing_slip'

5. Update image processing status
   ↓ UPDATE pms_image_uploads:
      - validation_stage='processed'
      - processed_by=service_role
      - processed_at=NOW()
```

**Output to frontend**:
```json
{
  "status": "success",
  "session_id": "uuid",
  "session_number": "RCV-2026-001",
  "session_status": "draft",
  "draft_lines": [
    {
      "draft_line_id": "uuid",
      "line_number": 1,
      "quantity": 12.0,
      "unit": "ea",
      "description": "MTU Oil Filter Element",
      "extracted_part_number": "MTU-OF-4568",
      "is_verified": false,
      "suggested_part": {
        "part_id": "uuid",
        "part_number": "MTU-OF-4568",
        "part_name": "MTU Oil Filter Element",
        "confidence": 0.95,
        "current_stock": 8,
        "on_shopping_list": true
      },
      "alternative_suggestions": [
        {
          "part_id": "uuid2",
          "part_number": "MTU-OF-4569",
          "confidence": 0.72
        }
      ]
    }
  ],
  "metadata": {
    "total_lines": 12,
    "matched_lines": 10,
    "unmatched_lines": 2,
    "processing_time_ms": 3400,
    "ocr_method": "tesseract",
    "llm_used": false
  }
}
```

---

### Stage 5: User Verification (Frontend Checkbox)

**UI Flow**:

```
1. Display draft lines table
   Columns:
   - ☐ Checkbox (verify)
   - Line #
   - Qty / Unit
   - Description
   - Suggested Part (dropdown to change)
   - Actions (edit, mark discrepancy)

2. User actions:

   A) Verify line (check checkbox)
      ↓ PATCH /api/v1/receiving/sessions/{id}/lines/{line_id}/verify
      ↓ Body: {verified_by: user_id}
      ↓ Backend: UPDATE pms_receiving_draft_lines
         SET is_verified=true, verified_by=user_id, verified_at=NOW()

   B) Change matched part
      ↓ User selects different part from dropdown
      ↓ PATCH /api/v1/receiving/sessions/{id}/lines/{line_id}/match
      ↓ Body: {part_id: selected_uuid}
      ↓ Backend: UPDATE draft line with new part_id

   C) Edit quantity
      ↓ User changes quantity value
      ↓ PATCH /api/v1/receiving/sessions/{id}/lines/{line_id}
      ↓ Body: {quantity: new_value}

   D) Mark discrepancy
      ↓ User clicks "Mark Damaged" or "Mark Missing"
      ↓ POST /api/v1/receiving/sessions/{id}/lines/{line_id}/discrepancy
      ↓ Body: {type: 'damaged', notes: 'box crushed'}
      ↓ Opens: photo upload flow (Section C)

3. Validation rules:
   - At least 1 line must be verified to commit
   - Discrepancies must have photo attached
   - All verified lines must have matched part_id OR be marked "create new part"

4. Ready to commit indicator:
   ↓ Check: all lines either verified OR marked "skip"
   ↓ Enable: "Commit Receiving" button
```

---

### Stage 6: Commit (Create Immutable Records)

**Endpoint**: `POST /api/v1/receiving/sessions/{id}/commit`

**Role gate**: Only **HOD** can commit

**Process**:

```
1. Validate preconditions
   ↓ Check: session.status='draft' OR 'reconciling' OR 'verifying'
   ↓ Check: user role = HOD
   ↓ Check: at least 1 verified line exists
   ↓ Check: all discrepancies have photos attached

2. Create receiving event (immutable)
   ↓ INSERT INTO pms_receiving_events:
      - yacht_id
      - session_id
      - event_number = generate_event_number()
      - received_at = NOW()
      - received_by = user_id
      - total_lines = COUNT(verified lines)
      - has_discrepancies = CHECK(any line has_discrepancy=true)

3. For each verified draft line:

   ↓ INSERT INTO pms_receiving_line_items:
      - yacht_id
      - receiving_event_id
      - line_number
      - part_id (matched)
      - quantity_received
      - unit
      - verified_by
      - verified_at
      - notes (if any)
      - has_discrepancy (if marked)

4. Update inventory (if not discrepancy)
   FOR EACH line WHERE has_discrepancy=false:

      ↓ INSERT INTO pms_inventory_transactions:
         - yacht_id
         - part_id
         - transaction_type='receiving'
         - quantity_change=quantity_received
         - reference_type='receiving_line_item'
         - reference_id=line_item_id
         - performed_by=user_id
         - performed_at=NOW()

      ↓ UPDATE pms_inventory_stock:
         - quantity_on_hand += quantity_received
         - last_received_at=NOW()

5. Create finance transaction
   IF line has unit_price:
      ↓ INSERT INTO pms_finance_transactions:
         - yacht_id
         - transaction_type='receiving_cost'
         - amount=quantity * unit_price
         - currency='USD'
         - reference_type='receiving_event'
         - reference_id=event_id
         - recorded_by=user_id

6. Update shopping list (if matched)
   FOR EACH line WHERE matched to shopping_list_item:
      ↓ UPDATE pms_shopping_list_items:
         - quantity_received += quantity
         - IF quantity_received >= quantity_requested:
            SET status='fulfilled'

7. Update session status
   ↓ UPDATE pms_receiving_sessions:
      - status='committed'
      - committed_by=user_id
      - committed_at=NOW()

8. Create audit log
   ↓ INSERT INTO pms_audit_log:
      - yacht_id
      - action='receiving_session_committed'
      - entity_type='receiving_session'
      - entity_id=session_id
      - user_id
      - old_values={status: 'draft'}
      - new_values={status: 'committed', line_count: X}
      - signature=compute_signature()
```

**Response**:
```json
{
  "status": "success",
  "receiving_event_id": "uuid",
  "event_number": "RCV-EVT-2026-001",
  "lines_committed": 10,
  "inventory_updated": true,
  "finance_recorded": true,
  "next_steps": {
    "action": "generate_labels",
    "url": "/api/v1/receiving/events/{event_id}/generate-labels"
  }
}
```

---

### Stage 7: Label PDF Generation (Optional)

**Endpoint**: `POST /api/v1/receiving/events/{event_id}/generate-labels`

**Process**:

```
1. Fetch receiving line items
   ↓ Query: pms_receiving_line_items WHERE receiving_event_id=X

2. For each line item (or each unit if config.labels_per_unit=true):

   ↓ Generate QR code data:
      {
        "part_id": "uuid",
        "part_number": "MTU-OF-4568",
        "quantity": 12,
        "received_date": "2026-01-09",
        "receiving_event_id": "uuid",
        "bin_location": "A-12-3" (if assigned)
      }

   ↓ Encode as QR code (using qrcode library)
   ↓ Create label layout (4x6 format):
      +------------------+
      | [QR CODE]        |
      | MTU-OF-4568      |
      | MTU Oil Filter   |
      | Qty: 12 ea       |
      | Rcvd: 2026-01-09 |
      +------------------+

3. Generate PDF
   ↓ Use ReportLab
   ↓ Combine all labels into single PDF
   ↓ Filename: labels_{event_number}_{timestamp}.pdf

4. Upload to storage
   ↓ Upload to: pms-label-pdfs/{yacht_id}/{filename}

   ↓ INSERT INTO pms_label_generations:
      - yacht_id
      - receiving_event_id
      - pdf_path
      - label_count
      - generated_by=user_id
      - generated_at=NOW()

5. Generate signed URL
   ↓ Create: 1-hour expiry signed URL
   ↓ Return to frontend for download
```

**Response**:
```json
{
  "status": "success",
  "label_pdf_id": "uuid",
  "pdf_url": "https://storage.../signed-url...",
  "label_count": 12,
  "expires_at": "2026-01-09T16:30:00Z"
}
```

---

## Sequence Diagram

```
User           Frontend        Upload API      Worker Queue    Processing      Reconciliation    Commit API      Label Gen
 │                │                │                │               │                  │               │              │
 │─ Upload ─────→│                │                │               │                  │               │              │
 │                │─ POST /upload→│                │               │                  │               │              │
 │                │                │─ Validate ────│               │                  │               │              │
 │                │                │─ Dedupe Check─│               │                  │               │              │
 │                │                │─ DB Insert ───│               │                  │               │              │
 │                │                │─ Storage Write│               │                  │               │              │
 │                │                │─ Queue Job ──→│               │                  │               │              │
 │                │←─ 202 Accepted─│                │               │                  │               │              │
 │←─ Show Spinner─│                │                │               │                  │               │              │
 │                │                │                │─ Dequeue ────→│                  │               │              │
 │                │                │                │               │─ OCR ────────────│               │              │
 │                │                │                │               │─ Extract ────────│               │              │
 │                │                │                │               │─ Normalize (LLM)?│               │              │
 │                │                │                │               │←─ Draft Lines ───│               │              │
 │                │                │                │               │─ Match ──────────→│               │              │
 │                │                │                │               │←─ Suggestions ───│               │              │
 │                │                │                │               │─ Create Session ─│               │              │
 │                │                │                │               │─ Create Drafts ──│               │              │
 │                │←─ WebSocket Update ─────────────│               │                  │               │              │
 │←─ Show Drafts ─│                │                │               │                  │               │              │
 │                │                │                │               │                  │               │              │
 │─ Verify Lines →│                │                │               │                  │               │              │
 │─ Check Boxes ─→│─ PATCH /verify→│                │               │                  │               │              │
 │                │                │─ Update DB ───│               │                  │               │              │
 │                │←─ 200 OK ──────│                │               │                  │               │              │
 │                │                │                │               │                  │               │              │
 │─ Commit Button →│─ POST /commit─│                │               │                  │               │              │
 │                │                │─ Role Check ──│               │                  │               │              │
 │                │                │─ Create Event─│               │                  │               │              │
 │                │                │─ Create Lines─│               │                  │               │              │
 │                │                │─ Update Inv ──│               │                  │               │              │
 │                │                │─ Finance Txn ─│               │                  │               │              │
 │                │                │─ Audit Log ───│               │                  │               │              │
 │                │←─ 200 Success ─│                │               │                  │               │              │
 │                │                │                │               │                  │               │              │
 │─ Gen Labels ──→│─ POST /gen-labels ─────────────────────────────────────────────────→│              │
 │                │                │                │               │                  │               │─ Generate QR─│
 │                │                │                │               │                  │               │─ Create PDF ─│
 │                │                │                │               │                  │               │─ Upload ─────│
 │                │                │                │               │                  │               │←─ Signed URL │
 │                │←─ PDF URL ──────────────────────────────────────────────────────────│              │
 │←─ Download PDF─│                │                │               │                  │               │              │
```

---

## Decision Points & Triggers

### Trigger 1: Deduplication Hit
**Condition**: SHA256 hash exists in DB
**Action**: Return existing image_id, skip storage upload, skip processing
**Cost saved**: $0.03-0.15 per duplicate

### Trigger 2: Low OCR Coverage
**Condition**: `coverage < 0.8`
**Action**: Invoke gpt-4.1-mini normalization
**Cost added**: $0.02-0.10

### Trigger 3: LLM Normalization Fails
**Condition**: gpt-4.1-mini confidence < 0.6
**Action**: Escalate to gpt-4.1 (stronger model)
**Cost added**: $0.05-0.20

### Trigger 4: Max LLM Calls Reached
**Condition**: Session has 3 LLM calls already
**Action**: Return partial results, flag manual_match_required=true
**User impact**: Must manually match unmatched lines

### Trigger 5: Multi-Page PDF
**Condition**: PDF has > 1 page
**Action**: Process each page separately, create separate draft lines per page
**All pages linked to same session**

### Trigger 6: Discrepancy Marked
**Condition**: User marks line as damaged/missing
**Action**: Require photo upload (Section C flow)
**Block commit until photo attached**

### Trigger 7: Create New Part
**Condition**: No match found, user selects "Create Candidate Part"
**Action**: Create candidate part (requires HOD approval later)
**Line can be verified but part is pending**

---

## Error Handling

### Recoverable Errors

1. **OCR fails** → Retry with different preprocessing
2. **LLM timeout** → Retry once, then escalate or fail
3. **Storage upload fails** → Retry 3 times with exponential backoff
4. **Match suggestions timeout** → Return empty suggestions, allow manual match

### Non-Recoverable Errors

1. **Rate limit exceeded** → Block upload, return error
2. **Invalid file type** → Reject immediately
3. **Commit without verification** → Block with validation error
4. **Non-HOD tries to commit** → 403 Forbidden

### Error Response Format

```json
{
  "status": "error",
  "error_code": "OCR_FAILED",
  "message": "Failed to extract text from image after 3 attempts",
  "details": {
    "image_id": "uuid",
    "attempts": 3,
    "last_error": "Tesseract timeout"
  },
  "recoverable": true,
  "suggested_action": "Try uploading a clearer image or PDF"
}
```

---

## Performance Metrics

### Target Latencies

- **Upload API**: < 2 seconds (file validation + DB insert + storage)
- **OCR Processing**: < 5 seconds per image
- **LLM Normalization**: < 10 seconds (if needed)
- **Reconciliation**: < 3 seconds
- **Commit**: < 5 seconds
- **Label Generation**: < 10 seconds

### End-to-End Target

**From upload to verified drafts**: < 30 seconds for typical packing slip (1-2 pages, 10-20 lines)

---

## Cost Breakdown (Per Session)

### Typical Case (Good OCR, No LLM)
- OCR (Tesseract): $0.00 (self-hosted)
- Heuristic extraction: $0.00 (deterministic)
- Reconciliation queries: $0.00 (DB queries)
- **Total**: $0.00-0.01

### LLM Needed (Poor OCR Quality)
- OCR: $0.01-0.03
- gpt-4.1-mini normalization: $0.02-0.10
- Reconciliation: $0.00
- **Total**: $0.03-0.13

### Escalation Case (Terrible Scan)
- OCR: $0.01-0.03
- gpt-4.1-mini fails: $0.05
- gpt-4.1 escalation: $0.05-0.20
- **Total**: $0.11-0.28

**Hard cap**: $0.50 per session (enforced by max 3 LLM calls)

---

## Next: API Contracts

See `04_api_contracts.md` for detailed endpoint specifications and JSON schemas.
