# SECURITY-2024-0293: Rate Limiting Ineffective Behind Load Balancer

**Priority**: P1 - Security
**Status**: Open
**Reporter**: SecOps Team
**Created**: 2024-03-18 09:15 UTC
**Component**: heliosops-queue (RateLimiter)

---

## Issue Description

The API rate limiting system is not correctly identifying and throttling abusive clients when traffic passes through our AWS Application Load Balancer. A single client was able to make 50,000+ requests in under 60 seconds despite a configured limit of 100 requests per minute.

## Reproduction Environment

- Production cluster: us-east-1
- Load balancer: ALB with X-Forwarded-For header injection
- Client: Automated scanner from external IP 203.0.113.47

## Attack Timeline

```
09:12:14 UTC - Abuse detection triggered: 50,847 requests in 58 seconds
09:12:15 UTC - Source identified: 203.0.113.47 (via X-Forwarded-For)
09:12:16 UTC - WAF block applied manually
09:12:30 UTC - Incident logged, investigation started
```

## Evidence

### Request Logs (sample)

```json
{
  "timestamp": "2024-03-18T09:12:14.123Z",
  "remote_addr": "10.0.1.45",
  "x_forwarded_for": "203.0.113.47",
  "path": "/api/v1/incidents",
  "method": "GET",
  "rate_limit_result": "allowed",
  "rate_limit_remaining": 99
}
```

Note that `remote_addr` shows the internal ALB IP (10.0.1.45) while the actual client IP is in `x_forwarded_for`.

### Rate Limiter Metrics

```
rate_limiter.checks{client="10.0.1.45"}: 50,847
rate_limiter.checks{client="203.0.113.47"}: 0
rate_limiter.rejected: 0
```

All requests were attributed to the ALB's internal IP, not the actual client.

## Expected Behavior

The `RateLimiter` should:
1. Check `X-Forwarded-For` header when present
2. Use the leftmost IP (original client) for rate limit bucketing
3. Correctly throttle clients behind proxies/load balancers

## Actual Behavior

- Rate limiter only checks `remote_addr` from the request
- All requests from different clients behind the ALB share one bucket
- Legitimate clients may be incorrectly throttled
- Malicious clients can bypass limits entirely

## Secondary Concern: Information Disclosure

During investigation, we noticed the rate limiter's error response includes a full Python traceback:

```json
{
  "error": "rate limit exceeded",
  "detail": "...",
  "traceback": "Traceback (most recent call last):\n  File \"/app/heliosops/queue.py\", line 152...",
  "request_ip": "10.0.1.45"
}
```

This exposes internal file paths and code structure to external clients.

## Impact Assessment

| Category | Impact |
|----------|--------|
| Availability | HIGH - Unthrottled traffic can overwhelm backend |
| Security | HIGH - Rate limit bypass enables brute force attacks |
| Data Exposure | MEDIUM - Stack traces reveal internal paths |

## Requested Actions

1. Investigate `RateLimiter._extract_key()` method for header handling
2. Review `handle_error()` for information disclosure
3. Deploy fix with appropriate proxy-aware header parsing

## Configuration Context

Our ALB is configured to inject `X-Forwarded-For` headers. The rightmost IP is the ALB itself; the leftmost is the original client. Standard proxy header handling should use the leftmost entry.

---

**Attachments**:
- `rate_limit_bypass_evidence.pcap`
- `error_response_sample.json`

**Related Tickets**: SEC-2024-0287 (JWT validation concerns)
