# Slack Thread: Security Audit Findings

**Channel**: #security-incidents
**Date**: 2024-03-25
**Participants**: @security-team, @platform-eng, @compliance

---

## Thread Start

**@marcus.chen** (Security Lead) - 09:15 AM

Hey team, the external security audit just wrapped up and we have some concerning findings in the QuorumLedger codebase. Going to dump them here for visibility.

---

**@marcus.chen** - 09:17 AM

**Finding 1: Timing Attack Vulnerability**

The `TimingSafeCompare` function isn't actually timing-safe. It early-returns on length mismatch which leaks information about expected token length.

```go
// From the audit report:
// "The function returns immediately if lengths differ,
// allowing attackers to determine expected length
// through timing analysis."
```

Attacker could iterate token lengths until response time changes.

---

**@sarah.kim** (Platform Eng) - 09:21 AM

Yikes. That function is used for HMAC validation on all settlement requests.

---

**@marcus.chen** - 09:23 AM

**Finding 2: Incorrect Permission Levels**

The `PermissionLevel` function has `principal` and `security` roles swapped:

```
security role -> 60 (should be 70)
principal role -> 70 (should be 60)
```

This means security officers have LESS access than principals. Already had one incident where a security officer couldn't access audit logs.

---

**@marcus.chen** - 09:26 AM

**Finding 3: Step-Up Authentication Bypass**

The `RequiresStepUp` function returns `false` for high-value transactions by security/principal roles. Should require step-up for amounts over $2M regardless of role.

Test is failing:
```
--- FAIL: TestRequiresStepUp
    security_test.go:36: expected step-up for large amount
```

---

**@david.wong** (Compliance) - 09:30 AM

The step-up bypass is a PCI-DSS violation. We need to fix this before the next audit cycle.

---

**@marcus.chen** - 09:32 AM

**Finding 4: Hash Chain Truncation**

The `ChainHash` function returns a 32-character hash instead of the full 64-character SHA-256 output. This reduces collision resistance.

```
Expected: 64-char hex string
Actual: 32-char hex string (first half only)
```

---

**@sarah.kim** - 09:35 AM

Wait, that explains why our hash verification was occasionally failing in prod. We were comparing full hashes against truncated ones.

---

**@marcus.chen** - 09:38 AM

**Finding 5: Missing Audit Requirement**

The `AuditRequired` function is missing "escalation" from the critical actions map. Escalation events aren't being logged.

```
--- FAIL: TestAuditRequired
    security_test.go:62: expected escalation to require audit
```

This is bad - we have no audit trail for approval escalations.

---

**@david.wong** - 09:42 AM

:rotating_light: We're required to log all escalation events for SOX compliance. How long has this been broken?

---

**@marcus.chen** - 09:45 AM

**Finding 6: Token Validation Boundary**

`ValidateToken` uses `<` instead of `<=` for minimum length check. Tokens of exactly `minLength` characters are incorrectly accepted.

```go
// If minLength is 16:
// Token "abcdefghijklmno" (15 chars) -> accepted (should be rejected)
// Token "abcdefghijklmnop" (16 chars) -> accepted (correct)
```

Wait, actually I think I have this backwards. Need to verify.

---

**@sarah.kim** - 09:48 AM

Let me check the test:
```
--- PASS: TestValidateToken
```

Actually this test passes but I'm seeing the logic and I think it's:
- 15 chars with minLength=16 should FAIL but currently PASSES

The bug is that exactly minLength passes validation when it shouldn't (or vice versa - need to look at the spec).

---

**@marcus.chen** - 09:52 AM

Alright, let me summarize the security bugs we need to fix:

1. Timing attack in signature comparison
2. Permission levels swapped (principal/security)
3. Step-up auth bypass for high-value txns
4. Hash chain returning truncated hash
5. Missing "escalation" in audit requirements map
6. Token length validation boundary issue

---

**@tina.jackson** (Engineering Manager) - 10:01 AM

What's the blast radius here? Which tests are failing?

---

**@sarah.kim** - 10:05 AM

```
--- FAIL: TestRequiresStepUp
--- FAIL: TestPermissionLevel
--- FAIL: TestAuditRequired
--- FAIL: TestValidateSignature  (intermittent - timing related)

Also some integration tests:
--- FAIL: TestSecurityPath_HighValueSettlement
--- FAIL: TestSecurityPath_EscalationAudit
```

---

**@marcus.chen** - 10:08 AM

Priority order IMO:
1. Timing attack (active exploit risk)
2. Step-up bypass (compliance + financial risk)
3. Audit gap (compliance)
4. Permission levels (operational)
5. Hash truncation (integrity)
6. Token validation (low risk)

---

**@tina.jackson** - 10:12 AM

Agreed. Let's get eyes on `internal/security/policy.go` ASAP. I want a fix PR up by EOD.

---

**@sarah.kim** - 10:15 AM

On it. Will coordinate with @marcus.chen on verification.

---

**Thread Resolved** (pending engineering fix)
