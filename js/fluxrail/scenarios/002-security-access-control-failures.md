# SECURITY ALERT SEC-2024-0892: Access Control Authorization Failures

**Classification:** Security Critical
**CVSSv3 Score:** 8.1 (High)
**Status:** Active Investigation
**Reported by:** InfoSec Automated Scan
**Date:** 2024-11-13 18:22 UTC

---

## Executive Summary

Multiple security anomalies detected in the authorization subsystem. The `allowed()` function appears to be returning inverted results - denying legitimate actions while potentially allowing unauthorized ones. Additionally, signature verification is accepting malformed payloads.

## Detailed Findings

### Finding 1: Role-Based Access Control Inversion

Operators with legitimate `read` permissions are being denied access, while the underlying logic appears to be inverted from its intended behavior.

**Evidence from security audit logs:**

```
[AUDIT] user=ops-controller-7 role=Operator action=read result=DENIED
  expected=ALLOWED
  note="Standard read operation denied despite valid role"

[AUDIT] user=shift-lead-12 role=REVIEWER action=approve result=DENIED
  expected=ALLOWED
  note="Reviewer cannot approve - all approval workflows blocked"
```

**Note:** Role names in the LDAP directory use various casings (`Operator`, `REVIEWER`, `Admin`). The system appears to be performing case-sensitive lookups against a lowercase registry.

### Finding 2: Payload Signature Verification Weakness

The `verifyPayload` function is accepting signatures with incorrect lengths, returning `true` instead of `false` for mismatched signatures.

**Proof of concept (do not run in production):**

```javascript
// This SHOULD return false but returns true
verifyPayload("sensitive-data", "wrong-length-sig", "secret")
```

### Finding 3: Token Freshness Boundary Error

Tokens expiring at exactly `issuedAt + ttl` are being rejected as expired, causing intermittent authentication failures during the exact second of expiry.

```
Token issued: 1000, TTL: 300, Current: 1300
Expected: VALID (at boundary)
Actual: INVALID
```

### Finding 4: Fingerprint Deduplication Mismatch

Event fingerprints are being generated with inconsistent casing, causing duplicate events to bypass deduplication:

```
fingerprint("Tenant-A", "Trace-1", "Dispatch") = "TENANT-A:TRACE-1:DISPATCH"
// But downstream systems expect lowercase: "tenant-a:trace-1:dispatch"
```

## Affected Test Suites

```
npm test -- tests/unit/security.test.js
npm test -- tests/unit/authorization.test.js
npm test -- tests/integration/security-compliance.test.js
```

Key failing assertions:
- `role matrix allows and denies expected actions`
- `token freshness guard`
- `fingerprint normalizes inputs`

## Affected Code Paths

- `src/core/security.js` - `allowed()`, `tokenFresh()`, `fingerprint()`
- `src/core/authorization.js` - `verifyPayload()`

## Immediate Actions Required

1. **DO NOT** deploy any changes until authorization logic is verified
2. Audit recent access logs for anomalous patterns
3. Review all role permission checks in affected timeframe
4. Verify no unauthorized escalation occurred

## Compliance Impact

- SOC2 Type II audit scheduled for next month
- PCI-DSS compliance requires functioning access controls
- GDPR Article 32 requires appropriate security measures

---

**Security Team Contact:** security-oncall@fluxrail.internal
**Escalation Path:** CISO direct line for P0 security events
