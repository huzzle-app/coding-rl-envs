# Security Audit Report: TaskForge API Assessment

## Executive Summary

**Audit Period**: January 10-17, 2024
**Auditor**: SecureRails Consulting
**Scope**: TaskForge API v3.2.1 (Rails 7 backend)
**Classification**: CONFIDENTIAL

---

## Critical Findings

### FINDING-001: SQL Injection in Search Endpoint

**Severity**: CRITICAL
**CVSS Score**: 9.1
**CWE**: CWE-89 (SQL Injection)

**Description**:
The global search endpoint constructs SQL queries using string interpolation rather than parameterized queries for certain filter parameters.

**Proof of Concept**:
```http
GET /api/v1/search?q=test&status=todo'%20OR%201=1-- HTTP/1.1
Authorization: Bearer <token>
```

**Evidence from Error Response**:
```json
{
  "error": "PG::SyntaxError: ERROR: unterminated quoted string at or near \"'todo' OR 1=1--\""
}
```

**Impact**: Full database read access, potential data exfiltration, privilege escalation.

**Affected Functionality**: Task search with status filter parameter.

---

### FINDING-002: Unauthorized User Discovery

**Severity**: HIGH
**CVSS Score**: 7.5
**CWE**: CWE-200 (Exposure of Sensitive Information)

**Description**:
The user search functionality returns results for all users in the system, not just users within the authenticated user's organization(s).

**Proof of Concept**:
```bash
# User from Organization A can discover users in Organization B
curl -H "Authorization: Bearer <org_a_user_token>" \
     "https://api.taskforge.io/api/v1/search?q=john&include_users=true"

# Returns users from all organizations, including those the user has no access to
{
  "results": [
    {"type": "user", "name": "John Smith", "email": "john@competitor.com"},
    {"type": "user", "name": "John Doe", "email": "jdoe@secretcorp.com"}
  ]
}
```

**Impact**: Competitor intelligence gathering, targeted phishing attacks, violation of data isolation between tenants.

---

### FINDING-003: Authentication Timing Attack

**Severity**: HIGH
**CVSS Score**: 7.4
**CWE**: CWE-208 (Observable Timing Discrepancy)

**Description**:
The login endpoint exhibits measurably different response times depending on whether an email address exists in the system.

**Proof of Concept**:
```
# Non-existent email - fast response
POST /api/v1/auth/login
{"email": "nonexistent@example.com", "password": "test"}
Average response time: 12ms

# Existing email - slower response (password check occurs)
POST /api/v1/auth/login
{"email": "valid@customer.com", "password": "wrongpassword"}
Average response time: 156ms
```

**Impact**: User enumeration allows attackers to:
- Build list of valid email addresses
- Focus brute force attacks on known accounts
- Enable targeted phishing campaigns

**Additional Finding**: Different error messages for "Invalid credentials" vs "Invalid password" further confirm email existence.

---

### FINDING-004: Insecure Token Comparison

**Severity**: HIGH
**CVSS Score**: 7.2
**CWE**: CWE-208 (Observable Timing Discrepancy)

**Description**:
Refresh token validation uses standard string comparison (`==`) instead of constant-time comparison, making it vulnerable to timing attacks.

**Technical Details**:
Standard string comparison returns early when the first character mismatch is found. An attacker can measure response times to gradually discover valid tokens character by character.

**Affected Endpoint**: `POST /api/v1/auth/refresh`

---

## Medium Findings

### FINDING-005: Account Enumeration via Password Reset

**Severity**: MEDIUM
**CVSS Score**: 5.3
**CWE**: CWE-204 (Observable Response Discrepancy)

**Description**:
Error messages on the login endpoint reveal whether an account exists, enabling user enumeration.

**Evidence**:
```
# Non-existent user
Response: {"error": "Invalid credentials"}

# Existing user, wrong password
Response: {"error": "Invalid password"}
```

---

### FINDING-006: Weak JWT Configuration

**Severity**: MEDIUM
**CVSS Score**: 6.5
**CWE**: CWE-798 (Use of Hard-coded Credentials)

**Description**:
JWT signing uses a weak default secret when `JWT_SECRET` environment variable is not set. Additionally, token type (access vs refresh) is not verified, allowing refresh tokens to be used as access tokens.

**Evidence**:
- Default secret is predictable/common
- Access and refresh tokens are interchangeable

---

### FINDING-007: Authorization Bypass in Development Mode

**Severity**: MEDIUM (High in exposed dev environments)
**CVSS Score**: 5.4
**CWE**: CWE-269 (Improper Privilege Management)

**Description**:
Several authorization checks are bypassed when `Rails.env.development?` returns true. If development configurations leak to production or staging environments are exposed, this creates privilege escalation vulnerabilities.

**Evidence**:
Task assignment authorization always returns true in development mode, allowing any user to assign tasks to projects they don't have access to.

---

## Low Findings

### FINDING-008: Synchronous Email Delivery Blocking Responses

**Severity**: LOW (Availability concern)
**Description**: User registration sends confirmation email synchronously, causing slow response times (~2-5 seconds) and potential timeout issues.

---

## Recommendations Summary

| Priority | Action |
|----------|--------|
| P0 | Use parameterized queries for all search filters |
| P0 | Scope user search to organization members only |
| P0 | Implement constant-time token comparison |
| P0 | Use consistent response times for login (add artificial delay) |
| P1 | Verify JWT token type matches expected usage |
| P1 | Require strong JWT_SECRET in production |
| P1 | Remove development-mode authorization bypasses |
| P2 | Use async email delivery for registration |

---

## Remediation Verification

Upon receiving fixes, SecureRails Consulting will perform verification testing at no additional charge within the 30-day remediation window.

---

**Report Prepared By**: Sarah Chen, Senior Security Consultant
**Reviewed By**: Dr. Marcus Williams, Principal Security Architect
**Date**: January 17, 2024
