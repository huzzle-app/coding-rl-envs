# Slack Thread: #security-incidents

---

**@maya.chen** [11:23 AM]
Hey team, we got flagged by the red team during the quarterly pentest. They found a way to bypass our path traversal protection.

**@david.kim** [11:24 AM]
oh no. what's the vector?

**@maya.chen** [11:25 AM]
URL encoding. They're using `%2e%2e` instead of `..` and our sanitization doesn't catch it.

Example payload:
```
/api/provenance/document/%2e%2e%2f%2e%2e%2fetc%2fpasswd
```

Our `hasPathTraversal` function only checks for literal `..` sequences.

**@sarah.liu** [11:26 AM]
yikes. I thought we had that covered in the security service

**@maya.chen** [11:27 AM]
Same issue exists in both:
- `src/core/security.js` - the `sanitisePath` function
- `services/security/service.js` - the `hasPathTraversal` check

Neither decodes URL-encoded characters before checking for traversal patterns.

**@david.kim** [11:28 AM]
there's more. I was reviewing the origin allowlist check and noticed it's case-sensitive

```javascript
// This won't match:
isAllowedOrigin("Example.COM", ["example.com"])
// Returns false because no toLowerCase()
```

**@maya.chen** [11:29 AM]
:facepalm: that explains the intermittent CORS failures on the partner portal

**@alex.thompson** [11:30 AM]
Adding to the pile - the risk scoring in the security service is using additive weights instead of multiplicative

If someone has both geo anomaly and time anomaly, we're adding `+20` and `+15` to the base score instead of multiplying by `1.5` and `1.3`

The difference:
- Current (additive): base=50 + 20 + 15 = 85
- Expected (multiplicative): base=50 * 1.5 * 1.3 = 97.5

We're underestimating risk for multi-factor anomalies

**@sarah.liu** [11:32 AM]
Is this why the fraud team was complaining about missed detections?

**@alex.thompson** [11:33 AM]
Probably. Let me check the test failures...

```
Running security tests...
security.service.test.js:
  - hasPathTraversal detects encoded traversal: FAIL
  - riskScore multiplies anomaly factors: FAIL

security.test.js:
  - sanitisePath handles URL encoding: FAIL
  - isAllowedOrigin is case insensitive: FAIL
  - validateToken checks scope: FAIL
```

**@david.kim** [11:34 AM]
wait there's a scope validation issue too?

**@alex.thompson** [11:35 AM]
Yeah, the token validation in core/security.js doesn't actually verify that the token's scope matches the required scope. It just checks if the token exists and hasn't expired.

```javascript
// Current behavior
validateToken(token, 'admin:write')
// Returns valid=true even if token only has 'read' scope
```

**@maya.chen** [11:36 AM]
That's a privilege escalation vector. Any authenticated user can access admin endpoints.

**@sarah.liu** [11:37 AM]
How many tests are failing because of these issues?

**@alex.thompson** [11:38 AM]
Checking the hyper-matrix results:
```
Security-related failures in hyper-matrix:
- hyper-matrix-00500 through hyper-matrix-00600: path sanitization
- hyper-matrix-04000 through hyper-matrix-04200: token scope validation
- service-mesh-matrix security scenarios: ~300 failures
```

**@maya.chen** [11:39 AM]
Let's prioritize:
1. Path traversal (critical - remote file access)
2. Token scope (high - privilege escalation)
3. Origin case sensitivity (medium - CORS bypass)
4. Risk scoring weights (medium - detection accuracy)

**@david.kim** [11:40 AM]
I'll start on the path traversal. Need to add `decodeURIComponent` before the traversal check.

**@alex.thompson** [11:41 AM]
I'll look at the token scope validation. The `validateToken` function needs to actually compare `token.scope` against the required scope parameter.

**@sarah.liu** [11:42 AM]
Created ticket SEC-2024-0892 to track all four issues

**@maya.chen** [11:43 AM]
Thanks everyone. Let's get these fixed before the audit next week.

---

**Thread reactions**: :fire: 4, :eyes: 6, :rotating_light: 3
