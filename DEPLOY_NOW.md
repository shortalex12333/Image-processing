# 🚀 Deploy to Render - Quick Start

**Status**: ✅ Production-ready with critical fixes applied

---

## ⚡ Quick Deploy (5 minutes)

### Step 1: Push to GitHub (1 minute)

```bash
# Add all files
git add .

# Commit
git commit -m "Complete image processing service with critical security fixes

- XSS protection implemented
- Race condition fixes with atomic operations
- Abuse protection middleware
- Comprehensive testing (74 tests)
- Production ready with all documentation

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Push to GitHub
git push -u origin main
```

**Wait for push to complete before proceeding!**

---

### Step 2: Create Render Web Service (2 minutes)

1. Go to: https://dashboard.render.com/
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository: `https://github.com/shortalex12333/Image-processing`

---

### Step 3: Configure Service (2 minutes)

**Basic Settings:**
```
Name:               image-processing-api
Language:           Python (NOT Node!)
Branch:             main
Root Directory:     [LEAVE EMPTY]
Build Command:      pip install --upgrade pip && pip install -r requirements.txt
Start Command:      uvicorn src.main:app --host 0.0.0.0 --port $PORT
Instance Type:      Starter ($7/month)
```

**⚠️ CRITICAL: Change Language from Node to Python!**

---

### Step 4: Add Environment Variables (2 minutes)

Click **"Advanced"** → **"Add Environment Variable"** for each:

#### Required Immediately:
```bash
PYTHON_VERSION=3.10
ENVIRONMENT=production
LOG_LEVEL=info
```

#### Supabase (get from: Supabase Dashboard → Settings → API)
```bash
SUPABASE_URL=https://[YOUR-PROJECT].supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...[SERVICE_ROLE]
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...[ANON_KEY]
```

#### OpenAI (get from: https://platform.openai.com/api-keys)
```bash
OPENAI_API_KEY=sk-proj-...[YOUR_KEY]
```

#### JWT (generate with: `openssl rand -base64 32`)
```bash
JWT_SECRET=[GENERATE_NOW]
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
```

#### CORS & Limits
```bash
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
MAX_UPLOAD_SIZE_MB=15
UPLOAD_RATE_LIMIT_PER_HOUR=50
MAX_COST_PER_SESSION=0.50
MAX_LLM_CALLS_PER_SESSION=3
STORAGE_BACKEND=supabase
```

---

### Step 5: Deploy! (10 minutes build time)

1. Click **"Create Web Service"**
2. Watch build logs for errors
3. Wait for **"Live"** status

---

### Step 6: Deploy Database Migration

**⚠️ CRITICAL: Must run before API is functional**

```bash
# Connect to Supabase
psql "postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres"

# Run migration
\i migrations/20260109_atomic_operations.sql

# Verify
SELECT proname FROM pg_proc WHERE proname LIKE 'atomic%';
# Should return: atomic_deduct_inventory, atomic_commit_session, get_part_stock_with_lock
```

**Get connection string from**: Supabase → Settings → Database → Connection string (URI)

---

### Step 7: Verify Deployment

```bash
# Test health endpoint
curl https://image-processing-api.onrender.com/health

# Expected:
{
  "status": "healthy",
  "service": "image-processing-api",
  "version": "1.0.0"
}

# Test API docs
open https://image-processing-api.onrender.com/docs
```

---

## 🔑 Where to Get Credentials

### Supabase Keys
1. Go to: https://supabase.com/dashboard
2. Select your Cloud_PMS project
3. Click: **Settings** (gear icon) → **API**
4. Copy:
   - **Project URL** → SUPABASE_URL
   - **service_role** (click Reveal) → SUPABASE_SERVICE_KEY
   - **anon** (click Reveal) → SUPABASE_ANON_KEY

### OpenAI API Key
1. Go to: https://platform.openai.com/api-keys
2. Click: **"Create new secret key"**
3. Name: "Cloud PMS Image Processing"
4. Copy key (starts with `sk-proj-`)
5. **SAVE NOW** - can't see again!

### JWT Secret
```bash
# Generate on Mac/Linux:
openssl rand -base64 32

# Or Python:
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Supabase Database Password
1. Supabase → Settings → Database
2. Look for "Connection string"
3. Password is in your Supabase account settings

---

## 📋 Pre-Deploy Checklist

- [ ] All files committed to git
- [ ] Pushed to GitHub repository
- [ ] Render account created
- [ ] GitHub repo connected to Render
- [ ] Language set to **Python** (NOT Node)
- [ ] All 16 environment variables added
- [ ] Supabase keys obtained
- [ ] OpenAI API key obtained
- [ ] JWT secret generated
- [ ] ALLOWED_ORIGINS updated with your frontend URL

---

## 🧪 Post-Deploy Testing

```bash
# 1. Health check
curl https://image-processing-api.onrender.com/health

# 2. Get auth token from Supabase
TOKEN="your-supabase-jwt-here"

# 3. Test upload endpoint
curl -X POST https://image-processing-api.onrender.com/api/v1/intake/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@/path/to/test.pdf"

# 4. Expected response
{
  "session_id": "uuid",
  "status": "processing",
  "image_id": "uuid"
}
```

---

## 🚨 Troubleshooting

### Build fails: "Could not find Python 3.10"
- Check: PYTHON_VERSION=3.10 in environment variables
- Check: Language is "Python" not "Node"

### Build fails: "No module named 'src'"
- Check: Root directory is EMPTY (not "src")
- Check: Start command is `uvicorn src.main:app --host 0.0.0.0 --port $PORT`

### Service fails: "Supabase connection failed"
- Check: SUPABASE_URL has no trailing slash
- Check: SUPABASE_SERVICE_KEY is service_role (not anon)
- Check: Keys are from correct project

### Upload fails: "CORS error"
- Check: ALLOWED_ORIGINS includes your frontend URL
- Check: No spaces in ALLOWED_ORIGINS (commas only)

---

## 📚 Full Documentation

- **Detailed deployment**: See `RENDER_DEPLOYMENT_COMPLETE.md`
- **Frontend integration**: See `FRONTEND_INTEGRATION.md`
- **Security fixes**: See `CRITICAL_FIXES_APPLIED.md`
- **Testing evidence**: See `HARD_EVIDENCE_REPORT.md`

---

## 💰 Monthly Cost

```
Render Starter:    $7/month
OpenAI usage:      ~$3/month (100 sessions)
─────────────────
Total:             $10/month
```

---

## ✅ Success Criteria

After deployment, you should be able to:
- ✅ Access `/health` endpoint
- ✅ View `/docs` for Swagger UI
- ✅ Upload packing slip PDF
- ✅ Get draft lines with match suggestions
- ✅ Commit receiving session
- ✅ Generate labels
- ✅ Process shipping labels
- ✅ Attach photos to discrepancies

---

**Your API will be live at**: `https://image-processing-api.onrender.com/api/v1`

**Next step**: Update your frontend's `NEXT_PUBLIC_IMAGE_API_URL` environment variable 🎉
