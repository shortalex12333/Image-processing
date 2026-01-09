# Frontend Integration Guide
## URL Naming Conventions & Required Components

---

## 🌐 Base URL Convention

```javascript
// Environment-based URLs
const API_URLS = {
  production: 'https://image-processing-api.onrender.com/api/v1',
  staging: 'https://image-processing-api-staging.onrender.com/api/v1',
  development: 'http://localhost:8001/api/v1'
};

// Use in your app
const BASE_URL = API_URLS[process.env.NODE_ENV || 'development'];
```

---

## 📋 URL Pattern: `/api/v1/{domain}/{action}`

### Domain Structure

| Domain | Purpose | Example Endpoint |
|--------|---------|-----------------|
| `intake` | File uploads | `/api/v1/intake/upload` |
| `sessions` | Receiving workflow | `/api/v1/sessions/{id}/draft-lines` |
| `extraction` | OCR & parsing | `/api/v1/extraction/classify` |
| `reconciliation` | Part matching | `/api/v1/reconciliation/suggest` |
| `labels` | Shipping labels | `/api/v1/labels/process` |
| `photos` | Photo attachments | `/api/v1/photos/attach/discrepancy` |
| `label-generation` | PDF/QR generation | `/api/v1/label-generation/parts/pdf` |
| `system` | Health & metrics | `/api/v1/system/status` |

---

## 🏗️ What You Need to Build

### 1. Receiving Screen (`/receiving`)

**Purpose**: Main receiving workflow - upload → verify → commit

**Required Components**:
```
ReceivingScreen/
├── ReceivingUpload.tsx          ← Camera/file upload button
├── DraftLinesTable.tsx          ← Verification table with checkboxes
├── PartMatchDialog.tsx          ← Match suggestions for unmatched items
├── ConfirmationDialog.tsx       ← "You ticked 30 items. Proceed?"
└── ReceivingCommit.tsx          ← Commit button (HOD only)
```

**API Endpoints Used**:
```javascript
// 1. Upload
POST /api/v1/intake/upload
Body: FormData with file
Returns: { session_id, status, image_id }

// 2. Get draft lines
GET /api/v1/sessions/{session_id}/draft-lines
Returns: { lines: [...] }

// 3. Get match suggestions (for unmatched items)
POST /api/v1/reconciliation/suggest
Body: { part_number, description, yacht_id }
Returns: { suggestions: [...] }

// 4. Update line matching
POST /api/v1/sessions/{session_id}/update
Body: { line_id, action: "match", match_id }
Returns: { success: true }

// 5. Commit receiving
POST /api/v1/sessions/{session_id}/commit
Body: { lines: [...], elapsed_seconds, confirmed }
Returns: { success: true, session_id, committed_at }
// Or: { requires_confirmation: true, message }
```

**State Management**:
```typescript
interface ReceivingState {
  session: { id: string; status: string } | null;
  draftLines: DraftLine[];
  ticked: Set<string>;  // line_ids
  elapsedSeconds: number;  // For lazy workflow protection
  isCommitting: boolean;
}

interface DraftLine {
  line_id: string;
  extracted_text: string;
  quantity: number;
  unit: string;
  part_number: string;
  description: string;
  suggested_match?: {
    part_id: string;
    part_number: string;
    name: string;
    confidence: number;
    match_type: string;
  };
  action?: 'match' | 'create_candidate' | 'ignore';
  match_id?: string;
}
```

**UI Flow**:
```
1. User clicks camera icon
2. Upload to /api/v1/intake/upload
3. Show loading "Extracting items..."
4. Fetch /api/v1/sessions/{id}/draft-lines
5. Display table with checkboxes:
   [☐] 10 ea | MTU-OF-4568 | MTU Oil Filter | → MTU-OF-4568 (100% ✅)
   [☐] 8 ea  | KOH-AF-9902 | Kohler Filter  | → KOH-AF-9902 (100% ✅)
   [☐] 5 ea  | UNKNOWN-123 | Mystery Part   | → No match (❓) [Resolve]
6. User ticks items to receive
7. For unmatched items: Click "Resolve" → show match suggestions
8. User clicks "Commit Receiving" (HOD only)
9. If ticked too fast: Show "You confirmed 30 items. Proceed?"
10. Success: Navigate to /receiving/labels or /inventory
```

---

### 2. Label Generation Screen (`/receiving/labels`)

**Purpose**: Generate printable labels after receiving

**Required Components**:
```
LabelGenerationScreen/
├── LabelPreview.tsx             ← Preview label layout
├── LabelOptions.tsx             ← Format selection (Avery 5160, etc.)
└── LabelDownload.tsx            ← Download PDF / Email options
```

**API Endpoints Used**:
```javascript
// Generate multi-part labels
POST /api/v1/label-generation/parts/pdf
Body: {
  part_ids: ["uuid1", "uuid2"],
  yacht_id: "uuid",
  label_format: "avery_5160",
  include_qr: true
}
Returns: PDF blob

// Get single part QR code
GET /api/v1/label-generation/parts/{part_id}/qr
Returns: PNG blob (200x200px QR code)
```

**UI Flow**:
```
1. After commit, show "Generate Labels"
2. Display received items with checkboxes (default: all checked)
3. Show format dropdown: Avery 5160 (3×10), Avery 5163 (2×5), etc.
4. Preview button → Show label layout
5. Download button → POST to /label-generation/parts/pdf
6. Open PDF in new tab or trigger download
```

---

### 3. Shipping Label Screen (`/receiving/shipping-label`)

**Purpose**: Process shipping labels to link with purchase orders

**Required Components**:
```
ShippingLabelScreen/
├── ShippingLabelUpload.tsx      ← Upload label photo
├── ExtractedMetadata.tsx        ← Display tracking#, PO#, carrier
└── OrderMatcher.tsx             ← Match to existing POs
```

**API Endpoints Used**:
```javascript
// Process shipping label
POST /api/v1/labels/process
Body: { image_id, yacht_id }
Returns: {
  status: "success",
  metadata: {
    tracking_number: "1Z999AA10123456784",
    carrier: "UPS",
    po_number: "PO-2026-001",
    ship_to: "MY Excellence"
  },
  matched_orders: [
    { order_id: "uuid", po_number: "PO-2026-001", confidence: 0.95 }
  ]
}

// Link to order
POST /api/v1/labels/link-to-order
Body: { image_id, order_id, yacht_id }
Returns: { success: true }
```

**UI Flow**:
```
1. User uploads shipping label photo
2. Show extracted metadata:
   - Tracking #: 1Z999AA10123456784
   - Carrier: UPS
   - PO #: PO-2026-001
3. Show matched orders (if found):
   → PO-2026-001 (95% match) [Link to Order]
4. User clicks "Link to Order"
5. Success: Order status updated to "arrived"
```

---

### 4. Discrepancy Photo Screen (`/receiving/discrepancy`)

**Purpose**: Attach photos to damaged/missing items

**Required Components**:
```
DiscrepancyScreen/
├── DiscrepancyCamera.tsx        ← Camera capture
├── DiscrepancyForm.tsx          ← Discrepancy type & notes
└── DiscrepancyGallery.tsx       ← View attached photos
```

**API Endpoints Used**:
```javascript
// Attach discrepancy photo
POST /api/v1/photos/attach/discrepancy
Body: {
  image_id: "uuid",
  yacht_id: "uuid",
  entity_type: "work_order",
  entity_id: "uuid",
  discrepancy_type: "damaged",  // or "missing", "wrong_item"
  notes: "Seal broken on delivery"
}
Returns: { success: true, attachment_id: "uuid" }

// Get attached photos
GET /api/v1/photos/work_order/{work_order_id}
Returns: {
  photos: [
    {
      image_id: "uuid",
      url: "https://...",
      discrepancy_type: "damaged",
      notes: "Seal broken",
      uploaded_by: "user@example.com",
      uploaded_at: "2026-01-09T..."
    }
  ]
}
```

**UI Flow**:
```
1. From receiving screen, click "Report Discrepancy"
2. Select discrepancy type: Damaged / Missing / Wrong Item
3. Click camera icon → Capture photo
4. Add notes: "Seal broken on delivery"
5. Submit → POST to /photos/attach/discrepancy
6. Photo appears in work order detail view
```

---

### 5. Pending Sessions Screen (`/receiving/pending`)

**Purpose**: Review incomplete receiving sessions (HOD only)

**Required Components**:
```
PendingSessionsScreen/
├── PendingSessionsList.tsx      ← List of abandoned sessions
└── SessionReviewDialog.tsx      ← Complete or delete session
```

**API Endpoints Used**:
```javascript
// List pending sessions
GET /api/v1/sessions/pending
Returns: {
  sessions: [
    {
      session_id: "uuid",
      created_at: "2026-01-08T...",
      created_by: "user@example.com",
      draft_count: 10,
      matched_count: 7,
      unmatched_count: 3,
      age_hours: 25
    }
  ]
}

// Get session details
GET /api/v1/sessions/{session_id}
Returns: { session: {...}, draft_lines: [...] }

// Delete session
DELETE /api/v1/sessions/{session_id}
Returns: { success: true }
```

**UI Flow**:
```
1. HOD views pending sessions (24+ hours old)
2. Click session → View draft lines
3. Complete matching and commit
4. Or delete if invalid
```

---

## 🔑 Authentication Pattern

**All requests** (except `/health`) require authentication:

```typescript
// Get Supabase session token
const { data: { session } } = await supabase.auth.getSession();
const token = session.access_token;

// Include in all requests
fetch(`${BASE_URL}/intake/upload`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`  // ← Required
  },
  body: formData
});
```

**Server extracts from token**:
- `user_id` - UUID of authenticated user
- `yacht_id` - UUID of user's yacht (from user_profiles)
- `roles` - Array of roles (e.g., ["crew", "eto"])
- `is_hod` - Boolean (chief_engineer, captain, or manager)

**RLS enforces**:
- Users only see data for their yacht_id
- HOD-only actions: commit, manage roles, close work orders
- All mutations create audit log entries

---

## 📦 Recommended API Client

```typescript
// lib/imageAPI.ts
import { supabase } from './supabase';

const BASE_URL = process.env.NEXT_PUBLIC_IMAGE_API_URL!;

async function getAuthToken() {
  const { data: { session } } = await supabase.auth.getSession();
  if (!session) throw new Error('Not authenticated');
  return session.access_token;
}

export const imageAPI = {
  // Upload
  async uploadPackingSlip(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('type', 'packing_slip');

    const token = await getAuthToken();
    const response = await fetch(`${BASE_URL}/intake/upload`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });

    if (!response.ok) throw new Error(await response.text());
    return response.json();
  },

  // Get draft lines
  async getDraftLines(sessionId: string) {
    const token = await getAuthToken();
    const response = await fetch(`${BASE_URL}/sessions/${sessionId}/draft-lines`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!response.ok) throw new Error(await response.text());
    return response.json();
  },

  // Commit session
  async commitSession(
    sessionId: string,
    lines: any[],
    elapsedSeconds: number,
    confirmed: boolean = false
  ) {
    const token = await getAuthToken();
    const response = await fetch(`${BASE_URL}/sessions/${sessionId}/commit`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ lines, elapsed_seconds: elapsedSeconds, confirmed })
    });

    if (!response.ok) throw new Error(await response.text());
    return response.json();
  },

  // Get match suggestions
  async getMatchSuggestions(partNumber: string, description: string) {
    const token = await getAuthToken();
    const response = await fetch(`${BASE_URL}/reconciliation/suggest`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ part_number: partNumber, description })
    });

    if (!response.ok) throw new Error(await response.text());
    return response.json();
  },

  // Generate labels
  async generatePartLabels(partIds: string[]) {
    const token = await getAuthToken();
    const response = await fetch(`${BASE_URL}/label-generation/parts/pdf`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ part_ids: partIds })
    });

    if (!response.ok) throw new Error(await response.text());
    return response.blob();
  }
};
```

**Usage in Components**:
```typescript
import { imageAPI } from '@/lib/imageAPI';

const ReceivingScreen = () => {
  const handleUpload = async (file: File) => {
    try {
      const result = await imageAPI.uploadPackingSlip(file);
      const { lines } = await imageAPI.getDraftLines(result.session_id);
      setDraftLines(lines);
    } catch (error) {
      toast.error(error.message);
    }
  };

  return <ReceivingUpload onUpload={handleUpload} />;
};
```

---

## 🎨 UI Components Needed

### Core Components

1. **FileUpload** - Camera/file picker with intake gate validation
2. **DraftLineRow** - Single draft line with checkbox, match indicator
3. **MatchSuggestionCard** - Display match suggestion with confidence
4. **ConfirmationDialog** - Interstitial for bulk operations
5. **LabelPreview** - Preview generated labels
6. **DiscrepancyPhotoCapture** - Camera integration for photos

### Shared Utilities

```typescript
// lib/formatting.ts
export function formatPartNumber(partNumber: string): string {
  return partNumber.toUpperCase().replace(/\s+/g, '-');
}

export function formatConfidence(confidence: number): string {
  const percent = Math.round(confidence * 100);
  if (percent >= 90) return `${percent}% ✅`;
  if (percent >= 70) return `${percent}% ⚠️`;
  return `${percent}% ❓`;
}

export function formatCost(cost: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 4
  }).format(cost);
}
```

---

## 🚀 Getting Started

1. **Set environment variables**:
   ```bash
   NEXT_PUBLIC_IMAGE_API_URL=https://image-processing-api.onrender.com/api/v1
   ```

2. **Create API client**: Copy `lib/imageAPI.ts` from above

3. **Build components** in this order:
   - ReceivingUpload (file upload)
   - DraftLinesTable (verification)
   - PartMatchDialog (reconciliation)
   - ReceivingCommit (commit button)
   - LabelGeneration (PDF download)

4. **Test flow**:
   ```
   Upload → Verify → Match → Commit → Labels
   ```

---

## 📚 API Documentation

Full API docs:
- **Swagger UI**: `https://image-processing-api.onrender.com/docs`
- **ReDoc**: `https://image-processing-api.onrender.com/redoc`

---

**Ready to integrate**: All endpoints are production-ready with critical fixes applied ✅
