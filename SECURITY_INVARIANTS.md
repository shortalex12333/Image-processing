# Security Invariants
**What Must Never Be Broken**

---

## Core Principle

**Yacht = Tenant. Data isolation is absolute.**

Every yacht's data must be completely invisible to every other yacht. No exceptions. No "admin view all" mode. No cross-yacht queries "just for analytics."

---

## Invariant 1: Yacht Isolation in Queries

### The Rule

**Every database query MUST filter by `yacht_id`.**

No query may return data from multiple yachts. No query may omit yacht filtering.

### Current Implementation

**Method**: Manual filtering (RLS not enabled)

```python
# CORRECT
result = supabase.table("pms_image_uploads") \
    .select("*") \
    .eq("yacht_id", str(yacht_id)) \
    .execute()

# WRONG - NEVER DO THIS
result = supabase.table("pms_image_uploads") \
    .select("*") \
    .execute()
```

### Status

**VIOLATED**: No enforcement at database level

**Risk**: Human error could expose data

**Mitigation Required**: Add RLS policies as defense-in-depth

```sql
ALTER TABLE pms_image_uploads ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Yacht isolation"
  ON pms_image_uploads
  USING (yacht_id = (current_setting('app.current_yacht_id')::uuid));
```

### How to Verify

**Test**:
1. Query as Yacht A
2. Verify response contains only Yacht A data
3. Query as Yacht B
4. Verify response contains only Yacht B data
5. Attempt cross-yacht query
6. Verify it fails or returns empty

**Never rely on client-side filtering.**

---

## Invariant 2: Authentication Required

### The Rule

**All API endpoints MUST require valid JWT authentication.**

No endpoints may be accessible without authentication. No "/debug" routes. No "internal-only" endpoints without auth.

### Current Implementation

**Method**: Supabase JWT validation

```python
@router.post("/images/upload")
async def upload_images(
    files: list[UploadFile],
    auth: AuthContext = Depends(get_auth_context)  # REQUIRED
):
    # auth.yacht_id is extracted from JWT
    # auth.user_id identifies who uploaded
```

### Exceptions

**Health check only**:
```python
@router.get("/health")
async def health_check():
    return {"status": "healthy"}
```

### Status

**ENFORCED**: Auth middleware protects all routes except `/health`

**Risk**: LOW (framework-level enforcement)

### How to Verify

**Test**:
```bash
# Without JWT - should fail
curl https://api/images/upload

# With invalid JWT - should fail
curl -H "Authorization: Bearer fake_token" https://api/images/upload

# With valid JWT - should succeed
curl -H "Authorization: Bearer $REAL_JWT" https://api/images/upload
```

---

## Invariant 3: User Metadata Contains yacht_id

### The Rule

**All authenticated users MUST have `yacht_id` in their Supabase user_metadata.**

Authentication fails if `yacht_id` is missing. No defaults. No assuming a yacht. No "guest mode."

### Current Implementation

```python
# In auth middleware
user_metadata = user.user_metadata or {}
yacht_id_str = user_metadata.get("yacht_id")

if not yacht_id_str:
    raise HTTPException(
        status_code=403,
        detail="User not associated with any yacht"
    )
```

### Status

**ENFORCED**: Auth middleware requires yacht_id

**Risk**: MEDIUM (no automated setup for new users)

### How to Set

**During user signup** (frontend):
```javascript
supabase.auth.signUp({
  email: 'user@example.com',
  password: 'password',
  options: {
    data: {
      yacht_id: 'uuid-here',
      role: 'crew'
    }
  }
})
```

**For existing users** (admin API):
```bash
curl -X PUT "https://PROJECT.supabase.co/auth/v1/admin/users/USER_ID" \
  -H "apikey: SERVICE_KEY" \
  -H "Authorization: Bearer SERVICE_KEY" \
  -d '{"user_metadata":{"yacht_id":"YACHT_UUID","role":"crew"}}'
```

### How to Verify

**Test**:
1. Create user without yacht_id
2. Attempt to call API
3. Verify 403 error
4. Add yacht_id to metadata
5. Verify API calls succeed

---

## Invariant 4: No Plaintext Secrets

### The Rule

**Secrets MUST NOT be stored in code, logs, or database.**

No API keys in code. No passwords in environment variable defaults. No secrets in commit history. No secrets in error messages.

### Current Implementation

**Correct**:
```python
# src/config.py
google_vision_api_key: Optional[str] = None  # From environment only

# Render environment variables
GOOGLE_VISION_API_KEY=AIzaSyC...  # Set in dashboard, not code
```

**Incorrect Examples** (don't do this):
```python
# WRONG - hardcoded secret
GOOGLE_API_KEY = "AIzaSyC1234567890"

# WRONG - default secret
api_key: str = "sk-test-key"

# WRONG - secret in logs
logger.info(f"Using API key: {api_key}")
```

### Status

**ENFORCED**: No defaults in config, environment only

**Risk**: LOW (code review enforces this)

### How to Verify

**Test**:
```bash
# Search codebase for potential secrets
grep -r "sk-" src/
grep -r "AIzaSy" src/
grep -r "password" src/ --include="*.py"

# Should find zero hardcoded secrets
```

---

## Invariant 5: SHA256 Prevents Duplicate Storage

### The Rule

**Files MUST be deduplicated by SHA256 hash before storage.**

No file is stored twice for the same yacht. Duplicate uploads return existing record. Storage costs are controlled.

### Current Implementation

```python
# Calculate hash
sha256 = hashlib.sha256(file_content).hexdigest()

# Check for duplicate
existing = await deduplicator.check_duplicate(sha256, yacht_id)

if existing:
    return existing  # Don't upload again
```

**Database constraint**:
```sql
CREATE UNIQUE INDEX idx_pms_image_uploads_yacht_sha256
  ON pms_image_uploads(yacht_id, sha256_hash)
  WHERE sha256_hash IS NOT NULL;
```

### Status

**ENFORCED**: Unique constraint + application logic

**Risk**: LOW (database constraint prevents violations)

### How to Verify

**Test**:
1. Upload file A to Yacht 1
2. Get response with image_id X
3. Upload same file A to Yacht 1 again
4. Verify response returns existing image_id X (not new)
5. Verify only one record in database
6. Upload same file A to Yacht 2
7. Verify NEW record created (different yacht)

---

## Invariant 6: Rate Limits Prevent Abuse

### The Rule

**Uploads MUST be rate-limited to prevent abuse.**

Current limit: 50 uploads per hour per yacht. Enforced before storage, not after.

### Current Implementation

```python
# Before processing
await rate_limiter.check_rate_limit(yacht_id)

# If exceeded, raises RateLimitExceeded
# No files are processed or stored
```

### Status

**ENFORCED**: Rate limiter checks before upload

**Risk**: LOW (early rejection)

**Known Issue**: Uses database query count, not cached counter (could be slow at scale)

### How to Verify

**Test**:
1. Upload 50 files in quick succession
2. Verify all succeed
3. Upload 51st file
4. Verify 429 error: "Rate limit exceeded"
5. Wait 1 hour
6. Verify uploads work again

---

## Invariant 7: File Validation Prevents Attacks

### The Rule

**File uploads MUST be validated before processing.**

No executable files. No oversized files. No malformed files that crash OCR.

### Current Implementation

**Checks**:
```python
# File type whitelist
ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/heic",
    "application/pdf"
}

# Size limit
MAX_SIZE = 15 * 1024 * 1024  # 15 MB

# Quality checks (optional)
MIN_WIDTH = 800
MIN_HEIGHT = 600
DQS_THRESHOLD = 70.0  # Document quality score
```

### Status

**ENFORCED**: Validator rejects invalid files before storage

**Risk**: LOW (validation before any processing)

**Attack Vectors Prevented**:
- Executable upload (`.exe`, `.sh`, etc.)
- Zip bombs (size limit)
- Image exploits (Pillow validates on open)

### How to Verify

**Test**:
```bash
# Try uploading .exe file
curl -F "files=@malware.exe" https://api/upload
# Expected: 400 error "Invalid file type"

# Try uploading 20MB file
curl -F "files=@huge_image.jpg" https://api/upload
# Expected: 400 error "File too large"
```

---

## Invariant 8: OCR Results Are Audit-Logged

### The Rule

**All OCR processing MUST be recorded for audit trail.**

Every image processed must record:
- Which engine was used
- Confidence score
- Processing time
- Raw OCR text

Cannot be deleted or modified retroactively.

### Current Implementation

```python
# Save OCR results
await self._save_ocr_results(
    image_id=image_id,
    yacht_id=yacht_id,
    ocr_result=ocr_result
)

# Updates columns:
# - ocr_raw_text
# - ocr_confidence
# - ocr_engine
# - ocr_processing_time_ms
# - ocr_completed_at
```

### Status

**ENFORCED**: Handler saves OCR results after processing

**Risk**: LOW (automatic, hard to bypass)

**Missing**: Immutability (could be updated/deleted)

**Recommendation**: Add `updated_at` tracking or audit log table

### How to Verify

**Test**:
1. Upload image
2. Wait for processing
3. Query `pms_image_uploads` table
4. Verify `ocr_raw_text` is populated
5. Verify `ocr_engine` is set
6. Verify `ocr_completed_at` timestamp exists

---

## Invariant 9: Service Role Key Is Internal Only

### The Rule

**Supabase service role key MUST NEVER be exposed to clients.**

Only backend can use service role key. Frontend uses anon key + RLS. No service key in JavaScript. No service key in API responses.

### Current Implementation

**Backend** (correct):
```python
# Backend uses service role key
supabase = create_client(
    settings.next_public_supabase_url,
    settings.supabase_service_role_key  # SECRET
)
```

**Frontend** (correct pattern, not in this repo):
```javascript
// Frontend uses anon key
const supabase = createClient(
  SUPABASE_URL,
  SUPABASE_ANON_KEY  // PUBLIC
)
```

### Status

**ENFORCED**: Service key only in backend environment variables

**Risk**: LOW (physical separation, never sent to client)

### How to Verify

**Test**:
1. Inspect API responses
2. Verify no environment variable leaks
3. Check frontend network tab
4. Verify service key never appears

---

## Invariant 10: Yacht Data Cannot Cross Boundaries

### The Rule

**No API endpoint may mix data from multiple yachts in one response.**

Each response contains data from exactly one yacht. No aggregations across yachts. No "global statistics" that leak yacht information.

### Current Implementation

**Correct**:
```python
# Single yacht response
{
  "status": "success",
  "yacht_id": "uuid-a",
  "images": [...]  # Only Yacht A's images
}
```

**Incorrect Example** (don't do this):
```python
# WRONG - cross-yacht data
{
  "total_uploads_all_yachts": 10000,  # Leaks info about other yachts
  "your_yacht": {
    "uploads": 100
  }
}
```

### Status

**ENFORCED**: All handlers filter by auth.yacht_id

**Risk**: LOW (pattern consistently applied)

### How to Verify

**Test**:
1. Query all endpoints as Yacht A
2. Verify responses contain only Yacht A data
3. Check for aggregate statistics
4. Verify no cross-yacht counts/totals

---

## Risk Assessment

### Current Risks

**HIGH RISK**:
1. No RLS policies (Invariant 1) - Manual filtering only
2. Production never tested - Unknown if invariants hold

**MEDIUM RISK**:
3. No user metadata setup tool (Invariant 3) - Manual process
4. No immutable audit log (Invariant 8) - Can be modified

**LOW RISK**:
5. All other invariants have code-level enforcement

---

## Enforcement Checklist

Before deploying any change, verify:

- [ ] All queries filter by `yacht_id`
- [ ] All endpoints require authentication (except `/health`)
- [ ] No hardcoded secrets in code
- [ ] File validation runs before storage
- [ ] SHA256 deduplication is enabled
- [ ] Rate limiting is active
- [ ] OCR results are logged
- [ ] Service role key stays in backend

---

## What Would Break These Invariants

**Human Errors**:
- Forgot to filter query by yacht_id
- Logged secret to error tracking
- Hardcoded API key "just for testing"
- Disabled validation "temporarily"
- Removed rate limiter to "debug"

**System Failures**:
- Database constraint dropped
- RLS accidentally disabled (if added)
- Environment variable not set
- Middleware bypassed

**Malicious Actions**:
- Service role key leaked
- Attacker with database access
- Compromised Supabase account
- Cross-yacht query injected

---

## Testing Security

### Manual Security Audit

1. **Yacht Isolation**:
   - Query as Yacht A, verify only see Yacht A data
   - Query as Yacht B, verify only see Yacht B data
   - Verify no cross-contamination

2. **Authentication**:
   - Call API without JWT, verify 401
   - Call API with fake JWT, verify 401
   - Call API with expired JWT, verify 401

3. **File Validation**:
   - Upload `.exe` file, verify rejected
   - Upload 20MB file, verify rejected
   - Upload tiny (10x10) image, verify rejected

4. **Rate Limiting**:
   - Upload 51 files quickly, verify 429 on 51st

5. **Secrets**:
   - Search codebase for hardcoded keys
   - Check logs for leaked credentials
   - Verify environment variable isolation

### Automated Security Tests

**None exist currently.**

**Recommended**:
```python
# tests/test_security.py
def test_yacht_isolation():
    # Query as yacht_a
    # Verify only yacht_a data returned

def test_authentication_required():
    # Call without JWT
    # Verify 401 error

def test_no_secret_leaks():
    # Check response headers/body
    # Verify no env vars leaked
```

---

## Incident Response

### If Yacht Data Is Exposed

**Immediate**:
1. Disable service (Render dashboard → pause)
2. Investigate database query logs
3. Identify scope: which yachts, what data, when
4. Notify affected yachts

**Fix**:
5. Identify code that leaked data
6. Add yacht_id filter
7. Add RLS policy as defense
8. Add test to prevent regression

**Prevent**:
9. Enable RLS on all tables
10. Add pre-commit hook to check for yacht_id filters
11. Add monitoring for cross-yacht queries

### If Service Role Key Is Leaked

**Immediate**:
1. Rotate key in Supabase dashboard
2. Update Render environment variable
3. Redeploy service

**Investigate**:
4. Where was key leaked? (logs, error messages, git history)
5. Who had access?
6. What damage was done?

**Prevent**:
7. Scan code for hardcoded secrets
8. Add secret scanning to CI/CD
9. Rotate keys regularly (every 90 days)

---

## Final Words

**These invariants are not negotiable.**

They are not "best practices" or "nice to haves." They are the minimum requirements for multi-tenant data security.

Break them at your own risk.

---

**End of Security Invariants**
