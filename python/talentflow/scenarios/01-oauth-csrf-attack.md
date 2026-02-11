# Security Incident: Suspicious OAuth Login Activity

## PagerDuty Alert

**Severity**: Critical (P1)
**Triggered**: 2024-01-18 14:22 UTC
**Acknowledged**: 2024-01-18 14:25 UTC
**Team**: Security Operations

---

## Alert Details

```
SECURITY: Multiple OAuth login anomalies detected
Host: talentflow-api-prod.us-east-1.internal
Service: accounts-oauth
Pattern: Unusual state parameter behavior
Risk: Account takeover possible
```

## Incident Summary

Our security monitoring system detected a pattern of OAuth login activity that bypasses our CSRF protection. An external security researcher reported that users can be tricked into logging in to attacker-controlled accounts.

---

## Security Researcher Report (Bug Bounty #TF-2024-0127)

**Reported By**: alex.security@whitehatsec.io
**Submitted**: 2024-01-17 09:15 UTC
**Severity Assessment**: Critical

### Description

I discovered a CSRF vulnerability in the TalentFlow OAuth login flow. The OAuth callback endpoint does not validate the `state` parameter, allowing attackers to bypass CSRF protection.

### Attack Scenario

1. Attacker initiates OAuth flow with Google, obtains authorization code
2. Attacker crafts malicious link: `https://talentflow.io/oauth/callback?code=ATTACKER_CODE&state=arbitrary`
3. Victim clicks link (via phishing email, XSS, etc.)
4. Victim is logged in as the attacker's account
5. Victim enters sensitive data (resumes, job applications) thinking it's their account
6. Attacker later accesses this data via their own login

### Proof of Concept

```bash
# Attacker initiates OAuth
curl "https://talentflow.io/api/v1/accounts/oauth/?provider=google"
# Returns: {"state": "abc123...", "authorization_url": "..."}

# Attacker completes OAuth, gets code
# Attacker sends victim this link:
# https://talentflow.io/api/v1/accounts/oauth/callback/?code=ATTACKER_CODE&state=ANYTHING

# Server processes without validating state
curl "https://talentflow.io/api/v1/accounts/oauth/callback/?code=valid_code&state=attacker_controlled"
# Returns: {"access_token": "...", "user": {...}}
# BUG: Server should reject because state doesn't match any issued state
```

---

## Internal Investigation

### Slack Thread: #security-ops

**@sec.jennifer** (14:30):
> Team, we have a confirmed CSRF vuln in OAuth. The callback endpoint is processing arbitrary state values.

**@dev.marcus** (14:35):
> Looking at the code now. In `oauth.py`, the `process_oauth_callback` function receives `state` but never calls `validate_oauth_state()`. There's even a TODO comment about it.

**@sec.jennifer** (14:38):
> Can you confirm? This is a critical issue - we need to understand the full impact.

**@dev.marcus** (14:42):
> Confirmed. The validation code exists but it's commented out:
> ```python
> # TODO: Add state validation
> # oauth_state = validate_oauth_state(state)
> ```
> The function just passes `state` through without checking it.

**@sec.jennifer** (14:45):
> How many users could be affected? Do we have logs of suspicious OAuth callbacks?

**@sre.kim** (14:48):
> Checking logs... I see several callbacks in the last week where the `state` parameter doesn't match any state we issued. Could be legitimate errors or exploitation attempts.

**@dev.marcus** (14:52):
> The `validate_oauth_state` function is implemented and looks correct - it checks expiration and marks states as used. We just need to call it.

---

## Log Analysis

```
2024-01-17T08:45:12Z INFO  OAuth callback received provider=google state=unrecognized_state_1
2024-01-17T08:45:12Z INFO  OAuth login successful user_id=user_abc123
# Note: No error despite state not matching any issued state

2024-01-17T11:23:45Z INFO  OAuth callback received provider=google state=random_string_test
2024-01-17T11:23:45Z INFO  OAuth login successful user_id=user_def456
# Another successful login with arbitrary state

2024-01-18T09:12:33Z INFO  OAuth state created state=valid_state_xyz provider=google
2024-01-18T09:12:45Z INFO  OAuth callback received provider=google state=different_state_abc
2024-01-18T09:12:45Z INFO  OAuth login successful user_id=user_ghi789
# State issued was "valid_state_xyz" but callback used "different_state_abc"
```

---

## Impact Assessment

- **Affected Endpoints**: `/api/v1/accounts/oauth/callback/`
- **Attack Complexity**: Low - no special privileges required
- **User Impact**: Account takeover via login CSRF
- **Data at Risk**: User profiles, uploaded resumes, job applications, interview notes
- **Regulatory**: Potential GDPR/CCPA implications if PII exposed

---

## Customer Reports

Three enterprise customers reported suspicious activity in the last 48 hours:

1. **Acme Corp**: User found unfamiliar documents in their account
2. **TechStart Inc**: HR manager reported being logged into wrong account after clicking email link
3. **GlobalHire**: Security team flagged unusual OAuth login patterns

---

## Files to Investigate

Based on the security report and code review:
- `apps/accounts/oauth.py` - OAuth callback handling
- `apps/accounts/views.py` - OAuth endpoint implementations

---

## Remediation Priority

**IMMEDIATE**: The OAuth callback must validate the state parameter against our issued states before processing the login.

---

**Status**: CONFIRMED VULNERABILITY
**CVE Request**: Pending
**Assigned**: @security-team
**Deadline**: 2024-01-18 EOD
