# Scenario 04: Mobile App Token Refresh Causes Auth Failures

**Severity**: P2 (High)
**Reported By**: Mobile App Team / Customer Support
**Date**: Monday, 9:15 AM EST (Market Open)

---

## Incident Summary

Users of the NexusTrade mobile app experience authentication failures when resuming the app from background. The issue is most prevalent at market open when many users simultaneously access the app. Users report being logged out unexpectedly or receiving "Invalid token" errors.

## Symptoms

### Primary Complaint

Customer support received 847 tickets this morning:

```
"I opened the app to check my portfolio and got logged out!"
"App says my session expired but I used it 5 minutes ago"
"Had to log in 3 times this morning, keeps kicking me out"
"Got 'Invalid refresh token' error, had to reset password"
```

### Observed Behaviors

1. **Concurrent refresh attempts fail**:
   ```
   [09:30:01.234] POST /auth/refresh token=abc123 -> 200 OK, new_token=xyz789
   [09:30:01.235] POST /auth/refresh token=abc123 -> 401 "Invalid refresh token"
   [09:30:01.236] POST /auth/refresh token=abc123 -> 401 "Invalid refresh token"
   ```

2. **Pattern: Multiple devices or app instances**:
   - User has app on phone + tablet
   - Both attempt refresh simultaneously at market open
   - First request succeeds, revokes old token
   - Second request fails because token already revoked

3. **Mobile app retry behavior amplifies issue**:
   ```
   App wake from background
   -> Check token expiry
   -> Token expired (5min lifetime)
   -> Call /auth/refresh
   -> If 401: retry immediately (3 times)
   -> Each retry fails because token already revoked
   -> Force logout
   ```

4. **Timing correlation with failures**:
   - Failures spike at 9:30 AM (market open)
   - Secondary spike at 4:00 PM (market close)
   - Minor spikes at :00 and :30 of each hour (users checking)

### JWT Token Claims Missing

Users report that after successful login, some API calls fail with permission errors:

```
[09:31:15] GET /orders?user_id=abc -> 403 Forbidden
User claims "roles" missing from JWT
```

Looking at the JWT payload:
```json
{
  "sub": "user-uuid-here",
  "email": "trader@example.com",
  "username": "trader123",
  "iat": 1710500000,
  "exp": 1710503600
}
```

Missing: `roles`, `permissions`, `tenant_id`

## Impact

- **User Experience**: 12% of mobile users logged out at market open
- **Trading**: Users missed trading opportunities while re-authenticating
- **Support**: 847 tickets in 2 hours, 4-hour response SLA breached
- **Retention**: 3 users mentioned switching to competitor in feedback

## Initial Investigation

### What We've Ruled Out
- Token expiry too short (5 min is intentional for security)
- Server capacity issues (auth service p99 < 50ms)
- Database connection issues (all queries < 10ms)
- Redis cache issues (not used for tokens)

### Suspicious Observations

1. **Refresh token handling lacks atomicity**:
   ```python
   # Current flow (from logs):
   1. Find token in DB (token=abc123, revoked=False)
   2. Mark token as revoked
   3. Create new refresh token
   4. Return new tokens

   # Race window between steps 1 and 2
   ```

2. **No distributed lock on refresh operation**:
   - Two requests can both find token valid
   - Both proceed to revoke and create new
   - One succeeds, one fails on subsequent request

3. **Access token missing required claims**:
   - JWT creation doesn't include roles/permissions
   - Downstream services can't authorize properly
   - Forces users to re-authenticate with full login

4. **Service-to-service auth bypass possible**:
   - `X-Internal-Service` header check is too permissive
   - Empty string passes the check (should be non-empty)

### Relevant Code Paths
- `services/auth/views.py` - refresh endpoint
- `services/auth/views.py` - create_access_token function
- `services/auth/views.py` - service_auth endpoint
- `services/auth/models.py` - RefreshToken model

## Reproduction Steps

### Concurrent Refresh Test
1. Login and obtain refresh_token
2. Spawn 3 concurrent requests to /auth/refresh with same token
3. Expected: 1 success, 2 graceful failures or retries
4. Actual: 1 success, 2 hard 401 failures

### Token Claims Test
1. Login as user with admin role
2. Decode returned access_token (JWT)
3. Expected: Contains "roles": ["admin", "trader"]
4. Actual: No "roles" claim present

### Service Auth Bypass Test
1. Call /auth/service_auth with header `X-Internal-Service: `  (empty string)
2. Expected: 401 Unauthorized
3. Actual: Returns valid service token

## Questions for Investigation

- How is the refresh token revocation synchronized for concurrent requests?
- What claims should be included in the access token?
- Is there a grace period where old tokens remain valid?
- How does service-to-service authentication validate the header?

---

**Status**: Unresolved
**Assigned**: Identity/Auth Team
**SLA**: 8 hours (P2)
