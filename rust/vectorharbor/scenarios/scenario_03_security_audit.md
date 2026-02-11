# Scenario 03: Security Audit Findings

## Type: Security Alert

## Classification: HIGH

## Audit ID: SEC-2024-Q4-0892

---

### SECURITY ASSESSMENT REPORT

**Prepared by**: External Security Auditors
**Assessment Date**: 2024-12-10 through 2024-12-14
**System**: VectorHarbor Maritime Orchestration Platform

---

### Executive Summary

During penetration testing of the VectorHarbor platform, our team identified two critical security vulnerabilities in the path sanitization and signature verification subsystems.

---

### Finding 1: Incomplete Path Traversal Sanitization

**Severity**: HIGH
**CVSS Score**: 7.5
**CWE**: CWE-22 (Improper Limitation of a Pathname to a Restricted Directory)

**Description**:

The `sanitise_path` function in the security module fails to remove all instances of path traversal sequences. The current implementation only removes the **first occurrence** of `../` from input paths.

**Proof of Concept**:

```
Input:  "../../etc/passwd"
Expected: "etc/passwd" (all traversal removed)
Actual:   "../etc/passwd" (one traversal remains)

Input:  "foo/../../../secret/keys"
Expected: "foo/secret/keys"
Actual:   "foo/../../secret/keys"
```

**Attack Vector**:

An attacker can craft manifest paths containing multiple traversal sequences to escape the intended directory and access sensitive files.

**Recommendation**:

Replace `replacen("../", "", 1)` with a loop or `replace("../", "")` to remove all occurrences.

---

### Finding 2: Truncated Signature Verification

**Severity**: HIGH
**CVSS Score**: 8.1
**CWE**: CWE-328 (Reversible One-Way Hash)

**Description**:

The signature verification function compares only the first 8 characters of the digest, rather than the full 16-character hash. This dramatically reduces the cryptographic strength of signature validation.

**Technical Details**:

The `verify_signature` function performs:
```rust
signature.get(..8) == d.get(..8)
```

This means only 32 bits of the hash are validated instead of the full 64 bits, making collision attacks 2^32 times more feasible.

**Proof of Concept**:

Two different payloads that share the same first 8 hex characters of their digest would both pass signature verification when signed with the other's signature.

**Impact**:

- Manifest forgery possible with reduced computational effort
- Replay attacks more feasible
- Integrity guarantees compromised

**Recommendation**:

Compare the full digest string, not just a prefix.

---

### Finding 3: Service URL Generation Missing Port

**Severity**: MEDIUM
**CVSS Score**: 5.3

**Description**:

The `get_service_url` function in the contracts module generates URLs without including the service port, causing service discovery failures and potential misdirected traffic.

**Example**:
```
Expected: "http://gateway:8120/health"
Actual:   "http://gateway/health"
```

This could cause requests to be routed to wrong services or fail entirely.

---

### Remediation Timeline

| Finding | Severity | Recommended Fix Window |
|---------|----------|------------------------|
| Path Traversal | HIGH | 48 hours |
| Truncated Signature | HIGH | 48 hours |
| Missing Port | MEDIUM | 7 days |

---

### Affected Files

- `src/security.rs` - sanitise_path, verify_signature
- `src/contracts.rs` - get_service_url

---

**Report Status**: Delivered to Engineering Lead
**Acknowledgment Required By**: 2024-12-16
