# POST-MORTEM: Security Validation Bypass and Path Traversal Vulnerability

## Incident Classification

**Incident ID**: SEC-2024-0023
**Severity**: P0 - Critical Security
**Date**: 2024-11-11
**Duration**: ~18 hours (until emergency patch)
**Status**: Root Cause Analysis Required

---

## Executive Summary

A security audit identified two critical vulnerabilities in the ChronoMesh security module:

1. **Signature verification bypass**: Attackers could forge valid signatures by exploiting a truncated hash comparison
2. **Path traversal vulnerability**: Incomplete sanitization of `..` sequences allowed directory escape

Additionally, the resilience module's replay deduplication has a subtle ordering bug that could cause event replay inconsistencies.

---

## Vulnerability Details

### CVE-PENDING-001: Truncated Signature Comparison

**Affected Function**: `verify_signature()` in `security.cpp`

**Description**: The signature verification function only compares the first 8 characters of the computed digest against the expected signature, allowing collision attacks.

**Proof of Concept**:
```cpp
std::string payload = "legitimate_manifest_data";
std::string expected = digest(payload);  // e.g., "a1b2c3d4e5f6g7h8"

// Attacker finds a different payload with matching first 8 chars
std::string malicious = "malicious_payload_xyz";
std::string malicious_digest = digest(malicious);  // e.g., "a1b2c3d4xxxxxxxx"

// Verification passes because only first 8 chars are compared!
bool result = verify_signature(malicious, malicious_digest, expected);
// Returns TRUE when it should return FALSE
```

**Impact**: An attacker could:
- Forge manifest signatures
- Inject unauthorized dispatch orders
- Bypass cargo verification checks

### CVE-PENDING-002: Incomplete Path Sanitization

**Affected Function**: `sanitise_path()` in `security.cpp`

**Description**: The function only removes the first occurrence of `..` in a path, allowing attackers to bypass sanitization with multiple traversal sequences.

**Proof of Concept**:
```cpp
std::string malicious_path = "/uploads/../../../etc/passwd";
std::string sanitized = sanitise_path(malicious_path);
// Expected: "/uploads/etc/passwd" (all .. removed)
// Actual: "/uploads/../../etc/passwd" (only first .. removed!)

// Even worse case:
std::string attack = "....//....//secret";
// After single .. removal: "..//..//secret"
// Attacker can still traverse upward
```

**Impact**: Directory traversal allowing:
- Access to configuration files
- Reading sensitive credentials
- Potential arbitrary file read

---

## Resilience Module Issue

### Event Replay Ordering Bug

During investigation, the security team also identified a bug in the replay deduplication logic:

**Affected Function**: `replay()` in `resilience.cpp`

**Description**: When two events have the same ID and same sequence number, the function keeps the first one encountered instead of the latest (based on insertion order). The comparison uses `>=` instead of `>`.

**Example**:
```cpp
std::vector<Event> events = {
    {"evt-1", 100, "data-v1"},  // First event
    {"evt-1", 100, "data-v2"},  // Same ID, same sequence, newer data
};

auto replayed = replay(events);
// Expected: keeps {"evt-1", 100, "data-v2"} (latest)
// Actual: could keep either due to >= comparison (non-deterministic)
```

**Impact**:
- Non-deterministic replay behavior
- Potential data consistency issues in disaster recovery
- Audit log may show stale event data

### Checkpoint Interval Off-by-One

**Affected Function**: `should_checkpoint()` in `resilience.cpp`

The checkpoint manager has an off-by-one error:

```cpp
// Config: checkpoint every 1000 sequences
CheckpointManager mgr;
mgr.record("stream-1", 0);

// At sequence 1000:
bool should = mgr.should_checkpoint(1000);
// current_seq - last_sequence_ = 1000 - 0 = 1000
// Condition: 1000 > 1000 is FALSE
// Expected: TRUE (exactly 1000 sequences since last checkpoint)
// Actual: FALSE (misses the checkpoint window)
```

---

## Immediate Actions Taken

1. Emergency patch deployed for signature verification (adds full digest comparison)
2. WAF rules added to block paths containing `..`
3. Resilience module flagged for review (lower severity)

---

## Root Cause Analysis Request

The security team needs engineering to:

1. **Signature Verification**: Identify why only first 8 characters are being compared. The constant-time comparison looks correct, but there's an additional truncated check.

2. **Path Sanitization**: Determine why the `..` removal loop only executes once. The code should remove all occurrences.

3. **Replay Logic**: Review the sequence comparison operator. Should be strictly greater than (`>`) to keep latest, not greater-than-or-equal (`>=`).

4. **Checkpoint Timing**: Review boundary condition - should trigger at exactly the interval, not interval+1.

---

## Files for Investigation

- `src/security.cpp`: `verify_signature()`, `sanitise_path()`
- `src/resilience.cpp`: `replay()`, `CheckpointManager::should_checkpoint()`
- Associated test files

---

## Compliance Note

These vulnerabilities may require disclosure under our SOC2 obligations. Please prioritize fixes and provide timeline for complete remediation.
