# INC-2024-0891: Authentication Tokens Rejected After Security Upgrade

**Severity**: P1 - Critical
**Status**: Open
**Created**: 2024-03-15 02:47 UTC
**Component**: Security / Token Management
**Affected Services**: gateway, routing, all downstream consumers

---

## Executive Summary

Following a routine security infrastructure upgrade at 01:30 UTC, all inter-service authentication began failing. Approximately 847 vessels are currently unable to receive dispatch instructions, resulting in port congestion at 12 terminals.

Estimated revenue impact: $2.3M/hour.

---

## Timeline

| Time (UTC) | Event |
|------------|-------|
| 01:30 | Security infrastructure upgrade deployed |
| 01:45 | First alerts: token validation failures spike |
| 02:12 | On-call paged after 90% of auth requests failing |
| 02:35 | Confirmed: new tokens being rejected, old tokens still working |
| 02:47 | Incident declared, war room opened |

---

## Symptoms

1. **Token Validation Failures**
   - New tokens generated after 01:30 are rejected by all services
   - Tokens generated before upgrade continue to work until expiry
   - Error rate on `/auth/validate` endpoint: 94.7%

2. **Service-to-Service Auth Broken**
   ```
   [ERROR] gateway: token validation failed for routing-service
   [ERROR] Expected format: "subject:expires_at"
   [ERROR] Received: "1710475200000:routing-service"
   ```

3. **Session Management Issues**
   - New user sessions expire immediately
   - Session expiry calculation appears incorrect
   - Users report being logged out within seconds of login

---

## Test Failures Observed

```
FAILED: security_token_format
  Expected: "user123:999999"
  Actual: "999999:user123"

FAILED: security_session_expiry
  Expected: 4600000
  Actual: 1003600
  Note: created_at=1000000, ttl_seconds=3600

FAILED: security_hmac
  Signatures do not match expected pattern
  Token signatures generated on different services don't verify
```

---

## Investigation Notes

### Token Format Analysis
The token validation layer expects tokens in `subject:expires_at` format, but newly generated tokens appear to have the fields reversed. This causes immediate rejection by any service attempting to parse the token.

### Session Expiry Investigation
```cpp
// From service logs:
// created_at: 1710475200000 (epoch ms)
// ttl_seconds: 3600
// Expected expiry: 1710478800000 (created + ttl * 1000)
// Actual expiry: 1710475203600 (created + ttl)
```

The session expiry appears to be treating the TTL as milliseconds instead of converting from seconds.

### HMAC Verification
Cross-service signature verification is failing. Service A generates a signature, but Service B cannot verify it. Both services use identical secrets. The HMAC generation may have parameter ordering issues.

---

## Affected Tests

- `security_token_format` - Token field ordering
- `security_session_expiry` - TTL unit conversion
- `security_hmac` - Signature generation ordering
- `security_password_hash` - Hash input ordering

---

## Business Impact

- 847 vessels awaiting dispatch instructions
- 12 terminals reporting berth congestion
- Port authority escalation received from Rotterdam, Singapore, Los Angeles
- Customer support queue: 2,847 tickets

---

## Rollback Assessment

Rollback is **not recommended**. The pre-upgrade code had a critical CVE that this upgrade addressed. We need to fix forward.

---

## Next Steps

1. Investigate token formatting in `src/security.cpp`
2. Review session expiry calculation
3. Verify HMAC parameter ordering matches RFC specification
4. Coordinate with all service teams for synchronized fix deployment

---

## References

- Related: `tests/test_main.cpp` lines 355-412 (security test suite)
- Alert Dashboard: https://metrics.obsidianmesh.internal/d/sec-001
- CVE addressed by upgrade: CVE-2024-XXXX (token timing attack)
