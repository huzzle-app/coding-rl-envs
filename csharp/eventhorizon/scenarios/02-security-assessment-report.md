# Security Assessment Report: EventHorizon Platform

## Executive Summary

**Assessment Period**: February 15-28, 2024
**Auditor**: CyberShield Security Partners
**Scope**: EventHorizon Ticketing Platform v3.2.1 (.NET 8)
**Classification**: CONFIDENTIAL

---

## Critical Findings

### FINDING-001: Weak JWT Signing Key

**Severity**: CRITICAL
**CVSS Score**: 9.8
**CWE**: CWE-326 (Inadequate Encryption Strength)

**Description**:
The JWT token signing key used by the Auth service is only 64 bits (8 characters). HMAC-SHA256 requires a minimum key length of 256 bits (32 bytes) to provide adequate security. The current key is susceptible to brute-force attacks.

**Evidence**:
```
Token analyzed: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
Algorithm: HS256
Key length detected: 64 bits
Required minimum: 256 bits

Brute-force estimate: < 2 hours on commodity hardware
```

**Proof of Concept**:
Using hashcat with a standard wordlist, we recovered the signing key within 47 minutes:
```
Recovered key: weak-key
```

**Impact**: Attackers can forge valid JWT tokens, impersonate any user including administrators, and gain full access to the platform.

---

### FINDING-002: SQL Injection in Search Service

**Severity**: CRITICAL
**CVSS Score**: 9.1
**CWE**: CWE-89 (SQL Injection)

**Description**:
The Search service constructs SQL queries using raw string interpolation. User-supplied search terms are directly embedded into queries without parameterization.

**Proof of Concept**:
```http
POST /api/search HTTP/1.1
Content-Type: application/json
Authorization: Bearer <token>

{
  "query": "'; DROP TABLE events; --",
  "filters": {}
}
```

**Evidence from Error Response**:
```json
{
  "error": "Npgsql.PostgresException: 42601: syntax error at or near \"DROP\""
}
```

The error confirms user input is being interpreted as SQL. While the attack shown was blocked by the statement type, we confirmed data exfiltration is possible via UNION-based injection:

```http
POST /api/search
{ "query": "' UNION SELECT password_hash FROM users WHERE role='Admin' --" }
```

**Affected Endpoint**: `SearchController.Search()`

---

### FINDING-003: Authorization Bypass via AllowAnonymous

**Severity**: HIGH
**CVSS Score**: 8.1
**CWE**: CWE-862 (Missing Authorization)

**Description**:
Several controllers have `[AllowAnonymous]` applied at the class level, which overrides `[Authorize]` attributes on individual methods. This results in sensitive endpoints being publicly accessible.

**Evidence**:

Gateway controller:
```
GET /api/gateway/admin/stats HTTP/1.1
(No Authorization header)

Response: 200 OK
{
  "totalOrders": 284521,
  "revenue": 45892341.50,
  "activeUsers": 89234
}
```

Expected: 401 Unauthorized

**Impact**: Unauthenticated access to administrative endpoints, internal statistics, and potentially sensitive operations.

---

### FINDING-004: Path Traversal in Venue Assets

**Severity**: HIGH
**CVSS Score**: 7.5
**CWE**: CWE-22 (Path Traversal)

**Description**:
The Venue service allows uploading and downloading venue floor plans and images. The file path handling is vulnerable to path traversal attacks.

**Proof of Concept**:
```http
GET /api/venues/1/assets/../../../etc/passwd HTTP/1.1
Authorization: Bearer <token>

Response: 200 OK
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
...
```

**Additional Bypass Vectors**:
- URL encoding: `%2e%2e%2f`
- Double URL encoding: `%252e%252e%252f`
- Backslash on Windows: `..\..\`
- Absolute path override: `/etc/passwd` (Path.Combine behavior)

**Impact**: Arbitrary file read on the server. In containerized environments, this exposes configuration files, secrets mounted as volumes, and potentially database connection strings.

---

## High Findings

### FINDING-005: CORS Misconfiguration

**Severity**: HIGH
**CVSS Score**: 6.8
**CWE**: CWE-942 (Overly Permissive CORS Policy)

**Description**:
The API Gateway allows CORS requests from any origin with credentials enabled.

**Evidence**:
```http
OPTIONS /api/orders HTTP/1.1
Origin: https://evil-site.com

Response Headers:
Access-Control-Allow-Origin: *
Access-Control-Allow-Credentials: true
```

**Impact**: Enables cross-site request forgery from any malicious website. Attackers can steal user sessions and perform actions on behalf of authenticated users.

---

### FINDING-006: Insecure Deserialization

**Severity**: HIGH
**CVSS Score**: 7.2
**CWE**: CWE-502 (Deserialization of Untrusted Data)

**Description**:
The Events service uses polymorphic deserialization with System.Text.Json without proper type discrimination. The `$type` discriminator allows instantiation of arbitrary types.

**Evidence**:
```json
POST /api/events
{
  "$type": "System.Diagnostics.Process, System.Diagnostics.Process",
  "StartInfo": {
    "FileName": "cmd.exe",
    "Arguments": "/c whoami"
  }
}
```

While .NET 8 has some protections, the configuration explicitly enables polymorphic deserialization without a type allowlist.

---

### FINDING-007: Rate Limiter Disabled in Production

**Severity**: MEDIUM
**CVSS Score**: 5.3
**CWE**: CWE-770 (Allocation of Resources Without Limits)

**Description**:
The rate limiting middleware is registered but effectively disabled. Environment variable override sets the rate limit to `int.MaxValue`.

**Evidence from Configuration**:
```
Environment: Production
Rate Limit Setting: 2147483647 requests/minute
Effective: No rate limiting
```

**Impact**: The platform is vulnerable to denial-of-service attacks, credential stuffing, and brute-force attempts.

---

## Medium Findings

### FINDING-008: Sensitive Data in Error Messages

**Severity**: MEDIUM
**Description**: Stack traces and internal exception details are returned to clients in error responses. This includes database schema information, file paths, and service internals.

### FINDING-009: Missing Security Headers

**Severity**: MEDIUM
**Description**: Security headers like `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy` are not set.

---

## Recommendations Summary

| Priority | Action |
|----------|--------|
| P0 | Generate new JWT signing key with minimum 256 bits |
| P0 | Parameterize all SQL queries in Search service |
| P0 | Review and fix authorization attributes on all controllers |
| P0 | Implement proper path validation and canonicalization |
| P1 | Configure CORS with explicit allowed origins |
| P1 | Disable polymorphic deserialization or use strict allowlist |
| P1 | Enable and configure rate limiting properly |
| P2 | Sanitize error messages in production |
| P2 | Add security headers |

---

## Services Requiring Immediate Attention

- `Auth` - JWT token provider
- `Search` - Query construction
- `Gateway` - Authorization, CORS, rate limiting
- `Venues` - File path handling
- `Events` - Deserialization configuration

---

**Report Prepared By**: Marcus Chen, Principal Security Consultant
**Reviewed By**: Dr. Elena Rodriguez, CISO
**Date**: March 1, 2024
