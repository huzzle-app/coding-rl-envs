# Security Alert: Path Traversal Vulnerability in Document API

**Alert ID:** SEC-2024-0445
**Severity:** HIGH
**CVSS Score:** 7.5
**Status:** Confirmed
**Reporter:** External Security Researcher (Bug Bounty)

---

## Vulnerability Summary

A path traversal vulnerability exists in the NimbusFlow document retrieval API. While the system attempts to sanitize file paths, the sanitization is incomplete and can be bypassed using Windows-style path separators.

## Proof of Concept

### Test 1: Standard Unix Traversal (Blocked)
```bash
$ curl "https://api.nimbusflow.internal/documents?path=../../../etc/passwd"
# Result: Sanitized to "etc/passwd" - BLOCKED as expected
```

### Test 2: Windows Backslash Traversal (BYPASSED)
```bash
$ curl "https://api.nimbusflow.internal/documents?path=..\..\..\..\etc\passwd"
# Result: Path accepted as-is, returned /etc/passwd contents
# VULNERABILITY CONFIRMED
```

### Test 3: Mixed Traversal (BYPASSED)
```bash
$ curl "https://api.nimbusflow.internal/documents?path=..\..\../config/secrets.json"
# Result: Successfully accessed sensitive configuration
```

## Technical Analysis

The path sanitization function appears to only handle forward-slash traversal patterns (`../`). Backslash patterns (`..\`) are not stripped, allowing attackers to:

1. Escape the document root directory
2. Access arbitrary files on the filesystem
3. Read sensitive configuration, credentials, or system files

### Expected Sanitization Behavior
```
Input: "../../../etc/passwd"  -> Output: "etc/passwd"    (WORKING)
Input: "..\..\..\etc\passwd"  -> Output: "etc\passwd"    (BROKEN - returns as-is)
Input: "..\/..\/etc/passwd"   -> Output: "etc/passwd"    (BROKEN - partial strip)
```

## Attack Scenarios

1. **Configuration Theft:** Attacker retrieves database credentials from `/app/config/db.json`
2. **Key Exfiltration:** Access to `/app/secrets/signing.key` compromises manifest signatures
3. **Internal Discovery:** Reading `/etc/hosts` or `/proc/net/tcp` reveals internal infrastructure

## Affected Endpoints

- `GET /documents?path=<file>`
- `GET /manifests/{vesselId}/attachments?file=<file>`
- `GET /audit/logs?filename=<file>`

## Remediation Recommendations

1. Sanitize BOTH forward slash (`../`) AND backslash (`..\`) patterns
2. Normalize all path separators before sanitization
3. Consider using allowlist-based path validation instead of blocklist
4. Implement chroot or containerized file access

## Timeline

- **2024-09-10:** Vulnerability reported via bug bounty
- **2024-09-11:** Initial triage confirmed issue
- **2024-09-12:** Engineering notified
- **2024-09-15:** This alert issued

## Temporary Mitigation

WAF rule deployed to block requests containing `..\\` pattern. This is a stopgap; code fix required.

---

**Contact:** security@nimbusflow.internal
**Bug Bounty Payout:** Pending fix verification
**Classification:** Confidential - Security
