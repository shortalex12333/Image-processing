# Pipeline Sections (A-E)
## Five distinct workflows for image processing

**Date**: 2026-01-09
**Purpose**: Define input → output for each image type
**Key principle**: Different workflows, not one generic pipeline

---

## Overview: Why Separate Sections?

Each upload type has **different goals**, **different outputs**, and **different cost profiles**:

| Section | Goal | Output | OCR Required | LLM Required | User Verification |
|---------|------|--------|--------------|--------------|-------------------|
| **A: Receiving** | Extract line items | Draft lines | ✓ Yes | ✓ Yes | ✓ Checkbox |
| **B: Shipping Label** | Extract metadata | Order attachment | ✓ Yes | △ Light | ✗ No |
| **C: Discrepancy** | Prove damage/missing | Photo attachment | ✗ No | ✗ No | ✓ Manual tag |
| **D: Part Photos** | Visual reference | Part attachment | ✗ No | ✗ No | ✗ No |
| **E: Label PDF** | Generate labels | PDF output | ✗ No | ✗ No | ✗ No |

**Critical**: Sections A-D are **upload handlers**. Section E is **output generation**.

---

## Section A: Receiving (Packing Slips / Receiving Notes)

### Goal
Extract **line items with quantities** from packing slips/receiving notes into draft lines for checkbox verification.

### Input
- **File types**: PDF, JPG, PNG, HEIC (multi-page supported)
- **Typical content**: Tables with columns like:
  - Quantity / Unit
  - Part number (sometimes)
  - Description / Item name
  - Unit price (sometimes)
- **Examples**: Supplier packing slip, receiving note, delivery receipt

### Processing Pipeline

```
1. Intake
   ↓ File validation (type, size, dimensions, blur check)
   ↓ SHA256 dedupe check
   ↓ Rate limit check
   ↓ Create pms_image_uploads record
   ↓ Upload to storage bucket (pms-receiving-images)

2. OCR (Stage 1: Deterministic)
   ↓ Tesseract OCR OR Cloud Vision API
   ↓ Preprocessing: deskew, binarize, contrast adjustment
   ↓ Extract raw text + bounding boxes
   ↓ Store ocr_raw_text, mark validation_stage='validated'

3. Structure Detection (Stage 2: Heuristics)
   ↓ Detect tables (OpenCV line detection OR heuristics)
   ↓ Identify column headers (qty, unit, desc, etc.)
   ↓ Parse rows via regex patterns
   ↓ Calculate coverage: % of rows successfully parsed

4. Normalization (Stage 3: LLM - conditional)
   IF coverage < 80% OR table detection failed:
      ↓ gpt-4.1-mini with prompt:
        "Normalize this OCR text into structured rows.
         Extract: quantity, unit, description, part_number (if present).
         Return JSON array of line items."
      ↓ Parse LLM response
      ↓ Validate schema (pydantic)

   IF still fails (low confidence, too many unknowns):
      ↓ Escalate to gpt-4.1 (stronger model)
      ↓ If still fails: mark extraction_status='failed'
      ↓ Return to user with "manual match" UI

5. Reconciliation (Stage 4: Match suggestions)
   ↓ For each draft line:
      ↓ Fuzzy match description → pms_parts (rapidfuzz)
      ↓ Check against pms_shopping_list_items
      ↓ Check against pms_purchase_order_items
      ↓ Store suggestions (part_id, confidence)

6. Draft Creation (Stage 5: DB write)
   ↓ Create pms_receiving_session (status='draft')
   ↓ Create pms_receiving_draft_lines[] (is_verified=false)
   ↓ Link to pms_image_uploads via pms_entity_images
   ↓ Return session_id + draft_lines to frontend
```

### Output Schema

```json
{
  "status": "success",
  "session_id": "uuid",
  "image_ids": ["uuid1", "uuid2"],
  "draft_lines": [
    {
      "id": "uuid",
      "line_number": 1,
      "quantity": 12.0,
      "unit": "ea",
      "description": "MTU Oil Filter Element",
      "extracted_part_number": "MTU-OF-4568",
      "is_verified": false,
      "suggested_matches": [
        {
          "part_id": "uuid",
          "part_number": "MTU-OF-4568",
          "part_name": "MTU Oil Filter Element",
          "confidence": 0.95,
          "source": "exact_match"
        }
      ]
    }
  ],
  "metadata": {
    "extraction_method": "ocr+heuristics",
    "needed_llm": false,
    "coverage": 0.92,
    "latency_ms": 1250
  }
}
```

### Triggers & Decision Points

**Trigger 1: Multi-page detection**
- If PDF has >1 page OR multi-image upload:
  - Process each page separately
  - Create separate draft_lines per page
  - Link all images to same session

**Trigger 2: Low coverage (< 80%)**
- Invoke gpt-4.1-mini normalization
- Track cost: increment llm_calls_count

**Trigger 3: Normalization fails**
- Escalate to gpt-4.1 (stronger)
- If still fails: mark extraction_status='failed'
- Return partial results + "manual match required" flag

**Hard caps (cost control)**:
- Max 3 LLM calls per session
- Max 10,000 tokens per session
- If exceeded: return partial + manual match UI

### Role Gates

- **crew**: Can upload, view own sessions, verify assigned lines
- **hod**: Can commit sessions, override matches
- **service_role**: Writes OCR results, runs processing jobs

---

## Section B: Shipping Label / Invoice Support

### Goal
Extract **metadata** (supplier, PO number, tracking) from shipping labels to assist order attachment. **No draft lines created**.

### Input
- **File types**: PDF, JPG, PNG
- **Typical content**:
  - Carrier name (FedEx, UPS, DHL)
  - Tracking number
  - Supplier name/address
  - PO number or order reference
  - Ship to / Ship from addresses

### Processing Pipeline

```
1. Intake
   ↓ Same as Section A
   ↓ Upload to pms-receiving-images bucket

2. OCR (Fast mode)
   ↓ Tesseract OR Cloud Vision
   ↓ No table detection needed (just text extraction)

3. Classification (Stage 1: Determine type)
   ↓ gpt-4.1-nano with prompt:
     "Classify this text. Options: shipping_label, invoice, packing_slip, other.
      Return JSON: {type: string, confidence: float}"

   IF type != 'shipping_label':
      ↓ Route to appropriate section OR mark as 'unknown'

4. Metadata Extraction (Stage 2: Lightweight)
   ↓ gpt-4.1-nano with prompt:
     "Extract from this shipping label:
      - carrier (FedEx/UPS/DHL/USPS/other)
      - tracking_number
      - supplier_name
      - po_number (if present)
      - order_reference (if present)
      Return JSON only."
   ↓ Parse response
   ↓ Validate schema

5. Order Matching (Stage 3: Suggestions)
   ↓ Query pms_orders WHERE:
      ↓ order_number LIKE extracted_po_number
      OR supplier matches supplier_name
   ↓ Return top 3 suggestions (fuzzy match)

6. Attachment (Stage 4: Link to order)
   IF confident match (1 result, high confidence):
      ↓ Auto-attach to order via pms_entity_images
      ↓ Set image_role='shipping_label'
   ELSE:
      ↓ Return suggestions for manual selection
```

### Output Schema

```json
{
  "status": "success",
  "image_id": "uuid",
  "document_type": "shipping_label",
  "extracted_metadata": {
    "carrier": "FedEx",
    "tracking_number": "1234567890",
    "supplier_name": "Marine Supply Co",
    "po_number": "PO-2026-001",
    "order_reference": null
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
  "metadata": {
    "classification_confidence": 0.98,
    "extraction_method": "gpt-4.1-nano",
    "latency_ms": 850
  }
}
```

### Triggers & Decision Points

**Trigger 1: Classification confidence < 0.9**
- Return "manual classification" option
- Show preview + ask user to confirm type

**Trigger 2: No PO/tracking extracted**
- Allow "attach to order manually" flow
- Store metadata but don't force match

**Trigger 3: Multiple order matches**
- Never auto-attach
- Show all matches for user selection

### Role Gates

- **crew**: Can upload, view, attach to orders they created
- **hod**: Can attach to any order
- **service_role**: Runs OCR + extraction

---

## Section C: Discrepancy Photos (Damage/Missing Evidence)

### Goal
Attach photos of damaged, incorrect, or missing items to receiving line items. **No OCR, high trust**.

### Input
- **File types**: JPG, PNG, HEIC
- **Typical content**: Photos of:
  - Damaged items
  - Incorrect items received
  - Missing item evidence (empty box, etc.)
  - Packaging damage

### Processing Pipeline

```
1. Intake
   ↓ File validation (image types only, no PDFs)
   ↓ Size check (max 10MB)
   ↓ Blur check (reject blurry photos)
   ↓ SHA256 dedupe
   ↓ Upload to pms-discrepancy-photos bucket

2. Manual Tagging (Required)
   ↓ User MUST select:
      ↓ Discrepancy type: damaged | incorrect | missing
      ↓ Receiving line item (from active session)
      ↓ Optional: Description text

3. Attachment (Direct)
   ↓ Create pms_entity_images record:
      ↓ entity_type='receiving_line_item'
      ↓ entity_id=selected_line_item_id
      ↓ image_role='discrepancy'
   ↓ Update receiving_line_item:
      ↓ has_discrepancy=true
      ↓ discrepancy_type='damaged' (or other)

4. Email Draft Generation (Optional)
   ↓ Generate supplier notification draft:
      "We received damaged items in shipment X.
       Line item: [description]
       Quantity affected: [qty]
       Photos attached: [links]"
```

### Output Schema

```json
{
  "status": "success",
  "image_id": "uuid",
  "attached_to": {
    "entity_type": "receiving_line_item",
    "entity_id": "uuid",
    "line_number": 3
  },
  "discrepancy_type": "damaged",
  "description": "Box crushed, items inside broken",
  "metadata": {
    "file_size_bytes": 2048000,
    "dimensions": "4032x3024",
    "uploaded_by": "uuid",
    "uploaded_at": "2026-01-09T15:30:00Z"
  }
}
```

### Triggers & Decision Points

**No triggers** - This is a straightforward photo attachment.

**Validation gates**:
- Must be attached to an active receiving session
- User must tag discrepancy type
- Photo must pass blur check

### Role Gates

- **crew**: Can upload discrepancy photos for sessions they're assigned to
- **hod**: Can upload for any session, can override discrepancy resolution
- **service_role**: (not involved - no processing)

---

## Section D: Part Photos

### Goal
Attach photos of parts for visual reference. Optionally set as primary photo.

### Input
- **File types**: JPG, PNG
- **Typical content**: Clear photos of parts for inventory catalog

### Processing Pipeline

```
1. Intake
   ↓ File validation
   ↓ Size check (max 5MB)
   ↓ Resolution check (min 800x600)
   ↓ SHA256 dedupe
   ↓ Upload to pms-part-photos bucket

2. Part Selection (Required)
   ↓ User MUST select:
      ↓ Existing part (from pms_parts)
      OR Create candidate part (pending HOD approval)

3. Attachment (Direct)
   ↓ Create pms_entity_images record:
      ↓ entity_type='part'
      ↓ entity_id=selected_part_id
      ↓ image_role='part_photo' OR 'primary_photo'

4. Primary Photo Logic
   IF user selects "set as primary":
      ↓ Update other photos for this part: image_role='part_photo'
      ↓ Set this photo: image_role='primary_photo'
```

### Output Schema

```json
{
  "status": "success",
  "image_id": "uuid",
  "attached_to": {
    "entity_type": "part",
    "entity_id": "uuid",
    "part_number": "MTU-OF-4568",
    "part_name": "MTU Oil Filter Element"
  },
  "image_role": "primary_photo",
  "is_primary": true,
  "metadata": {
    "file_size_bytes": 1024000,
    "dimensions": "1920x1080",
    "uploaded_by": "uuid"
  }
}
```

### Triggers & Decision Points

**No triggers** - Simple attachment flow.

**Optional enhancement (future)**:
- Basic classification: filter, gasket, seal, bolt, etc.
- gpt-4.1-nano for "what type of part is this?"

### Role Gates

- **crew**: Can upload part photos, can create candidate parts (pending approval)
- **hod**: Can promote candidate parts to real parts
- **service_role**: (not involved)

---

## Section E: Label PDF Generation

### Goal
Generate QR code labels for received items. **Output generation, not upload processing**.

### Input (from database)
- Receiving line item data:
  - Part number, description, quantity
  - Bin location (if assigned)
  - Received date
  - Receiving session ID

### Generation Pipeline

```
1. Trigger
   ↓ User clicks "Generate Labels" for committed receiving session
   ↓ OR Auto-generate after commit (config option)

2. Data Fetch
   ↓ Query pms_receiving_line_items WHERE session_id=X
   ↓ For each line: get part, quantity, location

3. QR Code Generation
   ↓ For each line item (or each unit if config.label_per_unit=true):
      ↓ Generate QR code containing:
         {
           "part_id": "uuid",
           "part_number": "MTU-OF-4568",
           "received_at": "2026-01-09",
           "session_id": "uuid"
         }
      ↓ Encode as QR (using python-qrcode or similar)

4. PDF Layout
   ↓ Use ReportLab or similar
   ↓ Layout: 4x6 label format (or configurable)
   ↓ Include:
      ↓ QR code (large, scannable)
      ↓ Part number (human-readable)
      ↓ Description (truncated if long)
      ↓ Quantity
      ↓ Received date

5. Storage
   ↓ Save PDF to pms-label-pdfs bucket
   ↓ Path: {yacht_id}/labels/{session_id}_{timestamp}.pdf
   ↓ Create pms_label_generations record:
      ↓ session_id, pdf_path, generated_by, generated_at

6. Return signed URL
   ↓ Generate signed URL (1 hour expiry)
   ↓ Return to frontend for download/print
```

### Output Schema

```json
{
  "status": "success",
  "label_pdf_id": "uuid",
  "session_id": "uuid",
  "pdf_url": "https://...signed-url...",
  "label_count": 12,
  "metadata": {
    "file_size_bytes": 245000,
    "generated_at": "2026-01-09T15:35:00Z",
    "generated_by": "uuid"
  }
}
```

### Triggers & Decision Points

**Trigger 1: Auto-generate on commit**
- Config option: auto_generate_labels=true
- Generate immediately after session committed

**Trigger 2: Bulk re-generation**
- User selects multiple sessions
- Generate combined PDF (all labels)

**Trigger 3: Label per unit vs per line**
- Config: label_per_unit=true
  - Qty=12 → generates 12 labels (each unit scannable individually)
- Config: label_per_unit=false
  - Qty=12 → generates 1 label (for the batch)

### Role Gates

- **crew**: Can request label generation for sessions they verified
- **hod**: Can generate labels for any session
- **service_role**: Performs actual PDF generation

---

## Workflow Routing (UI Entry Points)

### How users select which section:

```
Upload Photo/PDF
   ↓
┌──────────────────────────────────────┐
│  Select Upload Type:                 │
│  ○ Receiving slip (packing slip)     │ → Section A
│  ○ Shipping label                    │ → Section B
│  ○ Discrepancy (damage/missing)      │ → Section C
│  ○ Part photo                        │ → Section D
│  ○ Auto-detect (uses classification) │ → gpt-4.1-nano → route
└──────────────────────────────────────┘
```

**Best practice**: Explicit UI selection (not auto-detect). Auto-detect is backup only.

---

## Cost Summary by Section

| Section | OCR Cost | LLM Cost | Total Est. | Notes |
|---------|----------|----------|------------|-------|
| **A: Receiving** | $0.01-0.05 | $0.02-0.10 | **$0.03-0.15** | Most expensive; LLM optional |
| **B: Shipping Label** | $0.01-0.03 | $0.01 (nano) | **$0.02-0.04** | Lightweight extraction |
| **C: Discrepancy** | $0 | $0 | **$0** | Photo only, no processing |
| **D: Part Photo** | $0 | $0 | **$0** | Photo only |
| **E: Label PDF** | $0 | $0 | **$0** | Generation only |

**Optimization**: Section A can avoid LLM calls 70-80% of the time with good heuristics.

---

## Next Steps

1. **Step 5**: Design end-to-end flow with sequence diagram (`03_end_to_end_flow.md`)
2. **Step 6**: Define API contracts (`04_api_contracts.md`)
3. **Step 7**: Model strategy and cost escalation rules (`05_model_strategy.md`)

---

**Key Takeaway**: Five separate pipelines, not one generic "upload image" flow. Each optimized for its purpose.
