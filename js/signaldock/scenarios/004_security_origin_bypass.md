# Scenario 004: Unauthenticated Requests Bypassing Origin Validation

## Type: Security Alert

## Severity: HIGH

## Source: Security Operations Center (SOC)

---

## Alert Details

**Alert ID:** SEC-4721
**Timestamp:** 2024-11-18 03:42:17 UTC
**Category:** Access Control Bypass

---

## Description

Our WAF logs show successful API requests to SignalDock dispatch endpoints from sources that should be blocked by origin validation. Initial analysis suggests requests with missing or empty `Origin` headers are being allowed through.

---

## Evidence

### WAF Log Excerpt

```
[03:41:55] POST /api/dispatch/create
           Origin: (empty)
           Source IP: 185.143.xx.xx (TOR exit node)
           Result: ALLOWED

[03:42:01] POST /api/dispatch/cancel
           Origin: (not present)
           Source IP: 185.143.xx.xx
           Result: ALLOWED

[03:42:17] POST /api/manifest/sign
           Origin: null
           Source IP: 185.143.xx.xx
           Result: ALLOWED
```

### Expected Behavior

Requests without a valid `Origin` header matching our allowlist should be rejected. The allowlist contains:
- `dispatch.signaldock.com`
- `ops.signaldock.com`
- `*.signaldock.internal`

### Actual Behavior

Requests with no `Origin` header, empty string, or `null` are being allowed through without validation.

---

## Reproduction

```javascript
// This should return false (blocked)
isAllowedOrigin(null, ['signaldock.com']);
// Actually returns: true

isAllowedOrigin(undefined, ['signaldock.com']);
// Actually returns: true

isAllowedOrigin('', ['signaldock.com']);
// Actually returns: true
```

---

## Additional Concerns

During investigation, we also noticed:

1. **Path Sanitization Issue**: The `sanitisePath()` function returns `null` or `undefined` unchanged instead of rejecting invalid input. This could allow path traversal if downstream code doesn't re-validate.

2. **Digest Truncation**: The `digest()` function appears to truncate hash output to 32 characters instead of the full 64-character SHA-256 hex string. This reduces collision resistance.

---

## Affected Components

- `src/core/security.js`
  - `isAllowedOrigin()` - Origin validation
  - `sanitisePath()` - Path sanitization
  - `digest()` - Hash generation

---

## Immediate Actions Required

1. Determine if origin-less requests should be blocked or allowed
2. Review all security functions for similar edge case handling
3. Assess if any unauthorized actions occurred via this bypass

---

## Risk Assessment

An attacker could:
- Submit dispatch commands without valid credentials
- Bypass CORS protections by omitting Origin header
- Potentially execute unauthorized manifest operations
