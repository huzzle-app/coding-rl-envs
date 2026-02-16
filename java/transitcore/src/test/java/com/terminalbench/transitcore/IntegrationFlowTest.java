package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class IntegrationFlowTest {
    @Test
    void dispatchRiskComplianceFlow() {
        DispatchPlanner planner = new DispatchPlanner();
        CapacityBalancer balancer = new CapacityBalancer();
        ComplianceLedger compliance = new ComplianceLedger();
        WorkflowOrchestrator workflow = new WorkflowOrchestrator();

        String route = planner.chooseRoute(Map.of("north", 18, "west", 21));
        int admitted = balancer.rebalance(12, 8, 3);

        assertEquals("north", route);
        assertEquals(8, admitted);
        assertTrue(compliance.overrideAllowed("committee approved expedited transit", 2, 45));
        assertTrue(workflow.transitionAllowed("capacity_checked", "dispatched"));
    }

    @Test
    void routeSelectionWithHubCongestion() {
        DispatchPlanner planner = new DispatchPlanner();
        RoutingHeuristics heuristics = new RoutingHeuristics();

        // Pick shortest route, then least congested hub
        String route = planner.chooseRoute(Map.of("express", 12, "local", 28, "scenic", 35));
        assertEquals("express", route);

        String hub = heuristics.selectHub(Map.of("central", 0.72, "east", 0.31, "west", 0.45));
        assertEquals("east", hub);

        // Combined: fast route to uncongested hub
        String combinedHub = heuristics.selectHub(Map.of(
            route + "-hub-a", 0.6,
            route + "-hub-b", 0.15,
            "fallback", 0.9
        ));
        assertEquals(route + "-hub-b", combinedHub);
    }

    @Test
    void capacityShedThrottleCycle() {
        CapacityBalancer balancer = new CapacityBalancer();
        QueueGovernor governor = new QueueGovernor();

        // At exactly the hard limit, shedding should trigger
        assertTrue(balancer.shedRequired(10, 10));

        // Governor policy with exactly-at-limit inflight+depth should throttle
        var policy = new QueueGovernor.QueuePolicy(20, false);
        assertTrue(governor.shouldThrottle(12, 8, policy));

        // Combined: shed triggers → governor should also agree to throttle
        boolean shouldShed = balancer.shedRequired(15, 15);
        assertTrue(shouldShed);
        assertTrue(governor.shouldThrottle(15, 5, new QueueGovernor.QueuePolicy(20, false)));
    }

    @Test
    void escalationBypassCompliance() {
        PolicyEngine engine = new PolicyEngine();
        ComplianceLedger ledger = new ComplianceLedger();

        // Severity 8 + impact > 10 should reach level 4 (enough for bypass)
        int level = engine.escalationLevel(8, 11, false);
        assertEquals(4, level);

        // Level 4 with proper approvals should allow bypass
        assertTrue(engine.bypassQueueAllowed(level, 2, 20));

        // Compliance override must also agree
        assertTrue(ledger.overrideAllowed("approved emergency override", 2, 90));
    }

    @Test
    void retryCircuitResilience() {
        RetryBudget budget = new RetryBudget();
        ResilienceReplay replay = new ResilienceReplay();

        // Attempt 1 backoff should be base (2^0 = 1)
        assertEquals(100, budget.backoffMs(1, 100));

        // At max attempts, should not retry
        assertFalse(budget.shouldRetry(3, 3, false));

        // Circuit at exactly 5 failures should be open
        assertTrue(replay.circuitOpen(5));

        // With circuit open, retry should be blocked regardless of attempt count
        assertFalse(budget.shouldRetry(1, 5, replay.circuitOpen(5)));
    }

    @Test
    void slaBreachSeverityWorkflow() {
        SlaModel sla = new SlaModel();
        WorkflowOrchestrator workflow = new WorkflowOrchestrator();

        // At exact boundary, should NOT be breach risk
        assertFalse(sla.breachRisk(970, 1000, 30));

        // Exactly 300s over should still be "minor"
        assertEquals("minor", sla.breachSeverity(1300, 1000));

        // Workflow events should map to correct states
        assertEquals("validated", workflow.nextStateFor("validate"));
        assertEquals("capacity_checked", workflow.nextStateFor("capacity_ok"));
    }

    @Test
    void watermarkAuditStatistics() {
        WatermarkWindow window = new WatermarkWindow();
        AuditTrail trail = new AuditTrail();
        StatisticsReducer stats = new StatisticsReducer();

        // At exact tolerance boundary, should accept
        assertTrue(window.accept(100, 105, 5));

        // Equal consecutive elements are NOT strictly ordered
        assertFalse(trail.ordered(List.of(5L, 10L, 10L, 15L)));

        // Percentile of single-element array should return that element
        assertEquals(42.0, stats.percentile(new double[]{42.0}, 0.5));
    }

    @Test
    void tokenFreshPolicyBypass() {
        SecurityPolicy security = new SecurityPolicy();
        PolicyEngine engine = new PolicyEngine();

        // Token at exact expiry should still be fresh
        assertTrue(security.tokenFresh(1000, 500, 1500));

        // Level 4 should allow bypass with sufficient approvals and reason
        assertTrue(engine.bypassQueueAllowed(4, 2, 20));

        // Combined: fresh token + bypass allowed means action proceeds
        boolean tokenOk = security.tokenFresh(2000, 3600, 5600);
        boolean bypassOk = engine.bypassQueueAllowed(4, 3, 25);
        assertTrue(tokenOk && bypassOk);
    }

    @Test
    void fingerprintHashChain() {
        AuditTrail trail = new AuditTrail();

        // Fingerprint should produce lowercase output
        String fp = trail.fingerprint("TENANT-A", "TRACE-42", "Dispatch.Accepted");
        assertEquals("tenant-a:trace-42:dispatch.accepted", fp);

        // Hash chain with multiplier 31: appendHash(prev, payload) = (prev * 31 + charSum) % 1_000_000_007
        // "abc": a=97, b=98, c=99 → sum=294
        long h1 = trail.appendHash(0, "abc");
        assertEquals(294L, h1);

        // "def": d=100, e=101, f=102 → sum=303
        // h2 = (294 * 31 + 303) % MOD = 9114 + 303 = 9417
        long h2 = trail.appendHash(h1, "def");
        assertEquals(9417L, h2);

        // Third link: "ghi": g=103, h=104, i=105 → sum=312
        // h3 = (9417 * 31 + 312) % MOD = 291927 + 312 = 292239
        long h3 = trail.appendHash(h2, "ghi");
        assertEquals(292239L, h3);
    }

    @Test
    void lagWatermarkAcceptance() {
        WatermarkWindow window = new WatermarkWindow();

        // When processedTs is ahead of nowTs, lag should be 0 (not negative)
        assertEquals(0, window.lagSeconds(100, 200));
        assertEquals(0, window.lagSeconds(50, 300));

        // Positive lag is normal
        assertEquals(50, window.lagSeconds(200, 150));

        // Accept at exact tolerance boundary
        assertTrue(window.accept(95, 100, 5));
    }

    @Test
    void churnRateHubSelection() {
        RoutingHeuristics heuristics = new RoutingHeuristics();

        // Churn rate with new keys: new keys count in both numerator and denominator
        double churn = heuristics.churnRate(
            Map.of("job-1", "route-a"),
            Map.of("job-1", "route-a", "job-2", "route-b", "job-3", "route-c")
        );
        // 0 changed + 2 new = 2 changed, 1 existing + 2 new = 3 total → 2/3
        assertEquals(2.0 / 3.0, churn, 1e-9);

        // Hub selection picks least congested
        String hub = heuristics.selectHub(Map.of("north", 0.85, "south", 0.15, "east", 0.50));
        assertEquals("south", hub);
    }

    @Test
    void replayDeltaInflightTracking() {
        ResilienceReplay replay = new ResilienceReplay();
        CapacityBalancer balancer = new CapacityBalancer();

        // Replay with distinct inflight and backlog deltas
        var events = List.of(
            new ResilienceReplay.ReplayEvent(11, "evt-1", 5, 2)
        );
        var snap = replay.replay(10, 3, 10, events);

        // inflight should increase by inflightDelta (5), not backlogDelta (2)
        assertEquals(15, snap.inflight());
        // backlog should increase by backlogDelta (2), not inflightDelta (5)
        assertEquals(5, snap.backlog());

        // Shed at exactly the inflight limit
        assertTrue(balancer.shedRequired(15, 15));
    }

    @Test
    void endToEndDraftToReport() {
        WorkflowOrchestrator workflow = new WorkflowOrchestrator();

        // Full lifecycle: drafted → validated → capacity_checked → dispatched → reported
        String state = "drafted";

        // validate event → "validated"
        String next = workflow.nextStateFor("validate");
        assertEquals("validated", next);
        assertTrue(workflow.transitionAllowed(state, next));
        state = next;

        // capacity_ok event → "capacity_checked"
        next = workflow.nextStateFor("capacity_ok");
        assertEquals("capacity_checked", next);
        assertTrue(workflow.transitionAllowed(state, next));
        state = next;

        // dispatch event → "dispatched"
        next = workflow.nextStateFor("dispatch");
        assertEquals("dispatched", next);
        assertTrue(workflow.transitionAllowed(state, next));
        state = next;

        // publish event → "reported"
        next = workflow.nextStateFor("publish");
        assertEquals("reported", next);
        assertTrue(workflow.transitionAllowed(state, next));
    }

    @Test
    void queueGovernorShedRebalance() {
        QueueGovernor governor = new QueueGovernor();
        CapacityBalancer balancer = new CapacityBalancer();

        // At burst=6, should trigger high-severity policy (maxInflight=8)
        var highPolicy = governor.nextPolicy(6);
        assertEquals(8, highPolicy.maxInflight());
        assertTrue(highPolicy.dropOldest());

        // At burst=3, should trigger medium policy (maxInflight=16)
        var medPolicy = governor.nextPolicy(3);
        assertEquals(16, medPolicy.maxInflight());

        // Rebalance should subtract reserve floor
        int admitted = balancer.rebalance(10, 8, 3);
        assertEquals(7, admitted);
    }

    @Test
    void penaltyScoreRetryDecision() {
        RetryBudget budget = new RetryBudget();

        // Penalty score: retries * 2 + latencyMs / 250
        int penalty = budget.penaltyScore(2, 500);
        assertEquals(6, penalty);

        // At exact max attempts, should not retry
        assertFalse(budget.shouldRetry(4, 4, false));

        // High penalty with exhausted retries means full stop
        int highPenalty = budget.penaltyScore(5, 2000);
        assertEquals(18, highPenalty);
        assertFalse(budget.shouldRetry(5, 5, false));
    }

    @Test
    void complianceRetentionAudit() {
        ComplianceLedger ledger = new ComplianceLedger();
        AuditTrail trail = new AuditTrail();

        // Exactly 12 characters should be allowed
        assertTrue(ledger.overrideAllowed("twelve_chars", 2, 60));

        // Exactly 30 days should be "hot"
        assertEquals("hot", ledger.retentionBucket(30));

        // Exactly 365 days should be "warm"
        assertEquals("warm", ledger.retentionBucket(365));

        // Fingerprint should be case-insensitive
        String fp1 = trail.fingerprint("TENANT", "TRACE", "EVENT");
        String fp2 = trail.fingerprint("tenant", "trace", "event");
        assertEquals(fp1, fp2);
    }
}
