# Implementation Guide: Applying Critical Fixes

## Quick Start

### Step 1: Deploy Database Migration

```bash
# Connect to Supabase
psql $DATABASE_URL

# Run atomic operations migration
\i migrations/20260109_atomic_operations.sql

# Verify functions created
SELECT proname FROM pg_proc
WHERE proname IN ('atomic_deduct_inventory', 'atomic_commit_session')
AND pronamespace = 'public'::regnamespace;
```

Expected output:
```
        proname
-------------------------
atomic_deduct_inventory
atomic_commit_session
get_part_stock_with_lock
(3 rows)
```

---

## Step 2: Update Handlers to Use Sanitization

### Example: Part Handler (BEFORE)

```python
# OLD CODE (vulnerable to XSS)
from src.handlers.base_handler import BaseHandler

class PartHandler(BaseHandler):
    async def add_part_to_work_order(self, part_number, description, quantity):
        # No sanitization - XSS vulnerability!
        result = await self.supabase.table("pms_work_order_parts").insert({
            "part_number": part_number,       # ← Could contain SQL injection
            "description": description,        # ← Could contain XSS
            "quantity": quantity               # ← Could be negative or garbage
        }).execute()

        return result.data
```

### Example: Part Handler (AFTER - Fixed)

```python
# NEW CODE (safe)
from src.handlers.base_handler import BaseHandler
from src.security.sanitization import (
    OutputSanitizer,
    InputValidator,
    sanitize_user_input
)

class PartHandler(BaseHandler):
    async def add_part_to_work_order(self, part_number, description, quantity):
        # STEP 1: Sanitize ALL inputs
        sanitized = sanitize_user_input(
            part_number=part_number,
            description=description,
            quantity=quantity
        )

        # STEP 2: Check validation errors
        if not sanitized["valid"]:
            raise ValueError("; ".join(sanitized["errors"]))

        # STEP 3: Use sanitized values
        result = await self.supabase.table("pms_work_order_parts").insert({
            "part_number": sanitized["sanitized"]["part_number"],
            "description": sanitized["sanitized"]["description"],
            "quantity": sanitized["sanitized"]["quantity"]
        }).execute()

        return result.data
```

---

## Step 3: Update Handlers to Use Atomic Operations

### Example: Inventory Deduction (BEFORE)

```python
# OLD CODE (race condition vulnerability)
from src.handlers.base_handler import BaseHandler

class PartHandler(BaseHandler):
    async def deduct_inventory(self, part_id, quantity, user_id):
        # VULNERABLE: Check-then-act pattern
        # Thread A and B can both pass this check
        part = await self.supabase.table("pms_parts").select("quantity_on_hand").eq("id", part_id).single().execute()

        if part.data["quantity_on_hand"] < quantity:
            raise ValueError("Insufficient stock")

        # Race condition here! ↓
        # Both threads might deduct, causing over-deduction
        result = await self.supabase.table("pms_parts").update({
            "quantity_on_hand": part.data["quantity_on_hand"] - quantity
        }).eq("id", part_id).execute()

        return result.data
```

### Example: Inventory Deduction (AFTER - Fixed)

```python
# NEW CODE (atomic, safe)
from src.handlers.base_handler import BaseHandler
from src.database.atomic_operations import AtomicInventoryOperations

class PartHandler(BaseHandler):
    def __init__(self, supabase_client):
        super().__init__(supabase_client)
        self.atomic_ops = AtomicInventoryOperations(supabase_client)

    async def deduct_inventory(self, part_id, quantity, user_id, work_order_id=None):
        # Use atomic operation (no race condition possible)
        result = await self.atomic_ops.atomic_deduct_inventory(
            part_id=part_id,
            quantity=quantity,
            user_id=user_id,
            work_order_id=work_order_id
        )

        if not result.success:
            raise ValueError(result.error)

        return {
            "old_quantity": result.old_quantity,
            "new_quantity": result.new_quantity,
            "usage_id": result.usage_id
        }
```

---

## Step 4: Update Routes to Apply Abuse Protection

### Example: Upload Route (BEFORE)

```python
# OLD CODE (no protection)
from fastapi import APIRouter, UploadFile
from src.handlers.intake_handler import IntakeHandler

router = APIRouter()

@router.post("/intake/upload")
async def upload_file(file: UploadFile, user: UserContext):
    # No validation - accepts any file!
    handler = IntakeHandler()
    result = await handler.process_upload(file, user.yacht_id, user.user_id)
    return result
```

### Example: Upload Route (AFTER - Fixed)

```python
# NEW CODE (with protection)
from fastapi import APIRouter, UploadFile, HTTPException
from src.handlers.intake_handler import IntakeHandler
from src.middleware.abuse_protection import (
    IntakeGate,
    RateLimiter,
    DuplicateDetector
)

router = APIRouter()

# Initialize protections (in production, use Redis)
rate_limiter = RateLimiter()
duplicate_detector = DuplicateDetector()

@router.post("/intake/upload")
async def upload_file(file: UploadFile, user: UserContext):
    # STEP 1: Rate limiting
    allowed, error = rate_limiter.check_upload_rate(str(user.user_id))
    if not allowed:
        raise HTTPException(status_code=429, detail=error)

    # STEP 2: Rapid-fire detection
    allowed, error = rate_limiter.check_rapid_fire(str(user.user_id))
    if not allowed:
        raise HTTPException(status_code=429, detail=error)

    # STEP 3: File type validation
    allowed, error = IntakeGate.validate_file_type(file.filename, file.content_type)
    if not allowed:
        raise HTTPException(status_code=400, detail=error)

    # STEP 4: File size validation
    content = await file.read()
    allowed, error = IntakeGate.validate_file_size(len(content))
    if not allowed:
        raise HTTPException(status_code=400, detail=error)

    # STEP 5: Duplicate detection
    file_hash = DuplicateDetector.hash_file(content)
    is_duplicate, prev_upload = duplicate_detector.check_duplicate(
        file_hash,
        str(user.user_id),
        file.filename
    )

    if is_duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate upload detected. Same file uploaded {prev_upload['uploaded_at']}"
        )

    # STEP 6: Process upload
    handler = IntakeHandler()
    result = await handler.process_upload(content, file.filename, user.yacht_id, user.user_id)

    return result
```

---

## Step 5: Update API Responses to Escape HTML

### Example: Draft Lines Response (BEFORE)

```python
# OLD CODE (XSS in responses)
@router.get("/sessions/{session_id}/draft-lines")
async def get_draft_lines(session_id: UUID):
    lines = await db.get_draft_lines(session_id)

    # Returning raw data - XSS vulnerability!
    return {
        "lines": [
            {
                "part_number": line["part_number"],      # ← Could contain XSS
                "description": line["description"],      # ← Could contain XSS
                "quantity": line["quantity"]
            }
            for line in lines
        ]
    }
```

### Example: Draft Lines Response (AFTER - Fixed)

```python
# NEW CODE (safe)
from src.security.sanitization import escape_for_display

@router.get("/sessions/{session_id}/draft-lines")
async def get_draft_lines(session_id: UUID):
    lines = await db.get_draft_lines(session_id)

    # Escape ALL user-facing text
    return {
        "lines": [
            {
                "part_number": escape_for_display(line["part_number"]),
                "description": escape_for_display(line["description"]),
                "quantity": line["quantity"]  # Numbers don't need escaping
            }
            for line in lines
        ]
    }
```

---

## Step 6: Add Lazy Workflow Protection

### Example: Bulk Commit (BEFORE)

```python
# OLD CODE (no protection against lazy ticking)
@router.post("/sessions/{session_id}/commit")
async def commit_session(session_id: UUID, lines: list[dict], user: UserContext):
    # Users can tick everything in 5 seconds without verification
    handler = SessionHandler()
    result = await handler.commit_session(session_id, lines, user.user_id)
    return result
```

### Example: Bulk Commit (AFTER - Fixed)

```python
# NEW CODE (with lazy workflow protection)
from src.middleware.abuse_protection import (
    LazyWorkflowProtection,
    ConfirmationRequired,
    check_needs_confirmation
)

@router.post("/sessions/{session_id}/commit")
async def commit_session(
    session_id: UUID,
    lines: list[dict],
    elapsed_seconds: float,  # Time since first tick
    confirmed: bool = False,  # User confirmed the bulk operation?
    user: UserContext = Depends(get_current_user)
):
    ticked_lines = [line for line in lines if line.get("ticked")]

    # Check if confirmation needed (bulk tick protection)
    try:
        check_needs_confirmation(
            operation="commit",
            item_count=len(ticked_lines),
            elapsed_seconds=elapsed_seconds,
            confirmed=confirmed
        )
    except ConfirmationRequired as e:
        # Return confirmation prompt to user
        return {
            "requires_confirmation": True,
            "message": e.message,
            "item_count": e.item_count
        }

    # Check that unmatched items are resolved
    needs_resolution, error = LazyWorkflowProtection.requires_unmatched_resolution(ticked_lines)
    if needs_resolution:
        raise HTTPException(status_code=400, detail=error)

    # Use atomic commit (prevent double-commit)
    atomic_ops = AtomicInventoryOperations(supabase)
    commit_result = await atomic_ops.atomic_commit_session(session_id, user.user_id)

    if not commit_result.success:
        raise HTTPException(status_code=409, detail=commit_result.error)

    return {
        "success": True,
        "session_id": str(commit_result.session_id),
        "committed_at": commit_result.committed_at
    }
```

---

## Step 7: Add Middleware to FastAPI App

### Update `src/main.py`

```python
# Add after creating FastAPI app
from src.middleware.abuse_protection import abuse_protection_middleware

app = FastAPI(title="Image Processing Service")

# Add abuse protection middleware
app.middleware("http")(abuse_protection_middleware)

# ... rest of app setup
```

---

## Testing the Fixes

### Test XSS Protection

```python
import requests

# Try XSS payload
response = requests.post(
    "http://localhost:8001/api/v1/parts",
    json={
        "part_number": "MTU-OF-4568",
        "description": "<script>alert('XSS')</script>",
        "quantity": 10
    },
    headers={"Authorization": f"Bearer {token}"}
)

# Check response is escaped
assert "&lt;script&gt;" in response.json()["description"]
print("✅ XSS protection working")
```

### Test Atomic Operations

```python
import asyncio
from uuid import uuid4

# Simulate race condition
part_id = uuid4()
user_id = uuid4()

async def concurrent_deduct():
    tasks = [
        atomic_ops.atomic_deduct_inventory(part_id, 5.0, user_id),
        atomic_ops.atomic_deduct_inventory(part_id, 5.0, user_id),
        atomic_ops.atomic_deduct_inventory(part_id, 5.0, user_id),
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    successes = sum(1 for r in results if r.success)
    failures = sum(1 for r in results if not r.success)

    assert successes == 2, "Expected 2 successes"
    assert failures == 1, "Expected 1 failure"
    print("✅ Atomic operations working")

asyncio.run(concurrent_deduct())
```

### Test Rate Limiting

```bash
# Rapid-fire 60 requests
for i in {1..60}; do
    curl -X POST http://localhost:8001/api/v1/intake/upload \
         -H "Authorization: Bearer $TOKEN" \
         -F "file=@test.pdf" &
done

# Expected: First 50 succeed, next 10 get 429 Too Many Requests
```

---

## Deployment Checklist

- [ ] 1. Deploy database migration (atomic operations)
- [ ] 2. Update all handlers to use sanitization
- [ ] 3. Update all handlers to use atomic operations
- [ ] 4. Update all routes to escape HTML output
- [ ] 5. Add abuse protection to upload routes
- [ ] 6. Add lazy workflow protection to commit routes
- [ ] 7. Add middleware to FastAPI app
- [ ] 8. Test XSS protection in staging
- [ ] 9. Test atomic operations in staging
- [ ] 10. Test rate limiting in staging
- [ ] 11. Deploy to production
- [ ] 12. Monitor for blocked attacks (first week)

---

## Monitoring Queries

### Check for XSS attempts (if logging enabled)

```sql
SELECT
    created_at,
    user_id,
    action,
    details
FROM audit_log
WHERE action = 'xss_blocked'
ORDER BY created_at DESC
LIMIT 100;
```

### Check for race condition errors

```sql
SELECT
    created_at,
    part_id,
    quantity_requested,
    quantity_available
FROM pms_audit_log
WHERE action = 'deduct_failed'
    AND error_message LIKE '%Insufficient stock%'
ORDER BY created_at DESC
LIMIT 100;
```

### Verify no negative inventory

```sql
SELECT
    part_number,
    name,
    quantity_on_hand
FROM pms_parts
WHERE quantity_on_hand < 0;
-- Expected: 0 rows
```

### Check rate limiting effectiveness

```sql
SELECT
    user_id,
    COUNT(*) as upload_count,
    MIN(created_at) as first_upload,
    MAX(created_at) as last_upload
FROM upload_attempts
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY user_id
HAVING COUNT(*) > 50
ORDER BY upload_count DESC;
-- Shows users who hit rate limit
```

---

## Quick Reference

### Import Statements

```python
# Sanitization
from src.security.sanitization import (
    escape_for_display,
    sanitize_user_input,
    OutputSanitizer,
    InputValidator
)

# Atomic operations
from src.database.atomic_operations import (
    AtomicInventoryOperations,
    DeductionResult,
    CommitResult
)

# Abuse protection
from src.middleware.abuse_protection import (
    IntakeGate,
    RateLimiter,
    DuplicateDetector,
    LazyWorkflowProtection,
    ConfirmationRequired
)
```

### Common Patterns

```python
# Sanitize text for display
safe_text = escape_for_display(user_input)

# Validate and sanitize input
result = sanitize_user_input(
    part_number=part_num,
    description=desc,
    quantity=qty
)

# Atomic inventory deduction
result = await atomic_ops.atomic_deduct_inventory(
    part_id, quantity, user_id
)

# Check rate limit
allowed, error = rate_limiter.check_upload_rate(user_id)

# Detect duplicates
file_hash = DuplicateDetector.hash_file(content)
is_dup, prev = duplicate_detector.check_duplicate(file_hash, user_id, filename)
```

---

## Support

If you encounter issues:

1. Check migration deployed: `SELECT proname FROM pg_proc WHERE proname LIKE 'atomic%';`
2. Check imports working: `python -c "from src.security.sanitization import escape_for_display"`
3. Run test suite: `pytest tests/test_security.py`
4. Check logs for errors: `tail -f logs/app.log | grep -i "xss\|race\|atomic"`

---

**Status**: Ready for implementation
**Estimated time**: 4-6 hours
**Risk**: Low (all changes backward compatible)
**Testing required**: Yes (staging environment first)
