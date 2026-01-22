# Handover Document
**For**: Next Engineer
**From**: Claude Sonnet 4.5 (2026-01-22 session)
**Status**: Feature development frozen, system in uncertain production state

---

## If You Have 1 Hour

### Do This First

1. **Verify Production Is Actually Running**
   ```bash
   curl https://image-processing-givq.onrender.com/health
   ```

   - **If 200 OK**: Service is up
   - **If 502/503**: Service crashed, check Render logs
   - **If timeout**: Service doesn't exist or domain wrong

2. **Check Render Dashboard**
   - URL: https://dashboard.render.com/web/srv-d5gou9qdbo4c73dg61u0
   - Look at "Events" tab
   - **Question**: When was last successful deployment?
   - **Question**: What commit is currently deployed?

3. **Check GitHub Webhook**
   - URL: https://github.com/shortalex12333/Image-processing/settings/hooks
   - **Question**: Does a Render webhook exist?
   - **Question**: Are recent deliveries successful?
   - **If missing**: Auto-deploy is broken, reconnect repo in Render

**Why**: Without knowing production status, all other work is blind.

---

## If You Have 1 Day

### Morning: Verify Core Functionality

1. **Test Production Authentication**
   ```bash
   # Get JWT from Supabase
   JWT=$(curl -X POST "https://vzsohavtuotocgrfkfyd.supabase.co/auth/v1/token?grant_type=password" \
     -H "apikey: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
     -H "Content-Type: application/json" \
     -d '{"email":"x@alex-short.com","password":"TestPassword123!"}' \
     | jq -r '.access_token')

   # Test upload
   curl -X POST "https://image-processing-givq.onrender.com/api/v1/images/upload" \
     -H "Authorization: Bearer $JWT" \
     -F "files=@test_image.png" \
     -F "upload_type=receiving"
   ```

   **Expected**: 200 OK with upload confirmation
   **If 401**: Auth broken
   **If 500**: Internal error, check logs
   **If 502**: Service crashed

2. **Verify Database Schema**
   ```sql
   -- Connect to Supabase and run:
   \d pms_image_uploads

   -- Critical question: Does it have column "id" or "image_id"?
   -- Code expects "id" but migration created "image_id"
   ```

   **If mismatch**: Apply schema fix or update code

3. **Check Environment Variables**
   - Render Dashboard → Environment tab
   - **Must have**:
     - `NEXT_PUBLIC_SUPABASE_URL`
     - `SUPABASE_SERVICE_ROLE_KEY`
     - `ENABLE_GOOGLE_VISION=true`
     - `GOOGLE_VISION_API_KEY`
   - **Missing any**: Add them and redeploy

### Afternoon: Fix What's Broken

Based on morning findings, prioritize:

1. **If production is down**: Get it running first
2. **If auth is broken**: Fix Supabase environment variables
3. **If schema is wrong**: Apply migration or fix code
4. **If auto-deploy is broken**: Reconnect GitHub webhook

**Don't add features until core works.**

---

## If You Have 1 Week

### Day 1-2: Production Stability

**Goal**: Prove the service actually works in production

Tasks:
1. Fix any issues from "1 Day" checklist above
2. Test upload with real image
3. Verify OCR processing completes
4. Verify database writes succeed
5. Test deduplication (upload same image twice)
6. Test rate limiting (upload 51 times in 1 hour)

**Definition of Done**:
- Can upload image to production
- Get 200 OK response
- See record in `pms_image_uploads` table
- Duplicate upload returns existing record

### Day 3: Apply Database Migrations

**Current State**: Migrations exist but status unknown

Tasks:
1. Dump current production schema
2. Compare to migration files
3. Identify missing columns/indexes
4. **Critical**: Fix `id` vs `image_id` mismatch
5. Apply missing migrations (coordinate with team)
6. Verify all indexes exist

**Files**:
- `migrations/20260122_fix_image_uploads_schema.sql`
- But: Uses `image_id`, code uses `id`
- Fix: Either rename column or update migration

### Day 4: Enable RLS Policies

**Current State**: NO RLS exists, all queries manually filter by `yacht_id`

**Risk**: Human error could expose yacht data

Tasks:
1. Write RLS policies for `pms_image_uploads`:
   ```sql
   ALTER TABLE pms_image_uploads ENABLE ROW LEVEL SECURITY;

   CREATE POLICY "Yacht isolation on SELECT"
     ON pms_image_uploads FOR SELECT
     USING (yacht_id = auth.uid()::uuid); -- Adjust based on your auth setup

   CREATE POLICY "Yacht isolation on INSERT"
     ON pms_image_uploads FOR INSERT
     WITH CHECK (yacht_id = auth.uid()::uuid);
   ```

2. Test with user JWTs (not service key)
3. Verify yacht A cannot see yacht B's images

**Blocker**: Need to understand how Supabase auth works with your user model.

### Day 5: Set Up Monitoring

**Current State**: Zero visibility into production

Tasks:
1. Add Sentry or similar error tracking
2. Set up uptime monitoring (UptimeRobot, Pingdom)
3. Add logging for key operations:
   - Upload success/failure
   - OCR processing time
   - LLM invocation rate
   - Cost per session

4. Create dashboard for:
   - Uploads per day
   - OCR engine usage
   - Error rates
   - Storage costs

**Why**: You're flying blind without this.

### Day 6-7: Test Untested Code

**Current State**: Entire extraction/reconciliation pipeline untested

Pick one flow and test end-to-end:

**Option A**: Receiving workflow
```
Upload packing slip → OCR → Extract entities → Create draft lines
```

**Option B**: Label workflow
```
Upload shipping label → OCR → Extract tracking → Match to order
```

Test with real images from production use case.

Document what actually works vs what breaks.

---

## If Something Breaks in Production

### 1. Service Won't Start (502/503)

**Check Render Logs**:
```
Render Dashboard → Logs tab → Look for errors
```

**Common Causes**:
1. **Wrong OCR engine enabled**
   - PaddleOCR on 512MB plan = crash
   - Fix: Set `ENABLE_PADDLEOCR=false`, `ENABLE_GOOGLE_VISION=true`

2. **Missing environment variable**
   - Error: "supabase_url is required"
   - Fix: Add `NEXT_PUBLIC_SUPABASE_URL` in Render

3. **Import error**
   - Error: "ModuleNotFoundError: No module named 'paddleocr'"
   - Fix: Check `requirements.txt` has all dependencies

4. **Database connection failed**
   - Error: "Connection refused" or "Invalid API key"
   - Fix: Verify `SUPABASE_SERVICE_ROLE_KEY`

### 2. Authentication Fails (401)

**Error**: "Invalid token: Signature verification failed"

**This is the OLD code, not the new Supabase client auth.**

**Cause**: Deployment didn't update, still running old commit

**Fix**:
1. Check deployed commit in Render Events tab
2. If old commit, trigger manual deploy
3. If auto-deploy broken, reconnect GitHub webhook

---

**Error**: "User not associated with any yacht"

**This is the NEW code with correct auth.**

**Cause**: User doesn't have `yacht_id` in metadata

**Fix**:
```bash
# Use Supabase Admin API to set metadata
curl -X PUT "https://vzsohavtuotocgrfkfyd.supabase.co/auth/v1/admin/users/USER_ID" \
  -H "apikey: SERVICE_KEY" \
  -H "Authorization: Bearer SERVICE_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_metadata":{"yacht_id":"YACHT_UUID","role":"crew"}}'
```

### 3. Upload Fails (500)

**Check the error detail** in response JSON.

**Error**: "column pms_image_uploads.image_id does not exist"

**Cause**: Schema mismatch, code uses `id` but database has `image_id`

**Fix**: Apply schema migration or update code

---

**Error**: "Image quality too low (DQS: 62.2/100)"

**Cause**: Document Quality Score validation failed

**Fix** (if quality checks too strict):
```bash
# In Render, set:
DQS_THRESHOLD=0.0  # Disable quality checks temporarily
MIN_IMAGE_WIDTH=0
MIN_IMAGE_HEIGHT=0
```

---

**Error**: "No OCR engines available"

**Cause**: All feature flags are false

**Fix**: Enable at least one OCR engine:
```bash
ENABLE_GOOGLE_VISION=true
ENABLE_TESSERACT=true
```

### 4. Slow Uploads (Timeout)

**Cause**: Google Vision API slow or quota exceeded

**Check**:
1. Test API key directly:
   ```bash
   curl "https://vision.googleapis.com/v1/images:annotate?key=YOUR_KEY" \
     -d '{"requests":[{"image":{"content":"..."},"features":[{"type":"TEXT_DETECTION"}]}]}'
   ```

2. Check Google Cloud Console for quota limits

**Fix**:
- Increase timeout (currently 60s)
- Enable Tesseract as fallback
- Verify API key billing is enabled

### 5. Memory Issues (502 after upload)

**Cause**: Wrong OCR engine for plan size

**Current Plan**: Starter (512MB RAM)

**Compatible Engines**:
- ✅ Google Vision (~50MB)
- ✅ Tesseract (~50MB)
- ❌ PaddleOCR (~500MB) - will crash
- ❌ Surya (~4GB) - will crash

**Fix**:
```bash
ENABLE_PADDLEOCR=false
ENABLE_SURYA=false
ENABLE_GOOGLE_VISION=true
```

---

## What Must NOT Be Changed Casually

### 1. Authentication Method

**Current**: Supabase client validation (`supabase.auth.get_user()`)

**Why It Matters**: This eliminates JWT_SECRET synchronization issues

**Don't**:
- Switch back to manual JWT decode
- Bypass authentication for "testing"
- Remove yacht_id from auth context

**Risk**: Security vulnerability, data exposure

### 2. Database Column Names

**Critical**: Code now uses `id` everywhere, not `image_id`

**Files that touch this**:
- `src/intake/rate_limiter.py` (line 47)
- `src/intake/deduplicator.py` (lines 54, 70)
- `src/handlers/receiving_handler.py` (lines 229, 400)

**Don't**: Rename columns without updating all references

**Risk**: 500 errors, data loss

### 3. OCR Factory Pattern

**Current**: `OCRFactory.get_ocr_engine()` with feature flags

**Why It Matters**: Prevents hardcoded engine selection

**Don't**:
- Import OCR engines directly (e.g., `from src.ocr.paddleocr_ocr import PaddleOCR_Engine`)
- Instantiate engines manually
- Bypass feature flags

**Risk**: Wrong engine loads, service crashes on small plans

### 4. Yacht ID Filtering

**Critical**: Every database query MUST filter by `yacht_id`

**Pattern**:
```python
result = supabase.table("pms_image_uploads") \
    .select("*") \
    .eq("yacht_id", str(yacht_id)) \  # NEVER SKIP THIS
    .execute()
```

**Don't**:
- Query without yacht_id filter
- Use service key without manual filtering
- Assume RLS is enabled (it isn't)

**Risk**: Data leak between yachts

### 5. Deduplication Logic

**Current**: SHA256 hash with `(yacht_id, sha256_hash)` uniqueness

**Why It Matters**: Prevents duplicate storage costs

**Don't**:
- Remove SHA256 calculation
- Skip duplicate check
- Delete existing record on duplicate upload

**Risk**: Storage costs explode, duplicate processing

---

## What Assumptions Are Safe

### 1. Supabase Is External

**Safe to assume**:
- Database is managed by Supabase (not self-hosted)
- Migrations must be applied via Supabase dashboard or SQL
- RLS policies can be enabled anytime
- Service role key has full access

**Not safe**:
- Assuming schema matches migrations
- Assuming RLS is enabled
- Assuming other tables exist

### 2. This Is a Microservice

**Safe to assume**:
- This service only handles image processing
- Frontend exists elsewhere (not in this repo)
- Other services handle user management, equipment, etc.

**Not safe**:
- Assuming this service is standalone
- Assuming it owns the database schema
- Assuming it can modify other tables

### 3. Multi-Tenant by Yacht

**Safe to assume**:
- `yacht_id` is the tenant identifier
- All data must be isolated by yacht
- Users can belong to one yacht only (for this service)

**Not safe**:
- Assuming RLS handles isolation (it doesn't, manual filtering does)
- Assuming service role queries are safe (they bypass RLS)

### 4. Cost Matters

**Safe to assume**:
- Google Vision costs $1.50/1000 images
- PaddleOCR is free but needs 2GB RAM ($25/month)
- OpenAI LLM has per-token costs
- Free tier has limits

**Not safe**:
- Assuming current plan can handle any OCR engine
- Assuming OpenAI models like `gpt-4.1-*` exist (verify first)

### 5. Feature Flags Control Behavior

**Safe to assume**:
- Disabling an engine prevents it from loading
- Factory tries engines in priority order
- Configuration is read at startup

**Not safe**:
- Assuming feature flags hot-reload (they don't, need redeploy)
- Assuming disabled engines are completely uninstalled (dependencies still there)

---

## What Is Dangerously Incomplete

### 1. No RLS Policies

**Risk**: HIGH

**What's missing**: Row-level security on `pms_image_uploads`

**Current state**: Manual yacht_id filtering in every query

**Why it matters**: Human error could expose data

**What to do**: Add RLS policies (Day 4 of 1-week plan)

### 2. No Production Verification

**Risk**: HIGH

**What's missing**: Any proof that production works

**Current state**: Local Docker tested, production unknown

**Why it matters**: Could be completely broken

**What to do**: Test production (Day 1 of 1-week plan)

### 3. No Monitoring

**Risk**: MEDIUM

**What's missing**: Error tracking, uptime monitoring, cost tracking

**Current state**: Flying blind

**Why it matters**: Can't detect or debug issues

**What to do**: Add Sentry + metrics (Day 5)

### 4. Untested Extraction Pipeline

**Risk**: MEDIUM

**What's missing**: Any testing of LLM extraction, reconciliation, commit flow

**Current state**: Code exists but never run

**Why it matters**: Probably doesn't work

**What to do**: Test one flow end-to-end (Day 6-7)

### 5. No User Metadata Setup

**Risk**: MEDIUM

**What's missing**: Tool to set yacht_id in user metadata

**Current state**: Manual API calls required

**Why it matters**: New users get 403 errors

**What to do**: Write migration script or update signup flow

### 6. Schema Migrations Out of Sync

**Risk**: MEDIUM

**What's missing**: Verified production schema

**Current state**: Migration uses `image_id`, code uses `id`

**Why it matters**: Could break on fresh database

**What to do**: Audit production schema (Day 3)

### 7. Auto-Deploy Reliability

**Risk**: LOW (can deploy manually)

**What's missing**: Proven GitHub webhook

**Current state**: Uncertain, many "force redeploy" commits

**Why it matters**: Manual deploys are slow

**What to do**: Verify webhook or accept manual deploys

---

## Critical Files Map

### If You Need To...

**Change authentication**:
- `src/middleware/auth.py` (Supabase client validation)
- `src/database.py` (Supabase client initialization)

**Change OCR engine**:
- `render.yaml` or Render dashboard (set feature flags)
- `src/ocr/ocr_factory.py` (factory logic)
- Do NOT touch `src/handlers/receiving_handler.py` (uses factory)

**Change validation rules**:
- `src/intake/validator.py` (file type, size, quality checks)
- `src/config.py` (DQS thresholds, min dimensions)

**Change database queries**:
- `src/intake/deduplicator.py` (duplicate checks)
- `src/intake/rate_limiter.py` (rate limit queries)
- `src/handlers/receiving_handler.py` (main upload logic)

**Change API endpoints**:
- `src/routes/upload_routes.py` (upload endpoint)
- `src/main.py` (FastAPI app, router registration)

**Change deployment**:
- `render.yaml` (Render config)
- `Dockerfile` (container definition)
- `requirements.txt` (Python dependencies)

### Files That Should Not Exist

**Root level clutter** (59 markdown files):
- Many are redundant or from previous sessions
- Most Important: `README.md`, `SYSTEM_INVENTORY.md`, `HANDOVER.md` (this file)
- Safe to delete: All the "PHASE_*", "CRITICAL_FIX_*", "DEPLOYMENT_*" files

**Test files never committed**:
- `test_*.py` (100+ scripts at root)
- All JSON dumps (PADDLEOCR_RESULTS.json, etc.)
- `preprocessed/` directory
- `deployment/` directory (duplicate)

---

## Architecture Decisions Log

### Why Supabase Client Auth (Not Manual JWT)?

**Decision**: Use `supabase.auth.get_user(token)` instead of `jwt.decode()`

**Reason**:
- Eliminates JWT_SECRET synchronization issues
- Supabase handles signature verification
- Token revocation support
- Less code to maintain

**Trade-offs**:
- Requires Supabase (not portable)
- Requires user metadata setup
- Network call to Supabase on every request

**Status**: Implemented this session, tested locally, production untested

### Why OCR Factory Pattern?

**Decision**: Feature flags + factory instead of hardcoded engine

**Reason**:
- PaddleOCR needs 2GB RAM, Starter plan has 512MB
- Must support different engines for different plans
- No code changes needed to switch engines

**Trade-offs**:
- More complex than hardcoded import
- All engines still in dependencies (could slim down)

**Status**: Implemented this session, tested locally, production untested

### Why Manual Yacht Filtering (Not RLS)?

**Decision**: Manually filter queries by yacht_id, use service role key

**Reason**:
- RLS policies don't exist yet
- Service role key needed for background jobs
- Manual filtering is explicit

**Trade-offs**:
- Human error risk
- Every query must remember to filter
- No enforcement at database level

**Status**: Should add RLS as defense-in-depth

### Why No Test Suite?

**Reality**: Tests exist but never run

**Reason**: Unknown (probably timeline pressure)

**Risk**: Unknown if anything works

**What to do**:
- Run existing tests
- Fix what breaks
- Add to CI/CD

---

## Questions You'll Have

### Q: What commit is in production?
**A**: Unknown. Check Render Events tab. Could be any commit from last 2 weeks.

### Q: Does auto-deploy work?
**A**: Uncertain. Many "force redeploy" commits suggest it's been flaky. Latest fix (3af9ce7) added `repo` field to render.yaml which might help.

### Q: Is there a staging environment?
**A**: No. Only production.

### Q: Can I test locally?
**A**: Yes. Docker setup works:
```bash
cp .env.example .env.local
# Edit .env.local with your keys
docker build -t image-processing-local .
docker run -p 8001:8001 --env-file .env.local image-processing-local
```

### Q: Do the OpenAI models exist?
**A**: Unknown. Code references `gpt-4.1-nano`, `gpt-4.1-mini`, `gpt-4.1` but these might be placeholders. Verify with OpenAI API.

### Q: Where are the tests?
**A**: `tests/` directory has 25 test files. Never run. Unknown if they work.

### Q: Who owns this codebase?
**A**: Unknown. Contact information not in repo. "CelesteOS Team" mentioned in README.

### Q: Is there a frontend?
**A**: Not in this repo. Assumed to exist elsewhere.

### Q: What's the SLA?
**A**: Unknown. No monitoring, no alerts. If it's down, nobody knows.

---

## Red Flags to Watch For

1. **Silent Data Exposure**
   - Query without yacht_id filter
   - Service role key used carelessly
   - RLS bypass without explicit reason

2. **Memory Leaks**
   - 502 errors after running for hours
   - Restart service = works again
   - Sign of slow memory leak

3. **Cost Explosion**
   - LLM invocations > 30% of sessions
   - Google Vision API quota errors
   - Bill suddenly jumps

4. **Schema Drift**
   - Code expects columns that don't exist
   - Migrations applied out of order
   - Fresh database vs production schema differs

5. **Authentication Bypass**
   - Endpoints that skip auth check
   - Service role key hardcoded
   - JWT validation disabled "for testing"

---

## Final Advice

### Do First
1. Verify production works at all
2. Fix any critical breakage
3. Add monitoring so you know when it breaks
4. Document what you learn

### Do Soon
1. Apply database migrations
2. Enable RLS policies
3. Test one complete workflow
4. Clean up documentation clutter

### Do Eventually
1. Run test suite
2. Add CI/CD pipeline
3. Set up staging environment
4. Optimize OCR pipeline

### Don't Do
1. Add features before core is stable
2. Change authentication method casually
3. Deploy without testing locally first
4. Assume anything works without verifying

---

## How to Reach Me

I'm Claude Sonnet 4.5. I don't persist between sessions. Everything I know is in this document and `SYSTEM_INVENTORY.md`.

If you need clarification, search the commit history and the 59 markdown files at root level. Somebody wrote a lot of docs, though much is redundant.

Good luck. This system has potential but needs production validation urgently.

---

**End of Handover**
