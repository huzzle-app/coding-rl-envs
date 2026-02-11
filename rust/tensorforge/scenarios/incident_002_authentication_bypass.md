# INC-002: Empty Authentication Tokens Accepted by Security Gateway

**Severity:** P0 - Security Critical
**Status:** Open
**Created:** 2024-03-18 14:22 UTC
**Reported By:** Security Operations Center (SOC)
**Impacted Services:** security, gateway, all downstream services
**Compliance Impact:** Potential PCI-DSS and SOC2 violation

---

## Executive Summary

The TensorForge security gateway is accepting empty string tokens as valid authentication credentials. This allows unauthenticated requests to bypass the authentication layer and access protected model-serving endpoints. The vulnerability was discovered during routine penetration testing.

## Discovery

During scheduled quarterly penetration testing, the security team discovered that requests with an empty `Authorization: Bearer ` header (no token value) are being accepted as valid:

```bash
# This should return 401 Unauthorized
curl -X POST https://api.tensorforge.internal/v1/dispatch/inference \
  -H "Authorization: Bearer " \
  -H "Content-Type: application/json" \
  -d '{"model_id": "gpt-inference-v3", "payload": {...}}'

# Actual response: 200 OK with inference results
# Expected response: 401 Unauthorized
```

## Observed Behavior

```
[2024-03-18T14:15:32.117Z] security::token_validator DEBUG
  token_length=0
  validation_result=VALID
  ANOMALY: Empty token should be rejected

[2024-03-18T14:15:32.118Z] gateway::auth INFO
  request_id=req-8b2c4d1f
  auth_status=authenticated
  token_preview="(empty)"
  proceeding_to_dispatch=true
```

The token validation function appears to check `token.len() >= 0` which is always true for any string, including empty strings.

## Impacted Tests

- `test_empty_token_rejected` - Verifies empty tokens are denied
- `test_token_validation_requires_content` - Token must have non-zero length
- `test_authentication_required_for_dispatch` - E2E auth enforcement
- `test_security_token_has_minimum_length` - Minimum token length check
- `hyper_matrix_scenarios::security_*` - Security validation matrix

## Scope of Exposure

| Endpoint | Protected | Currently Accessible Without Auth |
|----------|-----------|-----------------------------------|
| `/v1/dispatch/inference` | Yes | **YES - VULNERABLE** |
| `/v1/dispatch/batch` | Yes | **YES - VULNERABLE** |
| `/v1/models/list` | Yes | **YES - VULNERABLE** |
| `/v1/telemetry/export` | Yes | **YES - VULNERABLE** |
| `/health` | No | N/A (public endpoint) |

## Audit Log Analysis

```sql
-- Requests with empty or missing tokens in last 24 hours
SELECT
    COUNT(*) as request_count,
    endpoint,
    source_ip,
    MIN(timestamp) as first_seen,
    MAX(timestamp) as last_seen
FROM access_logs
WHERE (auth_token IS NULL OR auth_token = '')
  AND http_status = 200
  AND endpoint LIKE '/v1/%'
  AND timestamp > NOW() - INTERVAL '24 hours'
GROUP BY endpoint, source_ip
ORDER BY request_count DESC;
```

Results show 47 requests from internal penetration testing IPs only. No evidence of external exploitation yet.

## Immediate Mitigations Applied

1. **WAF Rule Added:** Rejecting requests with empty `Authorization` header at edge
2. **Rate Limiting:** Aggressive rate limiting on auth failures from any IP
3. **Monitoring:** Enhanced alerting on auth anomalies

## Required Fix

The token validation logic must be corrected to require a non-empty token. The check should be `token.len() > 0` or `!token.is_empty()`.

## Compliance Implications

- **PCI-DSS 8.3:** Authentication mechanisms must not be bypassable
- **SOC2 CC6.1:** Logical access controls must be enforced
- **GDPR Art. 32:** Appropriate security measures required

Legal and Compliance teams have been notified. Mandatory incident report due within 72 hours.

## Related Vulnerabilities

Also noted during testing - the password strength checker may have boundary issues. Password "8charss" (exactly 8 chars) is being rejected when it should be accepted per policy. See failing test `test_password_strength_8_chars_valid`.

---

**Security Team Contact:** security-oncall@tensorforge.internal
**Next Update:** 2024-03-18 16:00 UTC or upon status change
