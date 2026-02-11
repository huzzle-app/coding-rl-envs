# Scenario 05: Authentication and Authorization Vulnerabilities

## Security Ticket - AERO-SEC-2024-0089

**Reporter:** Security Operations Team
**Severity:** P1 - Critical (Security)
**Status:** Investigation
**CVE:** Pending

---

### Summary

Penetration testing has identified multiple vulnerabilities in the Aerolith authentication and authorization subsystem. Several bypasses allow unauthorized access to restricted operations.

### Vulnerability Details

#### VULN-001: Empty Token Acceptance

**Description:** The token validation accepts empty strings as valid tokens.

**Reproduction:**
```
Token: ""
Expected: REJECTED
Actual: ACCEPTED
```

**Analysis:** The length check uses `>= 0` which is always true for unsigned lengths.

---

#### VULN-002: Password Strength Bypass

**Description:** Password strength checker uses strict inequality, causing boundary values to be mis-classified.

**Reproduction:**
```
Password: "12345678" (exactly 8 chars)
Expected: "medium"
Actual: "weak"
```

**Analysis:** Boundaries use `>` instead of `>=`. An 8-character password needs >8 to be medium.

---

#### VULN-003: Sensitive Data Exposure

**Description:** Mask function exposes first 4 characters instead of last 4.

**Reproduction:**
```
Value: "sk_live_abc123xyz"
Expected: "*************xyz"
Actual: "sk_l*************"
```

**Analysis:** The visible portion is taken from the start instead of the end.

---

#### VULN-004: Rate Limit Bypass

**Description:** Rate limiting key only uses path, not IP address. All requests to the same path share a rate limit bucket.

**Reproduction:**
```
IP: "10.0.0.1", Path: "/api/commands"
IP: "10.0.0.2", Path: "/api/commands"
Expected: Different rate limit buckets
Actual: Same bucket (key = "ratelimit:/api/commands")
```

---

#### VULN-005: Session Expiry Bypass

**Description:** Session expiry calculation subtracts TTL instead of adding, causing sessions to appear expired immediately or never expire.

**Reproduction:**
```
created_at: 1000, ttl: 3600, now: 1500
Expected: NOT expired (1500 < 1000 + 3600)
Actual: EXPIRED (1500 > 1000 - 3600)
```

---

#### VULN-006: Header Injection

**Description:** Header sanitization only removes `\n`, leaving `\r` which enables header injection attacks.

**Reproduction:**
```
Input: "value\r\nX-Injected: malicious"
Expected: "valueX-Injected: malicious"
Actual: "value\rX-Injected: malicious"
```

---

#### VULN-007: Permission Check Bypass

**Description:** Permission check uses `any` instead of `all`, allowing access with partial permissions.

**Reproduction:**
```
Required: ["read", "write", "admin"]
User has: ["read"]
Expected: DENIED
Actual: ALLOWED
```

---

#### VULN-008: IP Allowlist Bypass

**Description:** IP allowlist uses prefix matching instead of exact match.

**Reproduction:**
```
Allowlist: ["10.0.0.1"]
Request IP: "10.0.0.100"
Expected: DENIED
Actual: ALLOWED (starts_with "10.0.0.1")
```

---

#### VULN-009: Credential Hash Order

**Description:** Hash function concatenates password:salt instead of salt:password, making rainbow table attacks easier.

**Reproduction:**
```
Password: "secret", Salt: "random123"
Expected: "hash(random123:secret)"
Actual: "hash(secret:random123)"
```

---

#### VULN-010: Token Expiry Wrong Sign

**Description:** Token expiry calculation subtracts TTL from issued_at.

**Reproduction:**
```
issued_at: 1000000, ttl: 3600
Expected expiry: 1003600
Actual expiry: 996400 (already in the past)
```

---

#### VULN-011: Scope Matching Too Permissive

**Description:** Scope check uses `contains` instead of exact match.

**Reproduction:**
```
User scope: "read_only"
Required scope: "read"
Expected: DENIED
Actual: ALLOWED ("read_only" contains "read")
```

---

#### VULN-012: Role Hierarchy Inverted

**Description:** Role hierarchy returns lowest number for admin and highest for observer, inverting privilege levels.

**Reproduction:**
```
role_hierarchy("admin") -> 1
role_hierarchy("observer") -> 3
Expected: admin > observer
Actual: observer > admin (numerically)
```

---

### Additional Configuration Issues

During investigation, we also identified issues in `src/config.rs`:

1. **Default altitude** returns 400km instead of 550km
2. **Concurrent connections** default to 16 instead of 32
3. **Port validation** always passes (>= 0 always true for unsigned)
4. **Satellite ID validation** uses `contains` instead of `starts_with`
5. **Environment normalization** uses uppercase instead of lowercase
6. **Telemetry retention** defaults to 12 hours instead of 24
7. **Timeout default** is 600s instead of 300s
8. **Tag parsing** splits on `;` instead of `,`
9. **Status validation** only accepts "operational", missing "nominal"
10. **Priority ordering** swaps production and development values
11. **Endpoint formatting** uses port:host instead of host:port
12. **Reconnect delay** is 30000ms instead of 5000ms

### Impact

- Unauthorized command execution possible
- Session hijacking via header injection
- Rate limiting ineffective
- Privilege escalation via role confusion

### Files to Investigate

- `src/auth.rs` - Authentication and authorization
- `src/config.rs` - Configuration and validation

### Reproduction

```bash
cargo test auth
cargo test token
cargo test permission
cargo test session
cargo test config
cargo test validation
```

### Remediation Priority

1. Fix empty token validation (VULN-001)
2. Fix permission check logic (VULN-007)
3. Fix IP allowlist matching (VULN-008)
4. Fix header sanitization (VULN-006)
5. Fix remaining vulnerabilities
