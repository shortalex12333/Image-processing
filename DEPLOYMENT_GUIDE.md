# Render.com Deployment Guide
## Image Processing Service for Cloud_PMS

**Service Name**: `image-processing-api`
**Expected URL**: `https://image-processing-api.onrender.com`
**Internal API Base**: `/api/v1`

---

## 🚀 Quick Deploy to Render

### Step 1: Push to GitHub

```bash
cd /private/tmp/Image-processing

# Initialize git if not already
git init
git add .
git commit -m "Initial commit: Image Processing Service with critical fixes"

# Add remote (replace with your repo)
git remote add origin https://github.com/shortalex12333/Image-processing.git
git branch -M main
git push -u origin main
```

### Step 2: Connect to Render

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub account
4. Select repository: `shortalex12333/Image-processing`
5. Render will auto-detect `render.yaml`

### Step 3: Configure Environment Variables

In Render Dashboard, set these **secret** environment variables:

```bash
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...  # Service role key
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...     # Anon key (public)

# OpenAI Configuration
OPENAI_API_KEY=sk-...  # Your OpenAI API key

# JWT Configuration (generate a random secret)
JWT_SECRET=$(openssl rand -base64 32)
# Example: vQz8X3mN9pL2kR5sT7wY1aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8A0C=

# CORS Configuration (your frontend domains)
ALLOWED_ORIGINS=https://cloud-pms.yourdomain.com,http://localhost:3000
```

**Important**: Never commit these values to git!

### Step 4: Deploy Database Migration

Before API goes live, run the atomic operations migration:

```bash
# Connect to Supabase via psql
psql "postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres"

# Run migration
\i migrations/20260109_atomic_operations.sql

# Verify functions created
SELECT proname FROM pg_proc
WHERE proname IN ('atomic_deduct_inventory', 'atomic_commit_session')
AND pronamespace = 'public'::regnamespace;

# Should return 3 rows
```

### Step 5: Deploy

Click **"Create Web Service"** in Render. It will:
1. Build the Docker image
2. Install dependencies
3. Start the service with `uvicorn src.main:app`
4. Run health checks at `/health`

**Build time**: ~5-10 minutes
**Status**: Check logs in Render dashboard

---

## 📡 API URL Naming Convention

### Base URL Structure

```
Production:  https://image-processing-api.onrender.com/api/v1
Staging:     https://image-processing-api-staging.onrender.com/api/v1
Local Dev:   http://localhost:8001/api/v1
```

### URL Pattern for Frontend

**Convention**: `{environment}/api/v1/{domain}/{action}`

```javascript
// Frontend environment config
const API_URLS = {
  production: 'https://image-processing-api.onrender.com/api/v1',
  staging: 'https://image-processing-api-staging.onrender.com/api/v1',
  development: 'http://localhost:8001/api/v1'
};

const BASE_URL = API_URLS[process.env.NODE_ENV || 'development'];
```

---

## 🗂️ API Endpoints (URL Reference for Frontend)

### Domain: Health & System

```
GET  /health                                    → Health check
GET  /api/v1/system/status                     → System status with cost tracking
GET  /api/v1/system/metrics                    → Usage metrics
```

### Domain: Intake (File Upload)

```
POST /api/v1/intake/upload                     → Upload packing slip/label
POST /api/v1/intake/upload-batch               → Upload multiple files
GET  /api/v1/intake/validate                   → Pre-validate file before upload
```

**Frontend Usage**:
```javascript
// Upload packing slip
const formData = new FormData();
formData.append('file', file);
formData.append('type', 'packing_slip');  // or 'shipping_label'

const response = await fetch(`${BASE_URL}/intake/upload`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${userToken}`
  },
  body: formData
});

const result = await response.json();
// Returns: { session_id, status, image_id, upload_url }
```

### Domain: Sessions (Receiving Workflow)

```
GET  /api/v1/sessions/{session_id}             → Get session details
GET  /api/v1/sessions/{session_id}/draft-lines → Get extracted draft lines
POST /api/v1/sessions/{session_id}/update      → Update draft line matching
POST /api/v1/sessions/{session_id}/commit      → Commit receiving (HOD only)
DEL  /api/v1/sessions/{session_id}             → Delete/cancel session
GET  /api/v1/sessions/pending                  → List pending sessions (needs review)
```

**Frontend Usage**:
```javascript
// Get draft lines for verification screen
const response = await fetch(`${BASE_URL}/sessions/${sessionId}/draft-lines`, {
  headers: {
    'Authorization': `Bearer ${userToken}`
  }
});

const { lines } = await response.json();
// Returns: [
//   {
//     line_id: "uuid",
//     extracted_text: "10  ea  MTU-OF-4568  MTU Oil Filter",
//     quantity: 10,
//     unit: "ea",
//     part_number: "MTU-OF-4568",
//     description: "MTU Oil Filter",
//     suggested_match: {
//       part_id: "uuid",
//       part_number: "MTU-OF-4568",
//       name: "MTU Oil Filter 16V4000",
//       confidence: 1.0,
//       match_type: "exact_part_number"
//     }
//   },
//   ...
// ]
```

### Domain: Extraction (OCR & Processing)

```
POST /api/v1/extraction/classify               → Classify document type
POST /api/v1/extraction/ocr                    → Run OCR on image
POST /api/v1/extraction/parse                  → Parse extracted text
GET  /api/v1/extraction/{session_id}/cost      → Get extraction cost breakdown
```

**Frontend Usage**:
```javascript
// Check extraction progress
const response = await fetch(`${BASE_URL}/extraction/${sessionId}/cost`, {
  headers: {
    'Authorization': `Bearer ${userToken}`
  }
});

const { total_cost, breakdown } = await response.json();
// Returns: {
//   total_cost: 0.00,
//   breakdown: {
//     ocr: 0.00,
//     parsing: 0.00,
//     llm_normalization: 0.00
//   },
//   within_budget: true
// }
```

### Domain: Reconciliation (Part Matching)

```
POST /api/v1/reconciliation/match-parts        → Match extracted items to catalog
POST /api/v1/reconciliation/suggest            → Get match suggestions
POST /api/v1/reconciliation/create-candidate   → Create new candidate part
GET  /api/v1/reconciliation/candidates         → List unverified candidate parts
```

**Frontend Usage**:
```javascript
// Get match suggestions for unmatched line
const response = await fetch(`${BASE_URL}/reconciliation/suggest`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${userToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    part_number: "MTU-OF-4568",
    description: "MTU Oil Filter",
    yacht_id: userContext.yacht_id
  })
});

const { suggestions } = await response.json();
// Returns: [
//   {
//     part_id: "uuid",
//     part_number: "MTU-OF-4568",
//     name: "MTU Oil Filter 16V4000",
//     confidence: 1.0,
//     match_type: "exact",
//     boost_factors: ["on_shopping_list", "recent_order"]
//   },
//   ...
// ]
```

### Domain: Shipping Labels

```
POST /api/v1/labels/process                    → Process shipping label (extract metadata)
GET  /api/v1/labels/{image_id}/metadata        → Get extracted label metadata
POST /api/v1/labels/link-to-order              → Link label to purchase order
```

**Frontend Usage**:
```javascript
// Process shipping label
const response = await fetch(`${BASE_URL}/labels/process`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${userToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    image_id: uploadedImageId,
    yacht_id: userContext.yacht_id
  })
});

const result = await response.json();
// Returns: {
//   status: "success",
//   metadata: {
//     tracking_number: "1Z999AA10123456784",
//     carrier: "UPS",
//     po_number: "PO-2026-001",
//     ship_to: "MY Excellence",
//     estimated_delivery: "2026-01-15"
//   },
//   matched_orders: [
//     { order_id: "uuid", po_number: "PO-2026-001", confidence: 0.95 }
//   ]
// }
```

### Domain: Photos (Attachments)

```
POST /api/v1/photos/attach/discrepancy         → Attach photo to discrepancy
POST /api/v1/photos/attach/part                → Attach photo to part
GET  /api/v1/photos/{entity_type}/{entity_id}  → Get all photos for entity
DEL  /api/v1/photos/{image_id}/detach          → Remove photo attachment
```

**Frontend Usage**:
```javascript
// Attach discrepancy photo (damaged item)
const response = await fetch(`${BASE_URL}/photos/attach/discrepancy`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${userToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    image_id: uploadedImageId,
    yacht_id: userContext.yacht_id,
    entity_type: "work_order",
    entity_id: workOrderId,
    discrepancy_type: "damaged",
    notes: "Seal broken on delivery"
  })
});
```

### Domain: Label Generation (PDF/QR)

```
POST /api/v1/label-generation/parts/pdf        → Generate part labels PDF
GET  /api/v1/label-generation/parts/{part_id}/pdf → Single part label
GET  /api/v1/label-generation/parts/{part_id}/qr  → Part QR code PNG
POST /api/v1/label-generation/equipment/pdf    → Generate equipment labels PDF
POST /api/v1/label-generation/locations/pdf    → Generate location labels PDF
```

**Frontend Usage**:
```javascript
// Generate part labels after receiving
const response = await fetch(`${BASE_URL}/label-generation/parts/pdf`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${userToken}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    part_ids: [partId1, partId2, partId3],
    yacht_id: userContext.yacht_id,
    label_format: "avery_5160",  // 3x10 grid
    include_qr: true
  })
});

// Returns PDF blob
const blob = await response.blob();
const url = URL.createObjectURL(blob);
// Open in new tab or download
window.open(url, '_blank');
```

---

## 🔐 Authentication Flow

All API requests (except `/health`) require authentication:

```javascript
// 1. User logs in via Supabase Auth
const { data: { session } } = await supabase.auth.signInWithPassword({
  email: 'user@example.com',
  password: 'password'
});

const userToken = session.access_token;

// 2. Use token in all API requests
const response = await fetch(`${BASE_URL}/intake/upload`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${userToken}`,  // ← Required
  },
  body: formData
});

// 3. Token is validated on server
// Server extracts: user_id, yacht_id, roles, is_hod
// RLS policies automatically filter data by yacht_id
```

**Token Format**: JWT (Supabase session token)
**Expiry**: 24 hours (configurable)
**Renewal**: Frontend should refresh via `supabase.auth.refreshSession()`

---

## 📦 What You Need to Build (Frontend)

### 1. Receiving Screen (`/receiving`)

**Purpose**: Upload packing slip, verify draft lines, commit to inventory

**Components**:
- `ReceivingUpload.tsx` - Camera/file upload
- `DraftLinesTable.tsx` - Verification table with checkboxes
- `PartMatcher.tsx` - Match suggestions for unmatched items
- `ReceivingCommit.tsx` - Commit button (HOD only)

**API Calls**:
```javascript
// Upload flow
POST /api/v1/intake/upload               → Upload packing slip
GET  /api/v1/sessions/{id}/draft-lines   → Get extracted lines
POST /api/v1/reconciliation/suggest      → Get match suggestions
POST /api/v1/sessions/{id}/update        → Update line matching
POST /api/v1/sessions/{id}/commit        → Commit (creates inventory events)
```

**State Management**:
```javascript
const [session, setSession] = useState(null);
const [draftLines, setDraftLines] = useState([]);
const [ticked, setTicked] = useState(new Set());
const [elapsedSeconds, setElapsedSeconds] = useState(0);  // For lazy workflow protection

// Upload
const handleUpload = async (file) => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${BASE_URL}/intake/upload`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${token}` },
    body: formData
  });

  const { session_id } = await response.json();
  setSession({ id: session_id });

  // Fetch draft lines
  const linesResponse = await fetch(`${BASE_URL}/sessions/${session_id}/draft-lines`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });

  const { lines } = await linesResponse.json();
  setDraftLines(lines);
};

// Commit
const handleCommit = async () => {
  const tickedLines = draftLines.filter(line => ticked.has(line.line_id));

  const response = await fetch(`${BASE_URL}/sessions/${session.id}/commit`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      lines: tickedLines,
      elapsed_seconds: elapsedSeconds,
      confirmed: false  // Will prompt if too fast
    })
  });

  const result = await response.json();

  if (result.requires_confirmation) {
    // Show interstitial: "You confirmed 30 items. Proceed?"
    if (confirm(result.message)) {
      // Retry with confirmed: true
      handleCommit(true);
    }
  } else {
    // Success - navigate to label generation or inventory
    navigate('/inventory');
  }
};
```

### 2. Label Generation Screen (`/receiving/labels`)

**Purpose**: Generate printable labels after receiving

**Components**:
- `LabelPreview.tsx` - Preview label layout
- `LabelDownload.tsx` - Download PDF/email options

**API Calls**:
```javascript
POST /api/v1/label-generation/parts/pdf  → Generate labels
GET  /api/v1/label-generation/parts/{id}/qr → Get QR code
```

### 3. Shipping Label Screen (`/receiving/shipping-label`)

**Purpose**: Process shipping labels to link with orders

**Components**:
- `ShippingLabelUpload.tsx` - Upload label photo
- `OrderMatcher.tsx` - Match to purchase orders

**API Calls**:
```javascript
POST /api/v1/labels/process              → Extract metadata
POST /api/v1/labels/link-to-order        → Link to PO
```

### 4. Discrepancy Photo Screen (`/receiving/discrepancy`)

**Purpose**: Attach photos to damaged/missing items

**Components**:
- `DiscrepancyPhotoUpload.tsx` - Camera capture
- `DiscrepancyForm.tsx` - Discrepancy details

**API Calls**:
```javascript
POST /api/v1/photos/attach/discrepancy   → Attach photo
GET  /api/v1/photos/work_order/{id}      → Get attached photos
```

### 5. Pending Sessions Screen (`/receiving/pending`)

**Purpose**: View incomplete receiving sessions (for HOD review)

**Components**:
- `PendingSessionsList.tsx` - List of abandoned sessions
- `SessionReview.tsx` - Review and complete session

**API Calls**:
```javascript
GET /api/v1/sessions/pending             → List pending sessions
GET /api/v1/sessions/{id}                → Get session details
```

---

## 🏗️ Frontend API Client (Recommended)

Create a centralized API client:

```typescript
// lib/imageProcessingApi.ts
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

const API_BASE = process.env.NEXT_PUBLIC_IMAGE_API_URL || 'http://localhost:8001/api/v1';

class ImageProcessingAPI {
  private async getAuthToken(): Promise<string> {
    const { data: { session } } = await supabase.auth.getSession();
    if (!session) throw new Error('Not authenticated');
    return session.access_token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = await this.getAuthToken();

    const response = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers: {
        'Authorization': `Bearer ${token}`,
        ...options.headers
      }
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'API request failed');
    }

    return response.json();
  }

  // Intake
  async uploadPackingSlip(file: File): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('type', 'packing_slip');

    const token = await this.getAuthToken();
    const response = await fetch(`${API_BASE}/intake/upload`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    });

    return response.json();
  }

  // Sessions
  async getDraftLines(sessionId: string): Promise<DraftLinesResponse> {
    return this.request(`/sessions/${sessionId}/draft-lines`);
  }

  async commitSession(
    sessionId: string,
    lines: DraftLine[],
    elapsedSeconds: number,
    confirmed: boolean = false
  ): Promise<CommitResponse> {
    return this.request(`/sessions/${sessionId}/commit`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lines, elapsed_seconds: elapsedSeconds, confirmed })
    });
  }

  // Reconciliation
  async getMatchSuggestions(
    partNumber: string,
    description: string
  ): Promise<MatchSuggestion[]> {
    return this.request(`/reconciliation/suggest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ part_number: partNumber, description })
    });
  }

  // Label Generation
  async generatePartLabels(partIds: string[]): Promise<Blob> {
    const token = await this.getAuthToken();

    const response = await fetch(`${API_BASE}/label-generation/parts/pdf`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ part_ids: partIds })
    });

    return response.blob();
  }
}

export const imageAPI = new ImageProcessingAPI();

// Types
export interface UploadResponse {
  session_id: string;
  status: string;
  image_id: string;
  upload_url: string;
}

export interface DraftLine {
  line_id: string;
  extracted_text: string;
  quantity: number;
  unit: string;
  part_number: string;
  description: string;
  suggested_match?: MatchSuggestion;
}

export interface MatchSuggestion {
  part_id: string;
  part_number: string;
  name: string;
  confidence: number;
  match_type: 'exact' | 'fuzzy_part_number' | 'fuzzy_description';
  boost_factors?: string[];
}

export interface CommitResponse {
  success: boolean;
  requires_confirmation?: boolean;
  message?: string;
  session_id?: string;
  committed_at?: string;
}
```

**Usage in Components**:
```typescript
import { imageAPI } from '@/lib/imageProcessingApi';

// In component
const handleUpload = async (file: File) => {
  try {
    const result = await imageAPI.uploadPackingSlip(file);
    const lines = await imageAPI.getDraftLines(result.session_id);
    setDraftLines(lines.lines);
  } catch (error) {
    toast.error(error.message);
  }
};
```

---

## 🔄 Environment Variables for Frontend

Create `.env.local`:

```bash
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Image Processing API
NEXT_PUBLIC_IMAGE_API_URL=https://image-processing-api.onrender.com/api/v1

# For local development
# NEXT_PUBLIC_IMAGE_API_URL=http://localhost:8001/api/v1
```

---

## 📊 Monitoring & Logs

### Render Dashboard

- **Logs**: Real-time streaming logs
- **Metrics**: CPU, memory, requests/second
- **Health**: Automatic health check at `/health`

### Supabase Dashboard

- **Database**: Query editor, table browser
- **Storage**: View uploaded images
- **Auth**: User management
- **Logs**: Database and API logs

### Custom Monitoring Endpoints

```
GET /api/v1/system/status       → Current status
GET /api/v1/system/metrics      → Usage metrics
GET /api/v1/system/cost-report  → Cost breakdown
```

---

## 🚨 Troubleshooting

### Build Fails on Render

```bash
# Check Python version
cat runtime.txt  # Should say: python-3.10

# Check dependencies
cat requirements.txt

# Common issue: Missing system dependencies for Tesseract
# Solution: Use Docker deployment (already configured in render.yaml)
```

### API Returns 500 Error

```bash
# Check Render logs
# Look for:
- Database connection errors (check SUPABASE_URL)
- Missing environment variables
- Import errors (missing dependencies)
```

### CORS Errors from Frontend

```bash
# Check ALLOWED_ORIGINS includes your frontend domain
ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000

# In Render dashboard, update environment variable
```

### Authentication Fails

```bash
# Verify JWT_SECRET is set in Render
# Verify Supabase keys are correct
# Check token expiry (refresh if needed)
```

---

## ✅ Deployment Checklist

- [ ] 1. Push code to GitHub
- [ ] 2. Create Render web service from repo
- [ ] 3. Set all environment variables in Render dashboard
- [ ] 4. Deploy atomic operations migration to Supabase
- [ ] 5. Wait for build to complete (~10 minutes)
- [ ] 6. Check `/health` endpoint returns 200
- [ ] 7. Test upload with Postman/curl
- [ ] 8. Update frontend `NEXT_PUBLIC_IMAGE_API_URL`
- [ ] 9. Test full receiving flow from frontend
- [ ] 10. Monitor logs for errors in first 24 hours

---

## 📖 API Documentation

Full API docs available at:
- **Swagger UI**: `https://image-processing-api.onrender.com/docs`
- **ReDoc**: `https://image-processing-api.onrender.com/redoc`

---

**Status**: Ready for deployment
**Estimated Setup Time**: 30-60 minutes
**Cost**: $7/month (Starter plan) + Supabase free tier + OpenAI usage (~$3/month)

**Next Steps**:
1. Set environment variables in Render
2. Deploy to Render
3. Test API endpoints
4. Build frontend receiving screens
5. Integrate with Cloud_PMS
