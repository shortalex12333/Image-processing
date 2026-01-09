# Abuse Protection & Rate Limiting
## Image Processing Service - Security Layer

**Document Version**: 1.0
**Last Updated**: 2026-01-09
**Status**: Production Ready

---

## Table of Contents

1. [Overview](#overview)
2. [Rate Limiting](#rate-limiting)
3. [Cost Controls](#cost-controls)
4. [Upload Validation](#upload-validation)
5. [Deduplication](#deduplication)
6. [Anomaly Detection](#anomaly-detection)
7. [Response to Abuse](#response-to-abuse)
8. [Monitoring & Alerts](#monitoring--alerts)

---

## Overview

The Image Processing Service implements multiple layers of abuse protection to prevent:
- Resource exhaustion attacks
- Cost explosion from excessive LLM usage
- Storage flooding
- API abuse
- Data exfiltration attempts

### Defense in Depth Strategy

```
┌─────────────────────────────────────────┐
│  Layer 1: Authentication (JWT)          │
│  ↓ Verify user identity                 │
├─────────────────────────────────────────┤
│  Layer 2: Rate Limiting (50/hour)       │
│  ↓ Prevent request flooding              │
├─────────────────────────────────────────┤
│  Layer 3: File Validation (MIME, size)  │
│  ↓ Reject malicious uploads              │
├─────────────────────────────────────────┤
│  Layer 4: Deduplication (SHA256)        │
│  ↓ Prevent storage duplication           │
├─────────────────────────────────────────┤
│  Layer 5: Cost Controls ($0.50/session) │
│  ↓ Prevent LLM cost explosion            │
├─────────────────────────────────────────┤
│  Layer 6: Anomaly Detection              │
│  ↓ Identify suspicious patterns          │
└─────────────────────────────────────────┘
```

---

## Rate Limiting

### Upload Rate Limits

**Implementation**: `src/intake/rate_limiter.py`

#### Limits by Entity

| Entity | Limit | Window | Enforcement |
|--------|-------|--------|-------------|
| User | 50 uploads | 1 hour | Hard limit |
| Yacht | 200 uploads | 1 hour | Hard limit |
| IP Address | 100 uploads | 1 hour | Soft limit (logged) |

#### Configuration

```python
# src/config.py
RATE_LIMIT_UPLOADS_PER_HOUR = 50
RATE_LIMIT_WINDOW_SECONDS = 3600
```

#### Response Behavior

When rate limit exceeded:

```python
HTTP 429 Too Many Requests
{
  "error": "rate_limit_exceeded",
  "message": "Upload rate limit exceeded",
  "details": {
    "limit": 50,
    "window_hours": 1,
    "current_count": 51,
    "retry_after_seconds": 1847
  }
}
```

Client should:
1. Stop making requests
2. Wait for `retry_after_seconds`
3. Implement exponential backoff

#### Bypass for Admins

HOD users have higher limits:

```python
# HOD limits
RATE_LIMIT_HOD_MULTIPLIER = 2  # 100 uploads/hour
```

### API Endpoint Rate Limits

| Endpoint | Limit | Window |
|----------|-------|--------|
| POST /api/v1/images/upload | 50 | 1 hour |
| POST /api/v1/shipping-labels/process | 100 | 1 hour |
| POST /api/v1/photos/attach/* | 200 | 1 hour |
| POST /api/v1/labels/*/pdf | 50 | 1 hour |
| GET /api/v1/* | 1000 | 1 hour |

### Rate Limit Headers

Every response includes rate limit information:

```http
X-RateLimit-Limit: 50
X-RateLimit-Remaining: 37
X-RateLimit-Reset: 1704830400
```

### Implementation

```python
class RateLimiter:
    """Rate limiting with Redis-backed counters."""

    async def check_rate_limit(
        self,
        yacht_id: UUID,
        user_id: UUID
    ) -> tuple[bool, int, int | None]:
        """
        Check if rate limit exceeded.

        Returns:
            (is_limited, current_count, retry_after_seconds)
        """
        # Query recent uploads
        count = await self._get_upload_count(yacht_id, user_id)

        if count >= self.limit:
            retry_after = self._calculate_retry_after(yacht_id, user_id)
            return (True, count, retry_after)

        return (False, count, None)
```

---

## Cost Controls

### LLM Cost Limits

**Implementation**: `src/extraction/cost_controller.py`

#### Per-Session Limits

| Metric | Limit | Enforcement |
|--------|-------|-------------|
| Total cost | $0.50 | Hard cap |
| LLM calls | 3 | Hard cap |
| Total tokens | 10,000 | Hard cap |

#### Cost Tracking

Every LLM call is tracked:

```python
class SessionCostTracker:
    """Tracks LLM costs per session."""

    def record_llm_call(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float
    ):
        """Record LLM call metrics."""
        self.total_cost += cost
        self.total_tokens += input_tokens + output_tokens
        self.llm_calls += 1

        # Alert at 80% of budget
        if self.total_cost > 0.40:
            logger.warning("Session approaching cost limit", extra={
                "session_id": str(self.session_id),
                "cost": self.total_cost,
                "limit": 0.50
            })

        # Hard stop at 100%
        if self.total_cost >= 0.50:
            raise CostLimitExceededError("Session cost limit exceeded")
```

#### Decision Tree for Cost Control

```
Is coverage >= 80%?
├── YES → Accept deterministic parse (cost: $0)
└── NO → Coverage < 80%
    └── LLM attempts < 1?
        ├── YES → Use gpt-4.1-mini (cost: ~$0.05)
        └── NO → LLM attempts >= 1
            └── Coverage improved?
                ├── YES → Accept partial (cost: ~$0.05)
                └── NO → Coverage still low
                    └── Budget available?
                        ├── YES → Escalate to gpt-4.1 (cost: ~$0.20)
                        └── NO → Accept partial, log warning
```

#### Monthly Cost Caps

Per-yacht monthly limits:

```python
COST_LIMIT_PER_YACHT_MONTHLY = 100.00  # $100/month
```

When approaching limit:
1. Warning at 80% ($80)
2. Throttle at 90% ($90) - slower processing
3. Block at 100% ($100) - manual approval required

### Storage Cost Controls

#### File Size Limits

```python
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15MB
```

Rejects files larger than 15MB to prevent storage flooding.

#### Storage Quotas

Per-yacht storage quotas:

| Plan | Monthly Upload Limit | Total Storage |
|------|---------------------|---------------|
| Standard | 1,000 images | 50 GB |
| Premium | 5,000 images | 250 GB |
| Enterprise | Unlimited | 1 TB |

When quota exceeded:
- Uploads blocked
- Notification sent to yacht admin
- Option to upgrade plan

### Bandwidth Controls

```python
MAX_CONCURRENT_UPLOADS_PER_USER = 3
MAX_CONCURRENT_PROCESSING_PER_YACHT = 10
```

Prevents resource exhaustion from parallel uploads.

---

## Upload Validation

### File Type Validation

**Implementation**: `src/intake/validator.py`

#### Allowed MIME Types

```python
ALLOWED_MIME_TYPES = {
    "receiving": [
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf"
    ],
    "shipping_label": [
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf"
    ],
    "discrepancy_photo": [
        "image/jpeg",
        "image/png",
        "image/webp"
    ],
    "part_photo": [
        "image/jpeg",
        "image/png",
        "image/webp"
    ]
}
```

#### Validation Steps

1. **MIME Type Detection**
   - Use `python-magic` (libmagic) to detect true file type
   - Don't trust file extension or Content-Type header

2. **File Size Check**
   - Reject files > 15MB

3. **Image Dimension Check**
   - Minimum: 800x600 pixels
   - Maximum: 10000x10000 pixels
   - Rejects tiny images (likely not documents)
   - Rejects huge images (likely DoS attempt)

4. **Blur Detection**
   - Laplacian variance method
   - Reject if variance < 100 (too blurry to OCR)

5. **Malware Scan** (Optional)
   - ClamAV integration
   - Scan uploaded files for known malware signatures

### Rejected File Response

```python
HTTP 400 Bad Request
{
  "error": "validation_failed",
  "message": "File validation failed",
  "details": {
    "file_name": "test.exe",
    "rejection_reason": "invalid_mime_type",
    "expected": ["image/jpeg", "image/png", "application/pdf"],
    "detected": "application/x-executable"
  }
}
```

---

## Deduplication

### SHA256 Hash-Based Deduplication

**Implementation**: `src/intake/deduplicator.py`

#### Purpose

Prevent:
- Storage waste from duplicate uploads
- Redundant processing costs
- Accidental re-uploads

#### How It Works

1. **Calculate Hash**
   ```python
   def calculate_hash(self, file_bytes: bytes) -> str:
       """Calculate SHA256 hash of file."""
       return hashlib.sha256(file_bytes).hexdigest()
   ```

2. **Check for Duplicates**
   ```sql
   SELECT image_id, file_name, storage_path
   FROM pms_image_uploads
   WHERE yacht_id = $1 AND sha256_hash = $2
   LIMIT 1
   ```

3. **Response if Duplicate**
   ```python
   HTTP 200 OK
   {
     "status": "success",
     "images": [{
       "image_id": "existing-uuid",
       "file_name": "existing.pdf",
       "is_duplicate": true,
       "original_upload_date": "2026-01-08T10:30:00Z",
       "storage_path": "path/to/existing.pdf"
     }]
   }
   ```

Client receives reference to existing file instead of uploading again.

#### Benefits

- Saves storage costs
- Saves processing time
- Provides instant results for duplicates
- Maintains data integrity

---

## Anomaly Detection

### Suspicious Pattern Detection

#### Patterns to Detect

1. **Rapid Sequential Uploads**
   - >10 uploads in 60 seconds
   - Likely automated script

2. **Identical File Spam**
   - Same SHA256 hash uploaded repeatedly
   - Possible DoS attempt

3. **Size Anomalies**
   - Sudden spike in file sizes
   - All files exactly same size (suspicious)

4. **Off-Hours Activity**
   - Uploads at 3 AM local time
   - May indicate compromised account

5. **Unusual Success Rate**
   - 100% OCR failures (malformed files?)
   - 0% part matches (wrong data?)

### Implementation

```python
class AnomalyDetector:
    """Detects suspicious upload patterns."""

    async def check_anomalies(
        self,
        yacht_id: UUID,
        user_id: UUID,
        upload_metadata: dict
    ) -> dict:
        """
        Check for suspicious patterns.

        Returns:
            {
                "is_suspicious": bool,
                "anomalies": list[str],
                "risk_score": float (0.0-1.0)
            }
        """
        anomalies = []

        # Check upload velocity
        if await self._is_rapid_upload(user_id):
            anomalies.append("rapid_upload")

        # Check file patterns
        if await self._is_duplicate_spam(yacht_id, upload_metadata):
            anomalies.append("duplicate_spam")

        # Check off-hours activity
        if self._is_off_hours(yacht_id):
            anomalies.append("off_hours_activity")

        risk_score = len(anomalies) * 0.3

        return {
            "is_suspicious": risk_score > 0.5,
            "anomalies": anomalies,
            "risk_score": min(risk_score, 1.0)
        }
```

### Automated Responses

| Risk Score | Action | Notification |
|------------|--------|--------------|
| 0.0-0.3 | None | - |
| 0.3-0.5 | Log warning | - |
| 0.5-0.7 | Throttle requests | Email to user |
| 0.7-0.9 | Require CAPTCHA | Email to admin |
| 0.9-1.0 | Temporary block | Email to admin + user |

---

## Response to Abuse

### Incident Response Workflow

```
┌─────────────────────────┐
│  1. Detect Abuse        │
│  - Anomaly score > 0.7  │
│  - Manual report        │
└────────────┬────────────┘
             ↓
┌─────────────────────────┐
│  2. Investigate         │
│  - Review logs          │
│  - Check user history   │
│  - Assess impact        │
└────────────┬────────────┘
             ↓
┌─────────────────────────┐
│  3. Take Action         │
│  - Throttle             │
│  - Temporary block      │
│  - Permanent ban        │
└────────────┬────────────┘
             ↓
┌─────────────────────────┐
│  4. Notify              │
│  - User email           │
│  - Admin alert          │
│  - Compliance log       │
└─────────────────────────┘
```

### Throttling

Slow down requests without blocking:

```python
# Reduce rate limit to 10/hour
reduced_limit = original_limit * 0.2

# Add processing delay
await asyncio.sleep(5)  # 5-second delay per request
```

### Temporary Block

Block user for 24 hours:

```python
{
  "blocked_until": "2026-01-10T10:30:00Z",
  "reason": "suspicious_activity",
  "appeal_url": "https://support.cloud-pms.com/appeal"
}
```

User receives email:
```
Subject: Account Temporarily Suspended

Your account has been temporarily suspended due to unusual activity.

Reason: High volume of failed uploads

Duration: 24 hours

If you believe this is an error, please contact support at:
https://support.cloud-pms.com/appeal

Your suspension will be automatically lifted at:
2026-01-10 10:30 UTC
```

### Permanent Ban

Requires manual review:

```sql
UPDATE user_profiles
SET is_active = false,
    ban_reason = 'Terms of Service violation: Automated abuse',
    banned_at = NOW(),
    banned_by = 'system'
WHERE user_id = $1;
```

---

## Monitoring & Alerts

### Metrics to Monitor

#### System Health

- Request rate (req/sec)
- Error rate (%)
- Response time (p50, p95, p99)
- CPU and memory usage

#### Abuse Indicators

- Rate limit violations/hour
- Rejected uploads (by reason)
- Duplicate upload rate
- Anomaly score distribution
- Cost per yacht ($/day)

### Alert Thresholds

| Metric | Warning | Critical |
|--------|---------|----------|
| Rate limit violations | 10/hour | 50/hour |
| Cost per session | $0.40 | $0.50 |
| Error rate | 5% | 10% |
| Rejected uploads | 20% | 50% |
| Anomaly score | 0.7 | 0.9 |

### Logging

All abuse-related events logged to Supabase `pms_audit_log`:

```sql
INSERT INTO pms_audit_log (
  yacht_id,
  action,
  entity_type,
  user_id,
  details,
  created_at
) VALUES (
  '...',
  'rate_limit_exceeded',
  'upload',
  '...',
  '{"count": 51, "limit": 50, "window": 3600}',
  NOW()
);
```

### Dashboard Alerts

Real-time alerts sent to:
- Slack channel (#abuse-alerts)
- Email (admin@cloud-pms.com)
- PagerDuty (for critical alerts)

---

## Best Practices for Clients

### 1. Implement Retry Logic

```typescript
async function uploadWithRetry(file: File, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await upload(file);
    } catch (error) {
      if (error.status === 429) {
        // Rate limited - wait and retry
        const retryAfter = error.headers['retry-after'] || 60;
        await sleep(retryAfter * 1000);
        continue;
      }
      throw error;
    }
  }
}
```

### 2. Check for Duplicates

```typescript
// Calculate SHA256 before uploading
const hash = await calculateSHA256(file);

// Check if already uploaded
const existing = await checkDuplicate(hash);
if (existing) {
  console.log('File already uploaded:', existing.image_id);
  return existing;
}

// Upload new file
return await upload(file);
```

### 3. Batch Uploads

Instead of uploading 100 files individually, batch them:

```typescript
// Good - Batch upload
const files = [file1, file2, ..., file10];
await uploadBatch(files);

// Bad - Individual uploads
for (const file of files) {
  await upload(file);  // Hits rate limit
}
```

### 4. Monitor Usage

Track your own usage to avoid surprises:

```typescript
const usage = await getUsageStats();
console.log('Uploads this hour:', usage.upload_count);
console.log('Cost this month:', usage.monthly_cost);

if (usage.upload_count > 40) {
  console.warn('Approaching rate limit (50/hour)');
}
```

---

## Configuration Reference

### Environment Variables

```bash
# Rate Limiting
RATE_LIMIT_UPLOADS_PER_HOUR=50
RATE_LIMIT_WINDOW_SECONDS=3600
RATE_LIMIT_HOD_MULTIPLIER=2

# Cost Controls
COST_LIMIT_PER_SESSION=0.50
COST_LIMIT_PER_YACHT_MONTHLY=100.00
LLM_MAX_CALLS_PER_SESSION=3

# File Validation
MAX_FILE_SIZE_BYTES=15728640  # 15MB
MIN_IMAGE_WIDTH=800
MIN_IMAGE_HEIGHT=600
MIN_BLUR_VARIANCE=100

# Storage Quotas
STORAGE_QUOTA_STANDARD_GB=50
STORAGE_QUOTA_PREMIUM_GB=250
STORAGE_QUOTA_ENTERPRISE_GB=1000

# Anomaly Detection
ANOMALY_RAPID_UPLOAD_THRESHOLD=10  # uploads in 60s
ANOMALY_RISK_SCORE_WARNING=0.5
ANOMALY_RISK_SCORE_CRITICAL=0.7
```

---

## Summary

The Image Processing Service implements comprehensive abuse protection through:

1. **Authentication** - JWT-based identity verification
2. **Rate Limiting** - 50 uploads/hour per user
3. **Cost Controls** - $0.50 cap per session, $100/month per yacht
4. **File Validation** - MIME, size, dimension, blur checks
5. **Deduplication** - SHA256-based duplicate prevention
6. **Anomaly Detection** - Pattern recognition for suspicious activity
7. **Monitoring** - Real-time alerts and comprehensive logging

This multi-layered approach ensures system stability, prevents cost explosion, and maintains service quality for all users.

---

**Next Steps:**
- Review `docs/07_security.md` for authentication and authorization details
- Check `/health` endpoint for real-time system status
- Monitor Supabase dashboard for usage metrics
