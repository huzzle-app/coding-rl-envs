package com.terminalbench.transitcore;

import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.TestFactory;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.junit.jupiter.api.DynamicTest.dynamicTest;

/**
 * Stress tests for TransitCore - generates 300+ test cases across all modules.
 */
public class StressTest {

    private final DispatchPlanner dispatchPlanner = new DispatchPlanner();
    private final CapacityBalancer capacityBalancer = new CapacityBalancer();
    private final RoutingHeuristics routingHeuristics = new RoutingHeuristics();
    private final PolicyEngine policyEngine = new PolicyEngine();
    private final SecurityPolicy securityPolicy = new SecurityPolicy();
    private final ResilienceReplay resilienceReplay = new ResilienceReplay();
    private final QueueGovernor queueGovernor = new QueueGovernor();
    private final SlaModel slaModel = new SlaModel();
    private final ComplianceLedger complianceLedger = new ComplianceLedger();
    private final WatermarkWindow watermarkWindow = new WatermarkWindow();
    private final RetryBudget retryBudget = new RetryBudget();
    private final AuditTrail auditTrail = new AuditTrail();
    private final StatisticsReducer statisticsReducer = new StatisticsReducer();
    private final WorkflowOrchestrator workflowOrchestrator = new WorkflowOrchestrator();

    @TestFactory
    Collection<DynamicTest> dispatchPlannerChooseRouteTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (int i = 0; i < 20; i++) {
            final int idx = i;
            tests.add(dynamicTest("chooseRoute_scenario_" + i, () -> {
                Map<String, Integer> routes = Map.of(
                    "route_a", 10 + idx,
                    "route_b", 20 + idx,
                    "route_c", 5 + idx
                );
                String result = dispatchPlanner.chooseRoute(routes);
                // Should pick route with lowest travel time
                assertEquals("route_c", result, "Should pick fastest route");
            }));
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> dispatchPlannerPriorityTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (int severity = 1; severity <= 10; severity++) {
            for (int sla : new int[]{10, 15, 20, 30, 45, 60}) {
                final int sev = severity;
                final int slaMin = sla;
                tests.add(dynamicTest("assignPriority_sev" + sev + "_sla" + slaMin, () -> {
                    int priority = dispatchPlanner.assignPriority(sev, slaMin);
                    assertTrue(priority >= 35 && priority <= 100, "Priority should be in valid range");
                    // High severity should have higher base
                    if (sev >= 8) {
                        assertTrue(priority >= 90, "Severity 8+ should have base 90+");
                    }
                }));
            }
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> capacityBalancerTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (int available = 0; available <= 20; available += 5) {
            for (int demand = 0; demand <= 15; demand += 3) {
                for (int reserve = 0; reserve <= 5; reserve += 2) {
                    final int avail = available;
                    final int dem = demand;
                    final int res = reserve;
                    tests.add(dynamicTest("rebalance_" + avail + "_" + dem + "_" + res, () -> {
                        int result = capacityBalancer.rebalance(avail, dem, res);
                        int safeAvailable = Math.max(0, avail - res);
                        int expected = Math.min(Math.max(dem, 0), safeAvailable);
                        assertEquals(expected, result, "Rebalance should respect reserve floor");
                    }));
                }
            }
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> capacityBalancerShedTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (int inFlight = 0; inFlight <= 20; inFlight++) {
            for (int limit : new int[]{5, 10, 15}) {
                final int flight = inFlight;
                final int lim = limit;
                tests.add(dynamicTest("shedRequired_" + flight + "_" + lim, () -> {
                    boolean result = capacityBalancer.shedRequired(flight, lim);
                    boolean expected = flight >= lim;
                    assertEquals(expected, result, "Shed should trigger at or above limit");
                }));
            }
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> routingHeuristicsTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (int i = 0; i < 15; i++) {
            final int idx = i;
            tests.add(dynamicTest("selectHub_scenario_" + i, () -> {
                Map<String, Double> congestion = Map.of(
                    "hub_alpha", 0.3 + idx * 0.01,
                    "hub_beta", 0.5 + idx * 0.01,
                    "hub_gamma", 0.2 + idx * 0.01
                );
                String result = routingHeuristics.selectHub(congestion);
                // Should pick hub with lowest congestion
                assertEquals("hub_gamma", result, "Should pick least congested hub");
            }));
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> policyEngineEscalationTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (int severity = 1; severity <= 10; severity++) {
            for (int impacted = 0; impacted <= 15; impacted += 5) {
                for (boolean regulatory : new boolean[]{true, false}) {
                    final int sev = severity;
                    final int imp = impacted;
                    final boolean reg = regulatory;
                    tests.add(dynamicTest("escalation_" + sev + "_" + imp + "_" + reg, () -> {
                        int level = policyEngine.escalationLevel(sev, imp, reg);
                        assertTrue(level >= 1 && level <= 5, "Level should be 1-5");
                        // High severity should have higher base
                        if (sev >= 8) {
                            assertTrue(level >= 3, "Severity 8+ should have base level 3");
                        }
                    }));
                }
            }
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> policyEngineBypassTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (int level = 1; level <= 5; level++) {
            for (int approvals = 0; approvals <= 3; approvals++) {
                for (int reasonLen : new int[]{5, 12, 20}) {
                    final int lev = level;
                    final int app = approvals;
                    final int len = reasonLen;
                    tests.add(dynamicTest("bypass_" + lev + "_" + app + "_" + len, () -> {
                        boolean result = policyEngine.bypassQueueAllowed(lev, app, len);
                        boolean expected = lev >= 4 && app >= 2 && len >= 12;
                        assertEquals(expected, result, "Bypass rules should match");
                    }));
                }
            }
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> securityPolicyTokenTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (long issued = 1000; issued <= 2000; issued += 200) {
            for (long ttl = 100; ttl <= 500; ttl += 100) {
                for (long now = 1000; now <= 2500; now += 300) {
                    final long iss = issued;
                    final long t = ttl;
                    final long n = now;
                    tests.add(dynamicTest("tokenFresh_" + iss + "_" + t + "_" + n, () -> {
                        boolean result = securityPolicy.tokenFresh(iss, t, n);
                        boolean expected = n <= iss + t;
                        assertEquals(expected, result, "Token freshness should match");
                    }));
                }
            }
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> resilienceBackoffTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (int attempt = 1; attempt <= 8; attempt++) {
            for (int baseMs : new int[]{10, 50, 100}) {
                final int att = attempt;
                final int base = baseMs;
                tests.add(dynamicTest("backoff_" + att + "_" + base, () -> {
                    int result = resilienceReplay.retryBackoffMs(att, base);
                    int power = Math.min(Math.max(att - 1, 0), 6);
                    int expected = base * (1 << power);
                    assertEquals(expected, result, "Backoff should follow exponential pattern");
                }));
            }
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> resilienceCircuitTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (int failures = 0; failures <= 10; failures++) {
            final int fail = failures;
            tests.add(dynamicTest("circuitOpen_" + fail, () -> {
                boolean result = resilienceReplay.circuitOpen(fail);
                boolean expected = fail >= 5;
                assertEquals(expected, result, "Circuit should open at 5+ failures");
            }));
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> queueGovernorPolicyTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (int burst = 0; burst <= 10; burst++) {
            final int b = burst;
            tests.add(dynamicTest("nextPolicy_burst_" + b, () -> {
                var policy = queueGovernor.nextPolicy(b);
                if (b >= 6) {
                    assertEquals(8, policy.maxInflight(), "High burst should have limit 8");
                    assertTrue(policy.dropOldest(), "High burst should drop oldest");
                } else if (b >= 3) {
                    assertEquals(16, policy.maxInflight(), "Medium burst should have limit 16");
                } else {
                    assertEquals(32, policy.maxInflight(), "Low burst should have limit 32");
                }
            }));
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> queueGovernorThrottleTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (int inflight = 0; inflight <= 10; inflight++) {
            for (int depth = 0; depth <= 10; depth++) {
                final int inf = inflight;
                final int dep = depth;
                tests.add(dynamicTest("throttle_" + inf + "_" + dep, () -> {
                    var policy = new QueueGovernor.QueuePolicy(15, false);
                    boolean result = queueGovernor.shouldThrottle(inf, dep, policy);
                    boolean expected = inf + dep >= 15;
                    assertEquals(expected, result, "Throttle should trigger at policy limit");
                }));
            }
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> slaModelBreachRiskTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (long eta = 100; eta <= 500; eta += 50) {
            for (long sla = 200; sla <= 400; sla += 100) {
                for (long buffer = 10; buffer <= 50; buffer += 20) {
                    final long e = eta;
                    final long s = sla;
                    final long b = buffer;
                    tests.add(dynamicTest("breachRisk_" + e + "_" + s + "_" + b, () -> {
                        boolean result = slaModel.breachRisk(e, s, b);
                        boolean expected = e > s - b;
                        assertEquals(expected, result, "Breach risk should match");
                    }));
                }
            }
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> slaModelSeverityTests() {
        List<DynamicTest> tests = new ArrayList<>();
        long[] deltas = {-100, 0, 150, 300, 600, 900, 1200};
        for (long delta : deltas) {
            final long d = delta;
            tests.add(dynamicTest("breachSeverity_delta_" + d, () -> {
                long eta = 1000 + d;
                long sla = 1000;
                String result = slaModel.breachSeverity(eta, sla);
                if (d <= 0) {
                    assertEquals("none", result);
                } else if (d <= 300) {
                    assertEquals("minor", result);
                } else if (d <= 900) {
                    assertEquals("major", result);
                } else {
                    assertEquals("critical", result);
                }
            }));
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> complianceLedgerOverrideTests() {
        List<DynamicTest> tests = new ArrayList<>();
        String[] reasons = {"short", "twelve_chars", "this is a longer reason"};
        for (String reason : reasons) {
            for (int approvals = 0; approvals <= 3; approvals++) {
                for (int ttl : new int[]{60, 120, 180}) {
                    final String r = reason;
                    final int a = approvals;
                    final int t = ttl;
                    tests.add(dynamicTest("override_" + r.length() + "_" + a + "_" + t, () -> {
                        boolean result = complianceLedger.overrideAllowed(r, a, t);
                        boolean expected = r.trim().length() >= 12 && a >= 2 && t <= 120;
                        assertEquals(expected, result, "Override rules should match");
                    }));
                }
            }
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> complianceLedgerRetentionTests() {
        List<DynamicTest> tests = new ArrayList<>();
        long[] ages = {1, 15, 30, 31, 100, 365, 366, 500};
        for (long age : ages) {
            final long a = age;
            tests.add(dynamicTest("retention_age_" + a, () -> {
                String result = complianceLedger.retentionBucket(a);
                if (a <= 30) {
                    assertEquals("hot", result);
                } else if (a <= 365) {
                    assertEquals("warm", result);
                } else {
                    assertEquals("cold", result);
                }
            }));
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> watermarkAcceptTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (long eventTs = 100; eventTs <= 200; eventTs += 20) {
            for (long watermark = 100; watermark <= 200; watermark += 25) {
                for (long tolerance = 0; tolerance <= 50; tolerance += 25) {
                    final long e = eventTs;
                    final long w = watermark;
                    final long t = tolerance;
                    tests.add(dynamicTest("accept_" + e + "_" + w + "_" + t, () -> {
                        boolean result = watermarkWindow.accept(e, w, t);
                        boolean expected = e + t >= w;
                        assertEquals(expected, result, "Accept should match watermark rules");
                    }));
                }
            }
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> retryBudgetBackoffTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (int attempt = 1; attempt <= 7; attempt++) {
            for (int baseMs : new int[]{20, 40, 80}) {
                final int a = attempt;
                final int b = baseMs;
                tests.add(dynamicTest("retryBackoff_" + a + "_" + b, () -> {
                    int result = retryBudget.backoffMs(a, b);
                    int power = Math.min(Math.max(a - 1, 0), 6);
                    int expected = b * (1 << power);
                    assertEquals(expected, result, "Backoff should be exponential");
                }));
            }
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> retryBudgetShouldRetryTests() {
        List<DynamicTest> tests = new ArrayList<>();
        for (int attempt = 0; attempt <= 5; attempt++) {
            for (int max = 3; max <= 5; max++) {
                for (boolean open : new boolean[]{true, false}) {
                    final int a = attempt;
                    final int m = max;
                    final boolean o = open;
                    tests.add(dynamicTest("shouldRetry_" + a + "_" + m + "_" + o, () -> {
                        boolean result = retryBudget.shouldRetry(a, m, o);
                        boolean expected = !o && a < m;
                        assertEquals(expected, result, "Retry decision should match");
                    }));
                }
            }
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> auditTrailOrderedTests() {
        List<DynamicTest> tests = new ArrayList<>();
        List<List<Long>> sequences = List.of(
            List.of(1L, 2L, 3L),
            List.of(1L, 3L, 2L),
            List.of(1L, 1L, 2L),
            List.of(5L, 10L, 15L, 20L),
            List.of(1L, 2L, 2L, 3L)
        );
        for (int i = 0; i < sequences.size(); i++) {
            final List<Long> seq = sequences.get(i);
            final int idx = i;
            tests.add(dynamicTest("ordered_seq_" + idx, () -> {
                boolean result = auditTrail.ordered(seq);
                // Check if strictly increasing
                boolean expected = true;
                for (int j = 1; j < seq.size(); j++) {
                    if (seq.get(j) <= seq.get(j - 1)) {
                        expected = false;
                        break;
                    }
                }
                assertEquals(expected, result, "Ordered check should match");
            }));
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> workflowTransitionTests() {
        List<DynamicTest> tests = new ArrayList<>();
        String[] states = {"drafted", "validated", "capacity_checked", "dispatched", "reported", "canceled"};
        for (String from : states) {
            for (String to : states) {
                final String f = from;
                final String t = to;
                tests.add(dynamicTest("transition_" + f + "_to_" + t, () -> {
                    boolean result = workflowOrchestrator.transitionAllowed(f, t);
                    // Verify against known valid transitions
                    boolean expected = switch (f) {
                        case "drafted" -> t.equals("validated") || t.equals("canceled");
                        case "validated" -> t.equals("capacity_checked") || t.equals("canceled");
                        case "capacity_checked" -> t.equals("dispatched") || t.equals("canceled");
                        case "dispatched" -> t.equals("reported");
                        default -> false;
                    };
                    assertEquals(expected, result, "Transition should match workflow graph");
                }));
            }
        }
        return tests;
    }

    @TestFactory
    Collection<DynamicTest> workflowNextStateTests() {
        List<DynamicTest> tests = new ArrayList<>();
        Map<String, String> eventToState = Map.of(
            "validate", "validated",
            "capacity_ok", "capacity_checked",
            "dispatch", "dispatched",
            "publish", "reported",
            "cancel", "canceled",
            "unknown", "drafted"
        );
        for (var entry : eventToState.entrySet()) {
            final String event = entry.getKey();
            final String expectedState = entry.getValue();
            tests.add(dynamicTest("nextState_" + event, () -> {
                String result = workflowOrchestrator.nextStateFor(event);
                assertEquals(expectedState, result, "Next state should match event");
            }));
        }
        return tests;
    }
}
