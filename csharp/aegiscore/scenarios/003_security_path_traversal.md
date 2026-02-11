# SECURITY ALERT: Path Traversal Vulnerability in Document Sanitization

**Classification**: CONFIDENTIAL - Security Team Only
**CVE Tracking**: Pending assignment
**CVSS Score**: 7.5 (High)
**Discovered By**: Internal Security Audit
**Date**: 2024-11-13

---

## Vulnerability Summary

The `Security.SanitisePath()` function in AegisCore contains an incomplete path traversal mitigation. The current implementation only removes the FIRST occurrence of directory traversal sequences, allowing attackers to craft payloads that bypass the sanitization.

## Technical Details

### Vulnerable Code Path

The `SanitisePath` method is used to sanitize file paths for:
- Manifest document retrieval
- Audit log file access
- Configuration file loading

### Attack Vector

The sanitization uses `String.Replace()` which only replaces the first occurrence by default in the current implementation pattern. An attacker can bypass this with nested traversal sequences.

**Example Malicious Input**:
```
../../../etc/passwd
....//....//etc/passwd
..\..\..\..\windows\system32\config
```

**After Sanitization** (Current Behavior):
```
../../etc/passwd         # First ../ removed, second remains
...//...//etc/passwd     # Only first occurrence stripped
..\..\..\windows\system32\config  # First ..\ removed
```

### Root Cause

Two related issues (AGS0012, AGS0013):
1. The `Replace("../", "")` call does not loop to remove all occurrences
2. Same issue exists for backslash variant `..\\`

## Proof of Concept

```csharp
// Expected: "etc/passwd" or sanitized safe path
// Actual: "../../etc/passwd" - traversal sequences remain
var result = Security.SanitisePath("../../../etc/passwd");
```

## Affected Components

- Document manifest retrieval API
- Audit log viewer
- Configuration management endpoints

## Impact Assessment

- **Confidentiality**: HIGH - Unauthorized file read possible
- **Integrity**: MEDIUM - Could read sensitive configuration
- **Availability**: LOW - No direct denial of service

## Remediation Required

The sanitization loop must continue until no more traversal sequences remain. A single-pass replacement is insufficient for nested attack payloads.

## Failing Security Tests

```
SanitisePathTraversalNested
SanitisePathMultipleOccurrences
SanitisePathMixedSlashes
```

## Interim Mitigation

- WAF rule deployed to block requests containing `..` sequences
- Additional input validation at API gateway level
- Monitoring alert for any path containing traversal attempts

---

**Status**: Active Exploitation Not Detected
**Disclosure Timeline**: Internal fix required within 14 days
**Bug IDs**: AGS0012, AGS0013
