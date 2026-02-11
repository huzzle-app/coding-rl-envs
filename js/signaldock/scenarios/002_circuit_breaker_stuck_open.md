# Scenario 002: External Services Never Recovering After Transient Failures

## Type: Slack Thread (Engineering Channel)

## Channel: #signaldock-oncall

---

**@marina.chen** [14:22]
Anyone else seeing issues with the weather API integration? It went down briefly at 14:00 and now ALL dispatch requests that need weather checks are failing.

**@devops-bot** [14:22]
:alert: Circuit breaker for `weather-service` has been OPEN for 22 minutes.

**@james.wright** [14:25]
I checked the weather API directly - it's been healthy since 14:05. The circuit breaker should have transitioned to half-open by now and started allowing test requests through.

**@marina.chen** [14:27]
Looking at the logs... I see the breaker DID transition to `half_open` state at 14:20. But requests are still being rejected?

```
14:20:01 [CB] State transition: OPEN -> HALF_OPEN
14:20:02 [CB] Request denied - circuit open
14:20:02 [CB] Request denied - circuit open
14:20:03 [CB] Request denied - circuit open
```

That doesn't make sense. Half-open should allow requests through.

**@james.wright** [14:30]
Let me check the `isAllowed()` method in the CircuitBreaker class. Something's wrong with the state check.

**@marina.chen** [14:32]
We've had 3 similar incidents this month. Every time there's a brief external service hiccup, the circuit breaker opens (correct) but then NEVER allows recovery traffic through. We have to manually reset every breaker.

**@james.wright** [14:35]
Found it. The `isAllowed()` function is checking the state but I think there's a logic issue. It transitions to HALF_OPEN correctly, but then rejects requests anyway.

Can someone look at `src/core/resilience.js`?

**@devops-bot** [14:40]
:rotating_light: Manual intervention required. CircuitBreaker reset triggered by operator.

---

## Symptoms

1. Circuit breaker correctly opens after failure threshold is reached
2. After recovery timeout, breaker transitions to HALF_OPEN
3. Despite being in HALF_OPEN state, all requests are still denied
4. No test requests ever succeed, so breaker never closes
5. Manual reset is the only recovery path

## Impact

- 100% failure rate for any external service that has a brief outage
- Cascading failures across dependent dispatch operations
- Manual operator intervention required every time
