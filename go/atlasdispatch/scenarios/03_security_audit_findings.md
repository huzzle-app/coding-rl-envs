# Security Alert: Critical Findings from Q4 Penetration Test

**Classification:** CONFIDENTIAL
**Report ID:** SEC-2024-Q4-PENTEST-003
**Severity:** CRITICAL
**Prepared By:** CyberShield Maritime Security Consultants
**Date:** 2024-11-08

---

## Executive Summary

During the Q4 penetration test of the AtlasDispatch platform, our security team identified multiple critical vulnerabilities in the authentication, authorization, and input validation subsystems. Several of these vulnerabilities are actively exploitable and require immediate remediation.

---

## Finding 1: Token Validation Logic Inverted

**CVSS Score:** 9.1 (Critical)
**CWE:** CWE-613 Insufficient Session Expiration

### Observation

The token validation logic appears to have inverted expiration checking. Expired tokens are being accepted while valid tokens are being rejected.

### Test Case

```
Token created: 2024-11-08 10:00:00 UTC
Token expires: 2024-11-08 10:30:00 UTC
Current time:  2024-11-08 11:00:00 UTC (30 minutes AFTER expiry)

Expected: Token should be REJECTED (expired)
Actual: Token is ACCEPTED

Current time:  2024-11-08 10:15:00 UTC (15 minutes BEFORE expiry)

Expected: Token should be ACCEPTED (valid)
Actual: Token is REJECTED
```

### Impact

Attackers can use expired tokens indefinitely, while legitimate users with valid tokens are denied access.

---

## Finding 2: Path Traversal via URL Encoding

**CVSS Score:** 8.6 (High)
**CWE:** CWE-22 Path Traversal

### Observation

The path sanitization function does not decode URL-encoded path components before checking for traversal sequences.

### Proof of Concept

```
Input: "/documents/%2e%2e/%2e%2e/etc/passwd"
After filepath.Clean: "/documents/../../../etc/passwd"

The ".." check is performed on the RAW input before percent-decoding.
%2e%2e is not detected as ".." and the check passes.
```

### Impact

Attackers can access files outside the intended directory by using percent-encoded traversal sequences.

---

## Finding 3: Origin Allowlist Case Sensitivity Bypass

**CVSS Score:** 6.5 (Medium)
**CWE:** CWE-178 Improper Handling of Case Sensitivity

### Observation

The origin validation uses case-sensitive string comparison, allowing bypass through case variation.

### Test Case

```
Allowlist: ["api.atlasdispatch.com", "portal.atlasdispatch.com"]

Request Origin: "API.ATLASDISPATCH.COM"
Expected: ALLOWED (same domain, different case)
Actual: BLOCKED

Request Origin: "Api.AtlasDispatch.Com"
Expected: ALLOWED
Actual: BLOCKED
```

However, this also means an attacker could potentially exploit inconsistencies between this check and downstream systems that normalize case.

---

## Finding 4: Weak HMAC Secrets Permitted

**CVSS Score:** 7.4 (High)
**CWE:** CWE-326 Inadequate Encryption Strength

### Observation

The manifest signing function does not enforce a minimum secret length, allowing trivially weak secrets.

### Test Case

```go
secret := "a"  // Single character secret
signature := SignManifest("important cargo manifest", secret)
// Signature is computed without any warning or error
```

### Impact

Short secrets are vulnerable to brute-force attacks. Industry standard recommends minimum 32-byte secrets for HMAC-SHA256.

---

## Finding 5: Signature Verification Logic Flaw

**CVSS Score:** 8.8 (High)
**CWE:** CWE-347 Improper Verification of Cryptographic Signature

### Observation

The `VerifySignature` function contains a logic error in its comparison chain. After constant-time comparison of signature to expected, it then compares `expected` to the computed digest rather than `signature` to the computed digest.

### Analysis

```go
// Pseudocode of observed behavior:
digest := Digest(payload)
if signature != expected { return false }  // First check
return expected == digest                   // Should be: signature == digest
```

This creates scenarios where valid signatures fail verification and potentially allows signature forgery in edge cases.

---

## Finding 6: Empty Payload Hash Behavior

**CVSS Score:** 4.3 (Medium)
**CWE:** CWE-354 Improper Validation of Integrity Check Value

### Observation

The `Digest` function accepts empty payloads without validation, returning the hash of an empty string. This is a known constant value that could be exploited.

### Test Case

```
Digest("") returns: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
```

This predictable value could be used in replay attacks or signature forgery attempts.

---

## Remediation Timeline

| Finding | Severity | Recommended Fix Window |
|---------|----------|----------------------|
| Token Validation | Critical | 24 hours |
| Path Traversal | High | 48 hours |
| Signature Verification | High | 48 hours |
| Weak HMAC Secrets | High | 72 hours |
| Origin Case Sensitivity | Medium | 7 days |
| Empty Payload Hash | Medium | 7 days |

---

## Next Steps

1. Engineering to review `/internal/security/security.go`
2. Implement fixes for critical/high findings
3. Schedule re-test for 2024-11-15
4. Update security documentation

---

**Report Distribution:** Engineering Lead, Security Team, CTO
**Classification Review:** 2024-12-08
