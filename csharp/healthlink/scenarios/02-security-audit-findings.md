# Security Audit Report: HealthLink API Assessment

## Executive Summary

**Audit Period**: February 5-9, 2024
**Auditor**: MedSec Compliance Partners
**Scope**: HealthLink API v2.4.0 (C#/.NET 8 backend)
**Classification**: CONFIDENTIAL - HIPAA COMPLIANCE REVIEW

---

## Critical Findings

### FINDING-001: SQL Injection in Patient Data Update

**Severity**: CRITICAL
**CVSS Score**: 9.8
**CWE**: CWE-89 (SQL Injection)
**HIPAA Impact**: PHI exposure risk

**Description**:
The patient repository contains a custom query execution method that constructs SQL statements using string interpolation without parameterization. This allows arbitrary SQL injection through user-controlled input.

**Proof of Concept**:
```http
POST /api/patient/update-field HTTP/1.1
Authorization: Bearer <valid_token>
Content-Type: application/json

{
  "fieldName": "Notes",
  "value": "test'; DROP TABLE \"Patients\"; --"
}
```

**Evidence from Application Logs**:
```
Npgsql.PostgresException (0x80004005): 42601: syntax error at or near "DROP"
   STATEMENT: UPDATE "Patients" SET "Notes" = 'test'; DROP TABLE "Patients"; --' WHERE "IsActive" = true
```

The error message confirms injected SQL is being executed by PostgreSQL.

**Affected Functionality**:
- Patient custom field updates
- Bulk data operations
- Any endpoint using `ExecuteSqlRaw` or `ExecuteSqlRawAsync`

---

### FINDING-002: Path Traversal in Document Download

**Severity**: CRITICAL
**CVSS Score**: 9.1
**CWE**: CWE-22 (Path Traversal)
**HIPAA Impact**: Unauthorized PHI access

**Description**:
The document download endpoint uses `Path.Combine()` with user-supplied filenames. In .NET, `Path.Combine` returns the second argument unchanged if it's an absolute path, completely bypassing the intended directory restriction.

**Proof of Concept**:
```http
GET /api/document/download?filename=/etc/passwd HTTP/1.1
Authorization: Bearer <token>

# On Windows:
GET /api/document/download?filename=C:\Windows\System32\config\SAM HTTP/1.1
```

**Result**: Server returns contents of system files outside the intended upload directory.

**Additional Bypass Vectors Discovered**:
- Absolute paths: `/etc/passwd`, `C:\sensitive\data.txt`
- Relative with absolute prefix: `/../../../etc/passwd` (on some systems)
- UNC paths on Windows: `\\attacker-server\share\payload`

---

### FINDING-003: Weak JWT Signing Key

**Severity**: HIGH
**CVSS Score**: 8.1
**CWE**: CWE-326 (Inadequate Encryption Strength)

**Description**:
JWT tokens are signed using HMAC-SHA256 but with a key that is only 10 bytes (80 bits). HMAC-SHA256 requires a minimum of 256 bits (32 bytes) for security. The current key "short-key!" can be brute-forced in under 24 hours on commodity hardware.

**Evidence**:
```bash
# Extracted from decompiled assembly / config
Jwt:Key = "short-key!"

# Key length analysis
echo -n "short-key!" | wc -c
# Output: 10 (bytes)
```

**Impact**:
- Attacker can forge valid JWT tokens for any user
- Complete authentication bypass
- Impersonation of administrators and clinicians

---

### FINDING-004: Authorization Bypass on Patient Controller

**Severity**: HIGH
**CVSS Score**: 7.5
**CWE**: CWE-862 (Missing Authorization)

**Description**:
While reviewing controller authorization, we discovered inconsistent authorization behavior. The patient controller has `[Authorize]` attributes that appear to have no effect. Requests without valid tokens still reach protected endpoints.

**Testing Evidence**:
```http
# Request without Authorization header
GET /api/patient/123 HTTP/1.1
Host: api.healthlink.local

# Response: 200 OK with patient data
# Expected: 401 Unauthorized
```

**Notes**: The `[Authorize]` attribute is present on the controller but authentication middleware appears to not be executing for controller endpoints. This suggests a middleware configuration issue rather than missing attributes.

---

## Medium Findings

### FINDING-005: Singleton DbContext Thread Safety

**Severity**: MEDIUM
**CVSS Score**: 6.5
**CWE**: CWE-362 (Race Condition)

**Description**:
Entity Framework Core's `DbContext` is registered as a Singleton service. `DbContext` is not thread-safe and should be scoped per-request. This can cause data corruption and cross-request information leakage under concurrent load.

**Evidence from Load Testing**:
```
System.InvalidOperationException: A second operation was started on this context instance before a previous operation completed.
   at Microsoft.EntityFrameworkCore.Internal.ConcurrencyDetector.EnterCriticalSection()
```

**HIPAA Concern**: Cross-request state leakage could expose one patient's data to another user's session.

---

### FINDING-006: Unvalidated Owned Entity Configuration

**Severity**: MEDIUM
**CVSS Score**: 5.3

**Description**:
Patient address data appears in the domain model but is not being persisted to the database. Investigation suggests the Address value object is not properly configured with `OwnsOne()` in Entity Framework Core.

**Impact**: Patient address updates are silently dropped, potentially causing operational issues with appointment confirmations and billing.

---

## Low Findings

### FINDING-007: Missing Column Length Constraints

**Severity**: LOW
**Description**: String columns in the database default to `nvarchar(max)`, which can cause performance issues and allows unbounded data storage. Consider adding `HasMaxLength()` configuration.

---

## Recommendations Summary

| Priority | Action |
|----------|--------|
| P0 | Use parameterized queries (`ExecuteSqlInterpolated`) for all dynamic SQL |
| P0 | Validate and sanitize file paths - ensure final path starts with allowed directory |
| P0 | Increase JWT signing key to minimum 256 bits (32+ bytes) |
| P0 | Verify middleware ordering - authentication must run before endpoint mapping |
| P1 | Change DbContext registration from Singleton to Scoped |
| P1 | Configure owned entity mappings in DbContext |
| P2 | Add column length constraints to string properties |

---

## HIPAA Compliance Impact

The SQL injection and path traversal vulnerabilities represent potential PHI breaches under HIPAA. Immediate remediation is required before the compliance deadline (March 1, 2024).

---

**Report Prepared By**: Dr. Amanda Foster, Chief Security Consultant
**Reviewed By**: James Chen, Healthcare Compliance Specialist
**Date**: February 12, 2024
