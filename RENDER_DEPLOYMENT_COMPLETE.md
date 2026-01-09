# Complete Render Deployment Guide
## Step-by-Step with All Credentials

---

## STEP 1: Update GitHub Repository First

### 1.1 Navigate to Project Directory

```bash
cd /private/tmp/Image-processing
```

### 1.2 Initialize Git (if not already)

```bash
# Check if git is initialized
git status

# If not initialized, run:
git init
git branch -M main
```

### 1.3 Add Remote Repository

```bash
# Add your GitHub repo
git remote add origin https://github.com/shortalex12333/Image-processing.git

# Or if already exists, update it:
git remote set-url origin https://github.com/shortalex12333/Image-processing.git
```

### 1.4 Commit and Push ALL Code

```bash
# Add all files
git add .

# Commit with message
git commit -m "Complete image processing service with critical security fixes

- XSS protection implemented
- Race condition fixes with atomic operations
- Abuse protection middleware
- Comprehensive testing (74 tests)
- Production ready with all documentation"

# Push to GitHub
git push -u origin main
```

**IMPORTANT**: Wait for push to complete before proceeding to Render!

---

## STEP 2: Render Dashboard Configuration

### 2.1 Source Code Section

**Field: Public Git Repository**
```
https://github.com/shortalex12333/Image-processing
```

✓ You already selected this - leave as is

---

### 2.2 Name Your Service

**Field: Name**
```
image-processing-api
```

**Why this name?**
- Your frontend will use: `https://image-processing-api.onrender.com/api/v1`
- Clear, descriptive, follows convention
- Matches all documentation

---

### 2.3 Project (Optional)

**Leave blank for now** or create:
```
Project Name: cloud-pms-production
```

---

### 2.4 Language

**Select: Python** (NOT Node!)

Current setting shows "Node" - **CHANGE THIS TO PYTHON**

---

### 2.5 Branch

**Field: Branch**
```
main
```

✓ Already correct

---

### 2.6 Region

**Field: Region**
```
Oregon (US West)
```

✓ Already correct - keep with your other 8 services

---

### 2.7 Root Directory

**Field: Root Directory**
```
[LEAVE EMPTY]
```

Do NOT set a root directory - we want the repository root.

---

### 2.8 Build Command

**Field: Build Command**
```bash
pip install --upgrade pip && pip install -r requirements.txt
```

**What this does:**
- Upgrades pip to latest version
- Installs all dependencies from requirements.txt
- Includes: FastAPI, OpenCV, Tesseract, pdfplumber, etc.

---

### 2.9 Start Command

**Field: Start Command**
```bash
uvicorn src.main:app --host 0.0.0.0 --port $PORT
```

**What this does:**
- Starts FastAPI server with Uvicorn
- Binds to 0.0.0.0 (all interfaces)
- Uses Render's $PORT environment variable (automatically set)

---

### 2.10 Instance Type

**Select: Starter ($7/month)**

**Why Starter?**
- 512 MB RAM (sufficient for image processing)
- 0.5 CPU (handles OCR workload)
- Zero downtime deploys
- SSH access for debugging
- Can scale up later if needed

**DO NOT use Free tier** - it has:
- No persistent storage
- Spins down after inactivity
- Slower cold starts
- Not suitable for production

---

## STEP 3: Environment Variables (CRITICAL!)

Click **"Add Environment Variable"** for each of these:

### 3.1 Python Version

```
NAME:  PYTHON_VERSION
VALUE: 3.10
```

---

### 3.2 Environment

```
NAME:  ENVIRONMENT
VALUE: production
```

---

### 3.3 Log Level

```
NAME:  LOG_LEVEL
VALUE: info
```

---

### 3.4 Supabase URL

**WHERE TO FIND**: Supabase Dashboard → Project Settings → API → Project URL

```
NAME:  SUPABASE_URL
VALUE: https://[YOUR-PROJECT-ID].supabase.co

Example: https://abcdefghijklmnop.supabase.co
```

**How to get this:**
1. Go to https://supabase.com/dashboard
2. Select your Cloud_PMS project
3. Click Settings (gear icon) → API
4. Copy "Project URL"

---

### 3.5 Supabase Service Role Key (SECRET!)

**WHERE TO FIND**: Supabase Dashboard → Project Settings → API → service_role key

```
NAME:  SUPABASE_SERVICE_KEY
VALUE: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IltQUk9KRUNUX0lEXSIsInJvbGUiOiJzZXJ2aWNlX3JvbGUiLCJpYXQiOjE2ODEyMzQ1NjcsImV4cCI6MTk5NjgxMDU2N30...

⚠️  KEEP THIS SECRET!
```

**How to get this:**
1. Same page: Settings → API
2. Look for "service_role" key (NOT anon key!)
3. Click "Reveal" button
4. Copy entire JWT token (long string starting with eyJ...)

**WARNING**: This key bypasses RLS - never expose to frontend!

---

### 3.6 Supabase Anon Key (Public)

**WHERE TO FIND**: Supabase Dashboard → Project Settings → API → anon/public key

```
NAME:  SUPABASE_ANON_KEY
VALUE: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6IltQUk9KRUNUX0lEXSIsInJvbGUiOiJhbm9uIiwiaWF0IjoxNjgxMjM0NTY3LCJleHAiOjE5OTY4MTA1Njd9...

This is safe to expose (RLS protects data)
```

**How to get this:**
1. Same page: Settings → API
2. Look for "anon" or "public" key
3. Click "Reveal" button
4. Copy entire JWT token

---

### 3.7 OpenAI API Key (SECRET!)

**WHERE TO FIND**: OpenAI Dashboard → API Keys

```
NAME:  OPENAI_API_KEY
VALUE: sk-proj-abcdefghijklmnopqrstuvwxyz1234567890ABCDEFGHIJKLMNOPQR

⚠️  KEEP THIS SECRET!
```

**How to get this:**
1. Go to https://platform.openai.com/api-keys
2. Click "Create new secret key"
3. Name it: "Cloud PMS Image Processing"
4. Copy the key (starts with sk-proj- or sk-)
5. **SAVE IT NOW** - you can't see it again!

**If you don't have an OpenAI key yet:**
1. Sign up at https://platform.openai.com/signup
2. Add payment method (required for API access)
3. Set usage limits: $10/month
4. Create API key

**Cost**: ~$3/month for 100 sessions (mostly $0, only 30% need LLM)

---

### 3.8 JWT Secret (SECRET!)

**GENERATE A NEW ONE** - do NOT use an existing key!

```
NAME:  JWT_SECRET
VALUE: [GENERATE THIS NOW - see below]

⚠️  KEEP THIS SECRET!
```

**How to generate (choose one method):**

**Option A: Using openssl (Mac/Linux)**
```bash
openssl rand -base64 32
```

**Option B: Using Python**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Option C: Using online generator**
- Go to: https://www.grc.com/passwords.htm
- Copy the "63 random alpha-numeric characters" string

**Example output:**
```
vQz8X3mN9pL2kR5sT7wY1aB4cD6eF8gH0iJ2kL4mN6oP8qR0sT2uV4wX6yZ8A0C=
```

Copy this value and paste into Render.

---

### 3.9 JWT Algorithm

```
NAME:  JWT_ALGORITHM
VALUE: HS256
```

---

### 3.10 JWT Expiry

```
NAME:  JWT_EXPIRE_MINUTES
VALUE: 1440
```

(1440 minutes = 24 hours)

---

### 3.11 CORS Allowed Origins

**YOUR FRONTEND DOMAINS** - update these!

```
NAME:  ALLOWED_ORIGINS
VALUE: https://your-cloud-pms-frontend.vercel.app,http://localhost:3000,http://localhost:3001

⚠️  REPLACE with your actual frontend URLs!
```

**How to set this:**
1. If you have a production frontend: `https://cloud-pms.yourdomain.com`
2. If using Vercel: `https://your-app.vercel.app`
3. Always include localhost for local development
4. Separate multiple URLs with commas (NO SPACES!)

**Examples:**
```
# Production + local dev
https://cloud-pms.render.com,http://localhost:3000

# Multiple environments
https://cloud-pms.com,https://staging.cloud-pms.com,http://localhost:3000
```

---

### 3.12 Max Upload Size

```
NAME:  MAX_UPLOAD_SIZE_MB
VALUE: 15
```

---

### 3.13 Upload Rate Limit

```
NAME:  UPLOAD_RATE_LIMIT_PER_HOUR
VALUE: 50
```

---

### 3.14 Max Cost Per Session

```
NAME:  MAX_COST_PER_SESSION
VALUE: 0.50
```

(50 cents per session cap)

---

### 3.15 Max LLM Calls Per Session

```
NAME:  MAX_LLM_CALLS_PER_SESSION
VALUE: 3
```

---

### 3.16 Storage Backend

```
NAME:  STORAGE_BACKEND
VALUE: supabase
```

---

## SUMMARY OF ALL ENVIRONMENT VARIABLES

Copy this checklist and fill in your values:

```bash
# Python
PYTHON_VERSION=3.10

# Application
ENVIRONMENT=production
LOG_LEVEL=info

# Supabase (GET FROM SUPABASE DASHBOARD)
SUPABASE_URL=https://[YOUR-PROJECT].supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...[SERVICE_ROLE_KEY]
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...[ANON_KEY]

# OpenAI (GET FROM OPENAI DASHBOARD)
OPENAI_API_KEY=sk-proj-...[YOUR_OPENAI_KEY]

# JWT (GENERATE NEW)
JWT_SECRET=[GENERATE_WITH_OPENSSL]
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# CORS (UPDATE WITH YOUR FRONTEND URL)
ALLOWED_ORIGINS=https://your-frontend.vercel.app,http://localhost:3000

# Limits
MAX_UPLOAD_SIZE_MB=15
UPLOAD_RATE_LIMIT_PER_HOUR=50
MAX_COST_PER_SESSION=0.50
MAX_LLM_CALLS_PER_SESSION=3
STORAGE_BACKEND=supabase
```

---

## STEP 4: Deploy!

After setting ALL environment variables:

1. **Scroll down**
2. Click **"Create Web Service"**
3. Wait for build (~10 minutes)

### Build Process:
```
1. Cloning repository...
2. Installing Python 3.10...
3. Installing dependencies...
4. Building Docker image...
5. Starting service...
6. Running health check...
7. ✅ Deployment successful!
```

---

## STEP 5: Verify Deployment

### 5.1 Check Health Endpoint

Once deployed, test:

```bash
curl https://image-processing-api.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "image-processing-api",
  "version": "1.0.0",
  "timestamp": "2026-01-09T..."
}
```

### 5.2 Check API Docs

Open in browser:
```
https://image-processing-api.onrender.com/docs
```

You should see Swagger UI with all endpoints.

---

## STEP 6: Deploy Database Migration

**CRITICAL**: Before API is fully functional, deploy atomic operations:

```bash
# Connect to Supabase
psql "postgresql://postgres:[YOUR_PASSWORD]@db.[YOUR_PROJECT].supabase.co:5432/postgres"

# Run migration
\i migrations/20260109_atomic_operations.sql

# Verify functions created
SELECT proname FROM pg_proc
WHERE proname IN ('atomic_deduct_inventory', 'atomic_commit_session')
AND pronamespace = 'public'::regnamespace;

# Should return 3 rows
```

**Where to get Supabase connection string:**
1. Supabase Dashboard → Project Settings → Database
2. Look for "Connection string" → "URI"
3. Replace `[YOUR-PASSWORD]` with your database password

---

## STEP 7: Test with Postman

### 7.1 Get Auth Token

First, log in to get a Supabase JWT:

```bash
curl -X POST 'https://[YOUR-PROJECT].supabase.co/auth/v1/token?grant_type=password' \
  -H "apikey: [YOUR_ANON_KEY]" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-user@example.com",
    "password": "your-password"
  }'
```

Copy the `access_token` from response.

### 7.2 Test Upload

```bash
curl -X POST 'https://image-processing-api.onrender.com/api/v1/intake/upload' \
  -H "Authorization: Bearer [YOUR_ACCESS_TOKEN]" \
  -F "file=@/path/to/test-packing-slip.pdf"
```

Expected response:
```json
{
  "session_id": "uuid-here",
  "status": "processing",
  "image_id": "uuid-here",
  "upload_url": "https://..."
}
```

---

## TROUBLESHOOTING

### Build Fails

**Error: "Could not find Python 3.10"**
- Check: `PYTHON_VERSION=3.10` is set in environment variables
- Check: Language is set to "Python" (not Node)

**Error: "No module named 'src'"**
- Check: Root directory is EMPTY (not set to "src")
- Check: Start command is `uvicorn src.main:app --host 0.0.0.0 --port $PORT`

**Error: "Could not install requirements"**
- Check: requirements.txt exists in repository root
- Check: Build command is `pip install --upgrade pip && pip install -r requirements.txt`

### Service Fails to Start

**Error: "Supabase connection failed"**
- Check: `SUPABASE_URL` is correct (no trailing slash)
- Check: `SUPABASE_SERVICE_KEY` is the service_role key (not anon)

**Error: "OpenAI API error"**
- Check: `OPENAI_API_KEY` starts with `sk-`
- Check: OpenAI account has credits
- Check: Usage limits not exceeded

**Error: "CORS error from frontend"**
- Check: `ALLOWED_ORIGINS` includes your frontend URL
- Check: No spaces in ALLOWED_ORIGINS (use commas only)

### Health Check Fails

```bash
# Check logs in Render dashboard
# Look for startup errors

# Common issues:
- Missing environment variables
- Database connection timeout
- Port not binding correctly
```

---

## QUICK REFERENCE CARD

**Service URL**: `https://image-processing-api.onrender.com`
**API Base**: `https://image-processing-api.onrender.com/api/v1`
**Health Check**: `https://image-processing-api.onrender.com/health`
**API Docs**: `https://image-processing-api.onrender.com/docs`

**Frontend Environment Variable**:
```bash
NEXT_PUBLIC_IMAGE_API_URL=https://image-processing-api.onrender.com/api/v1
```

**Cost**: $7/month (Starter plan) + ~$3/month (OpenAI usage)

---

## NEXT STEPS

1. ✅ Deploy to Render (above)
2. ✅ Deploy atomic operations migration
3. ✅ Test health endpoint
4. ✅ Test upload endpoint with Postman
5. 🔄 Update frontend to use new API
6. 🔄 Build receiving screen components
7. 🔄 Test full workflow
8. 🔄 Monitor logs for first 24 hours

---

**Status**: Complete deployment guide with all credentials
**Time**: 30-60 minutes for full deployment
**Support**: Check Render logs if any issues
