# Scenario 02: Circuit Breaker Fails to Trip

## Slack Discussion Thread: #ops-resilience

---

**@dave.kumar** - 2026-01-18 14:23 UTC

Hey team, we're seeing strange behavior in the ground station failover system. The circuit breaker for the EU-WEST relay isn't opening when it should.

**@lisa.wong** - 2026-01-18 14:25 UTC

What's the failure threshold set to?

**@dave.kumar** - 2026-01-18 14:26 UTC

5 failures. But we're hitting exactly 5 consecutive failures and the breaker stays closed. Traffic keeps routing through the degraded node.

**@alex.petrov** - 2026-01-18 14:28 UTC

Wait, you're saying it trips at 6 but not 5? That sounds like an off-by-one.

**@dave.kumar** - 2026-01-18 14:30 UTC

Exactly. When we configure threshold=5, it requires 6 failures to open. Our runbook says "5 failures triggers failover" but we're seeing a 6th failure each time before the switch.

**@lisa.wong** - 2026-01-18 14:32 UTC

That extra failure is causing real problems. The 6th request is getting a timeout instead of being routed to backup.

**@james.chen** - 2026-01-18 14:35 UTC

I'm seeing this in the test failures too:

```
tests/unit/resilience_test.py::ResilienceTest::test_circuit_breaker_threshold
tests/stress/service_mesh_matrix_test.py::test_failover_boundary_*
```

The circuit breaker test expects the state to be "open" after exactly threshold failures, but it's still "closed".

**@dave.kumar** - 2026-01-18 14:38 UTC

Can someone check `aetherops/resilience.py`? The `CircuitBreaker.record_failure()` method is where the threshold check happens.

**@alex.petrov** - 2026-01-18 14:40 UTC

On it. Looks like a comparison operator issue. Should be straightforward to fix but someone needs to verify the boundary condition semantics.

---

## Related Incidents

- INC-2026-0098: EU-WEST ground station latency spike (6 affected commands)
- INC-2026-0099: Telemetry gap during failover delay
- Customer ticket: ORB-DYNAMICS-5521
