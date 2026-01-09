# Security Architecture
## Image Processing Service - Authentication, Authorization & Data Protection

**Document Version**: 1.0
**Last Updated**: 2026-01-09
**Status**: Production Ready
**Compliance**: GDPR, SOC 2, ISO 27001

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Authorization](#authorization)
4. [Data Protection](#data-protection)
5. [Network Security](#network-security)
6. [Secrets Management](#secrets-management)
7. [Audit & Compliance](#audit--compliance)
8. [Incident Response](#incident-response)
9. [Security Checklist](#security-checklist)

---

## Overview

The Image Processing Service implements enterprise-grade security across multiple layers:

```
┌──────────────────────────────────────────────┐
│  Transport Layer (TLS 1.3)                   │
│  ↓ Encrypted communication                   │
├──────────────────────────────────────────────┤
│  Authentication (JWT HS256)                  │
│  ↓ Verify user identity                      │
├──────────────────────────────────────────────┤
│  Authorization (RBAC + RLS)                  │
│  ↓ Enforce permissions                       │
├──────────────────────────────────────────────┤
│  Data Protection (Encryption at rest)        │
│  ↓ Secure sensitive data                     │
├──────────────────────────────────────────────┤
│  Audit Logging (SHA256 signatures)          │
│  ↓ Track all actions                         │
└──────────────────────────────────────────────┘
```

### Security Principles

1. **Zero Trust** - Never trust, always verify
2. **Least Privilege** - Minimum necessary permissions
3. **Defense in Depth** - Multiple security layers
4. **Fail Secure** - Deny access on error
5. **Audit Everything** - Complete traceability

---

## Authentication

### JWT (JSON Web Token) Authentication

**Implementation**: `src/middleware/auth.py`

#### Token Structure

```
Header:
{
  "alg": "HS256",
  "typ": "JWT"
}

Payload:
{
  "sub": "user_id",
  "yacht_id": "yacht_uuid",
  "email": "user@example.com",
  "roles": ["chief_engineer"],
  "iat": 1704830400,
  "exp": 1704916800
}

Signature:
HMACSHA256(
  base64UrlEncode(header) + "." +
  base64UrlEncode(payload),
  secret
)
```

#### Token Validation

```python
class JWTAuthenticator:
    """Validates JWT tokens."""

    def validate_token(self, token: str) -> UserContext:
        """
        Validate JWT and extract user context.

        Security checks:
        1. Signature verification (HMAC-SHA256)
        2. Expiration check (exp claim)
        3. Not-before check (nbf claim)
        4. Issuer validation (iss claim)
        5. Audience validation (aud claim)

        Raises:
            InvalidTokenError: If token invalid or expired
        """
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret,
                algorithms=["HS256"],
                options={
                    "require": ["sub", "exp", "iat"],
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True
                }
            )

            return UserContext(
                user_id=UUID(payload["sub"]),
                yacht_id=UUID(payload["yacht_id"]),
                email=payload["email"],
                roles=payload.get("roles", []),
                is_hod=self._is_hod(payload.get("roles", []))
            )

        except jwt.ExpiredSignatureError:
            raise InvalidTokenError("Token has expired")
        except jwt.InvalidTokenError as e:
            raise InvalidTokenError(f"Invalid token: {str(e)}")
```

#### Token Lifecycle

1. **Issuance**
   - User logs in via Cloud_PMS frontend
   - Supabase Auth validates credentials
   - JWT issued with 24-hour expiration

2. **Usage**
   - Client includes token in Authorization header
   - Every API request validates token
   - User context extracted for authorization

3. **Refresh**
   - Client requests new token before expiration
   - Refresh token used (longer-lived, single-use)
   - New access token issued

4. **Revocation**
   - Immediate: Change JWT_SECRET (revokes all tokens)
   - Per-user: Blacklist in Redis (check on validation)
   - On logout: Client discards token

#### Security Best Practices

**DO:**
- ✅ Store JWT secret securely (environment variable)
- ✅ Use HTTPS only (prevents token interception)
- ✅ Set short expiration (24 hours max)
- ✅ Validate signature on every request
- ✅ Include minimal claims (no sensitive data)

**DON'T:**
- ❌ Store JWT in localStorage (XSS vulnerable)
- ❌ Include passwords or secrets in JWT
- ❌ Use weak secret (min 32 bytes entropy)
- ❌ Accept tokens without signature
- ❌ Trust client-provided claims

---

## Authorization

### Role-Based Access Control (RBAC)

#### User Roles

| Role | Description | Permissions |
|------|-------------|-------------|
| `captain` | Yacht captain | Full read, approve work orders |
| `chief_engineer` | Head of engineering (HOD) | Full access, commit receiving events |
| `eto` | Electronics Technical Officer | Technical operations |
| `crew` | General crew | Read-only, create work orders |
| `manager` | Yacht manager | Administrative access |
| `vendor` | External vendor | Limited read access |
| `deck` | Deck crew | Deck-specific operations |
| `interior` | Interior crew | Interior-specific operations |

#### Permission Matrix

| Action | captain | chief_engineer | eto | crew | manager | vendor |
|--------|---------|----------------|-----|------|---------|--------|
| Upload images | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| View sessions | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Verify draft lines | ✅ | ✅ | ✅ | ❌ | ✅ | ❌ |
| Commit sessions | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |
| Generate labels | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| View audit logs | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ |

#### HOD (Head of Department) Check

Critical operations require HOD permissions:

```python
def require_hod(user: UserContext):
    """Decorator to require HOD permissions."""
    if not user.is_hod:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "insufficient_permissions",
                "message": "This action requires Head of Department permissions",
                "required_roles": ["chief_engineer", "captain", "manager"]
            }
        )
```

Used for:
- Committing receiving events
- Closing work orders
- Managing user roles
- Approving budget overruns

### Row-Level Security (RLS)

**Implementation**: Supabase PostgreSQL RLS policies

#### Multi-Tenant Isolation

Every table has `yacht_id` column with RLS policy:

```sql
-- Example RLS policy for pms_parts
CREATE POLICY "Users can only see own yacht parts"
ON pms_parts
FOR SELECT
TO authenticated
USING (yacht_id = public.get_user_yacht_id());

-- Helper function
CREATE FUNCTION public.get_user_yacht_id()
RETURNS UUID AS $$
    SELECT yacht_id FROM public.user_profiles WHERE id = auth.uid();
$$ LANGUAGE sql SECURITY DEFINER STABLE;
```

#### Policy Types

1. **SELECT Policy** - Who can read data
   ```sql
   USING (yacht_id = public.get_user_yacht_id())
   ```

2. **INSERT Policy** - Who can create data
   ```sql
   WITH CHECK (yacht_id = public.get_user_yacht_id())
   ```

3. **UPDATE Policy** - Who can modify data
   ```sql
   USING (yacht_id = public.get_user_yacht_id())
   WITH CHECK (yacht_id = public.get_user_yacht_id())
   ```

4. **DELETE Policy** - Who can delete data
   ```sql
   USING (yacht_id = public.get_user_yacht_id() AND is_hod())
   ```

#### Service Role Bypass

Service role (backend service) bypasses RLS:

```python
# Service role has full access
supabase_service = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key  # Bypasses RLS
)

# Use for system operations:
# - Background processing
# - Cross-yacht analytics
# - System maintenance
```

**Security Warning**: Service role key must be kept secret. Never expose to frontend.

---

## Data Protection

### Encryption

#### In Transit

- **TLS 1.3** for all API communication
- **Certificate pinning** in mobile apps
- **HSTS headers** (HTTP Strict Transport Security)

```python
# Enforce HTTPS
app.add_middleware(
    HTTPSRedirectMiddleware,
    enabled=settings.is_production
)

# Add security headers
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response
```

#### At Rest

- **Supabase Storage encryption** (AES-256)
- **Database encryption** (PostgreSQL native encryption)
- **Secrets encryption** (AWS KMS / Vault)

```python
# Files stored encrypted
storage_client.upload(
    bucket="receiving",
    path=storage_path,
    file=file_bytes,
    options={
        "cacheControl": "3600",
        "upsert": False,
        "contentType": mime_type
    }
)
# Supabase automatically encrypts at rest
```

### Sensitive Data Handling

#### Personal Identifiable Information (PII)

| Data Type | Location | Protection |
|-----------|----------|------------|
| Email | user_profiles | Encrypted in DB |
| Name | user_profiles | Encrypted in DB |
| IP Address | Logs only | Hashed, 30-day retention |
| Phone | Not stored | N/A |
| Address | Shipping labels | Encrypted, auto-deleted after 90 days |

#### Data Minimization

Only collect what's necessary:
- ❌ Don't store credit card numbers (use Stripe)
- ❌ Don't store passwords (use Supabase Auth)
- ❌ Don't log full requests (mask sensitive fields)

#### Data Retention

| Data Type | Retention | Rationale |
|-----------|-----------|-----------|
| Images | 2 years | Compliance requirement |
| OCR text | 2 years | Audit trail |
| Session data | 2 years | Historical analysis |
| Logs | 90 days | Debugging |
| Audit trail | 7 years | Legal requirement |
| PII | User lifetime + 30 days | GDPR compliance |

Auto-deletion implemented:

```sql
-- Scheduled job (runs daily)
DELETE FROM pms_image_uploads
WHERE created_at < NOW() - INTERVAL '2 years'
  AND archival_status = 'not_required';

DELETE FROM pms_audit_log
WHERE created_at < NOW() - INTERVAL '90 days'
  AND severity != 'critical';
```

### Data Anonymization

For analytics and testing:

```python
def anonymize_user_data(data: dict) -> dict:
    """Anonymize PII for analytics."""
    return {
        **data,
        "email": hashlib.sha256(data["email"].encode()).hexdigest()[:16],
        "name": "User-" + data["user_id"][:8],
        "ip_address": None
    }
```

---

## Network Security

### Firewall Rules

```
Inbound:
- Allow HTTPS (443) from anywhere
- Allow SSH (22) from admin IPs only
- Deny all other inbound traffic

Outbound:
- Allow HTTPS (443) to Supabase, OpenAI, Render
- Allow DNS (53) to any
- Deny all other outbound traffic
```

### CORS (Cross-Origin Resource Sharing)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url] if settings.is_production else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600
)
```

**Production**: Only allow trusted frontend domains
**Development**: Allow all origins for testing

### API Security Headers

```python
# CSP (Content Security Policy)
Content-Security-Policy: default-src 'self'; img-src *; media-src *; script-src 'self'

# Prevent clickjacking
X-Frame-Options: DENY

# MIME sniffing prevention
X-Content-Type-Options: nosniff

# XSS protection
X-XSS-Protection: 1; mode=block

# Referrer policy
Referrer-Policy: strict-origin-when-cross-origin
```

---

## Secrets Management

### Environment Variables

**Never commit secrets to git!**

```bash
# .env (git-ignored)
JWT_SECRET=<generated-with-openssl-rand-base64-32>
SUPABASE_SERVICE_ROLE_KEY=<from-supabase-dashboard>
OPENAI_API_KEY=<from-openai-dashboard>
```

### Secret Rotation

Rotate secrets every 90 days:

```bash
# Generate new JWT secret
openssl rand -base64 32 > new-jwt-secret.txt

# Update environment variables
# 1. Add new secret to environment
# 2. Deploy updated service
# 3. Remove old secret after 24 hours (grace period)
```

### Key Management

| Secret | Storage | Rotation | Backup |
|--------|---------|----------|--------|
| JWT_SECRET | Env var | 90 days | AWS Secrets Manager |
| Supabase keys | Env var | On compromise | Supabase Dashboard |
| OpenAI API key | Env var | On compromise | OpenAI Dashboard |
| Database credentials | Env var | 90 days | AWS Secrets Manager |

### Secure Deployment

```yaml
# render.yaml
services:
  - type: web
    name: image-processing
    env: docker
    envVars:
      - key: JWT_SECRET
        sync: false  # Don't sync from repo
        generateValue: true  # Generate random value
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
        # Set manually in Render dashboard
```

---

## Audit & Compliance

### Audit Logging

**Implementation**: `src/commit/audit_logger.py`

Every mutating action logged to `pms_audit_log`:

```python
class AuditLogger:
    """Logs all system actions for compliance."""

    async def log_action(
        self,
        yacht_id: UUID,
        user_id: UUID,
        action: str,
        entity_type: str,
        entity_id: UUID,
        old_values: dict | None = None,
        new_values: dict | None = None
    ):
        """
        Log audit trail entry.

        Generates SHA256 signature for tamper detection:
        signature = SHA256(yacht_id + user_id + action + timestamp + details)
        """
        signature = self._generate_signature(
            yacht_id, user_id, action, entity_type, entity_id
        )

        await self.supabase.table("pms_audit_log").insert({
            "yacht_id": str(yacht_id),
            "user_id": str(user_id),
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "old_values": old_values,
            "new_values": new_values,
            "signature": signature,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
```

### Actions Logged

- User authentication (login, logout, token refresh)
- Upload events (file uploaded, processed, rejected)
- Session events (created, committed, cancelled)
- Draft line events (verified, edited, deleted)
- Permission changes (role assigned, role revoked)
- Configuration changes (settings updated)

### Compliance Reports

Generate compliance reports:

```python
# All actions by user
GET /api/v1/audit/user/{user_id}?start_date=2026-01-01&end_date=2026-01-31

# All actions on entity
GET /api/v1/audit/entity/{entity_type}/{entity_id}

# All failed actions
GET /api/v1/audit/failures?severity=high
```

### GDPR Compliance

**Right to Access**:
```bash
GET /api/v1/gdpr/data-export/{user_id}
# Returns all user data in machine-readable format (JSON)
```

**Right to Erasure**:
```bash
DELETE /api/v1/gdpr/delete-user/{user_id}
# Anonymizes PII, keeps audit trail per legal requirements
```

**Right to Rectification**:
```bash
PATCH /api/v1/gdpr/update-user/{user_id}
# Allows user to correct their personal data
```

---

## Incident Response

### Security Incident Workflow

```
┌────────────────────────┐
│  1. Detect Incident    │
│  - Monitoring alert    │
│  - User report         │
│  - Penetration test    │
└───────────┬────────────┘
            ↓
┌────────────────────────┐
│  2. Assess Severity    │
│  - P0: Active breach   │
│  - P1: Vulnerability   │
│  - P2: Potential risk  │
└───────────┬────────────┘
            ↓
┌────────────────────────┐
│  3. Contain            │
│  - Block attack        │
│  - Isolate system      │
│  - Revoke credentials  │
└───────────┬────────────┘
            ↓
┌────────────────────────┐
│  4. Investigate        │
│  - Review logs         │
│  - Identify cause      │
│  - Assess damage       │
└───────────┬────────────┘
            ↓
┌────────────────────────┐
│  5. Remediate          │
│  - Patch vulnerability │
│  - Rotate secrets      │
│  - Update policies     │
└───────────┬────────────┘
            ↓
┌────────────────────────┐
│  6. Document           │
│  - Incident report     │
│  - Lessons learned     │
│  - Update runbooks     │
└────────────────────────┘
```

### Incident Severity Levels

| Level | Description | Response Time | Examples |
|-------|-------------|---------------|----------|
| P0 | Active security breach | Immediate | Data exfiltration, unauthorized access |
| P1 | Critical vulnerability | < 1 hour | SQL injection, authentication bypass |
| P2 | High-risk issue | < 4 hours | XSS vulnerability, weak encryption |
| P3 | Medium-risk issue | < 24 hours | Information disclosure, CSRF |
| P4 | Low-risk issue | < 1 week | Security header missing, weak cipher |

### Contact Information

```
Security Team: security@cloud-pms.com
PagerDuty: +1-555-SECURITY
Slack: #security-incidents
On-call: https://pagerduty.com/cloud-pms
```

---

## Security Checklist

### Pre-Deployment

- [ ] All secrets moved to environment variables
- [ ] JWT secret has 256+ bits entropy
- [ ] TLS 1.3 enabled on all endpoints
- [ ] CORS configured for production domains only
- [ ] Security headers configured
- [ ] RLS policies enabled on all tables
- [ ] Rate limiting configured
- [ ] File validation implemented
- [ ] Audit logging enabled
- [ ] Error messages don't leak sensitive info

### Post-Deployment

- [ ] Penetration testing completed
- [ ] Security scan passed (no high/critical)
- [ ] Dependencies up to date (no known CVEs)
- [ ] Monitoring alerts configured
- [ ] Incident response plan documented
- [ ] Compliance audit completed
- [ ] Backup and recovery tested
- [ ] Security training completed for team

### Monthly Maintenance

- [ ] Review audit logs for anomalies
- [ ] Update dependencies
- [ ] Rotate long-lived credentials
- [ ] Review and update firewall rules
- [ ] Test backup restoration
- [ ] Review access permissions

### Quarterly Reviews

- [ ] Security policy review
- [ ] Penetration testing
- [ ] Compliance audit
- [ ] Disaster recovery drill
- [ ] Security training refresher

---

## Summary

The Image Processing Service implements enterprise-grade security through:

1. **Authentication**: JWT-based identity verification with HS256 signatures
2. **Authorization**: RBAC with HOD permissions + RLS for multi-tenant isolation
3. **Data Protection**: Encryption in transit (TLS 1.3) and at rest (AES-256)
4. **Network Security**: Firewall rules, CORS policies, security headers
5. **Secrets Management**: Environment variables, 90-day rotation
6. **Audit & Compliance**: Complete action logging, GDPR compliance
7. **Incident Response**: Defined workflows and severity levels

This comprehensive security architecture ensures data confidentiality, integrity, and availability while meeting regulatory requirements.

---

**References:**
- OWASP Top 10: https://owasp.org/www-project-top-ten/
- NIST Cybersecurity Framework: https://www.nist.gov/cyberframework
- GDPR Guidelines: https://gdpr.eu/
- Supabase Security: https://supabase.com/docs/guides/platform/security
