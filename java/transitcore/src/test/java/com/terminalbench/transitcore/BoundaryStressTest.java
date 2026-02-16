package com.terminalbench.transitcore;

import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.TestFactory;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.junit.jupiter.api.DynamicTest.dynamicTest;

/**
 * Boundary stress tests for TransitCore - generates ~300 dynamic tests targeting
 * exact boundary values for every bug category including TRN031-TRN035.
 */
public class BoundaryStressTest {

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

    // ======================================================================
    // 1. Fingerprint case sensitivity (TRN031) ~10 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> fingerprintCaseSensitivityTests() {
        List<DynamicTest> tests = new ArrayList<>();
        String[][] cases = {
            {"TENANT", "TRACE", "EVENT", "tenant:trace:event"},
            {"Tenant-A", "Trace-7", "Dispatch.Accepted", "tenant-a:trace-7:dispatch.accepted"},
            {"ABC", "DEF", "GHI", "abc:def:ghi"},
            {"mixedCase", "TraceID", "Type", "mixedcase:traceid:type"},
            {"ALL-UPPER", "ALL-UPPER", "ALL-UPPER", "all-upper:all-upper:all-upper"},
            {"all-lower", "all-lower", "all-lower", "all-lower:all-lower:all-lower"},
            {"CamelCase", "SnakeCase", "MACRO_CASE", "camelcase:snakecase:macro_case"},
            {" Leading", "Trailing ", " Both ", "leading:trailing:both"},
            {"X", "Y", "Z", "x:y:z"},
            {"MiXeD123", "tRaCe-99", "EvEnT.OK", "mixed123:trace-99:event.ok"},
        };
        for (String[] c : cases) {
            tests.add(dynamicTest("fingerprint_case_" + c[0] + "_" + c[1], () -> {
                String result = auditTrail.fingerprint(c[0], c[1], c[2]);
                assertEquals(c[3], result, "Fingerprint should be lowercased and trimmed");
            }));
        }
        return tests;
    }

    // ======================================================================
    // 2. Hash value verification (TRN032) ~15 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> hashValueVerificationTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // Pre-computed expected hash values with correct multiplier (31)
        // appendHash(prev, payload) = (prev * 31 + charSum(payload)) % 1_000_000_007
        long[][] correctedCases = {
            {0, -1, 97},      // "a" sum=97
            {0, -2, 122},     // "z" sum=122
            {97, -3, 3105},   // 97*31+98=3105
            {0, -4, 294},     // "abc" sum=294
            {294, -5, 9417},  // 294*31+303=9417
            {9417, -6, 292239}, // 9417*31+312=292239
            {0, -7, 532},     // "hello" sum=532
            {532, -8, 17044}, // 532*31+552=17044
            {0, -9, 448},     // "test" sum=448
            {448, -10, 14298}, // 448*31+410=14298
            {0, -11, 131},    // "AB" sum=131
            {131, -12, 4196}, // 131*31+135=4196
            {0, -13, 49},     // "1" sum=49
            {49, -14, 1569},  // 49*31+50=1569
            {1569, -15, 48690}, // 1569*31+51=48690
        };
        String[] payloads = {"a", "z", "b", "abc", "def", "ghi", "hello", "world",
                             "test", "data", "AB", "CD", "1", "2", "3"};

        for (int i = 0; i < correctedCases.length; i++) {
            final long prev = correctedCases[i][0];
            final String payload = payloads[i];
            final long expected = correctedCases[i][2];
            tests.add(dynamicTest("hashChain_" + prev + "_" + payload, () -> {
                long result = auditTrail.appendHash(prev, payload);
                assertEquals(expected, result, "Hash with multiplier 31 for '" + payload + "' starting from " + prev);
            }));
        }
        return tests;
    }

    // ======================================================================
    // 3. Lag seconds edge cases (TRN033) ~15 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> lagSecondsEdgeCaseTests() {
        List<DynamicTest> tests = new ArrayList<>();
        long[][] cases = {
            // {nowTs, processedTs, expectedLag}
            {100, 200, 0},     // future: should be 0
            {50, 300, 0},      // far future: should be 0
            {0, 1, 0},         // barely future
            {100, 100, 0},     // equal: should be 0
            {200, 100, 100},   // normal lag
            {1000, 1, 999},    // large lag
            {500, 499, 1},     // minimal lag
            {Long.MAX_VALUE / 2, Long.MAX_VALUE / 2, 0}, // equal large
            {10, 0, 10},       // processed at epoch
            {0, 0, 0},         // both zero
            {1, 0, 1},         // just after epoch
            {1000, 900, 100},  // typical lag
            {5000, 4000, 1000}, // larger typical
            {100, 101, 0},     // one second future
            {999, 1000, 0},    // one second future
        };
        for (long[] c : cases) {
            tests.add(dynamicTest("lagSeconds_" + c[0] + "_" + c[1], () -> {
                long result = watermarkWindow.lagSeconds(c[0], c[1]);
                assertEquals(c[2], result, "Lag should be max(now-processed, 0)");
            }));
        }
        return tests;
    }

    // ======================================================================
    // 4. Churn rate denominator (TRN034) ~20 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> churnRateDenominatorTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // Test new keys increase total
        tests.add(dynamicTest("churn_allNew", () -> {
            double churn = routingHeuristics.churnRate(Map.of(), Map.of("a", "1", "b", "2"));
            assertEquals(1.0, churn, 1e-9); // 2 new / 2 total
        }));
        tests.add(dynamicTest("churn_oneNew", () -> {
            double churn = routingHeuristics.churnRate(Map.of("a", "1"), Map.of("a", "1", "b", "2"));
            assertEquals(0.5, churn, 1e-9); // 1 new / 2 total
        }));
        tests.add(dynamicTest("churn_twoNewOneExisting", () -> {
            double churn = routingHeuristics.churnRate(
                Map.of("a", "1"),
                Map.of("a", "1", "b", "2", "c", "3")
            );
            assertEquals(2.0 / 3.0, churn, 1e-9); // 2 new / 3 total
        }));
        tests.add(dynamicTest("churn_threeNewTwoExisting", () -> {
            double churn = routingHeuristics.churnRate(
                Map.of("x", "1", "y", "2"),
                Map.of("x", "1", "y", "2", "a", "1", "b", "2", "c", "3")
            );
            assertEquals(3.0 / 5.0, churn, 1e-9); // 3 new / 5 total
        }));
        tests.add(dynamicTest("churn_allRemoved", () -> {
            double churn = routingHeuristics.churnRate(Map.of("a", "1", "b", "2"), Map.of());
            assertEquals(1.0, churn, 1e-9); // 2 removed / 2 total
        }));
        tests.add(dynamicTest("churn_unchanged", () -> {
            double churn = routingHeuristics.churnRate(Map.of("a", "1"), Map.of("a", "1"));
            assertEquals(0.0, churn, 1e-9); // 0 changed / 1 total
        }));
        tests.add(dynamicTest("churn_allChanged", () -> {
            double churn = routingHeuristics.churnRate(Map.of("a", "1", "b", "2"), Map.of("a", "x", "b", "y"));
            assertEquals(1.0, churn, 1e-9); // 2 changed / 2 total
        }));
        tests.add(dynamicTest("churn_mixedOperations", () -> {
            double churn = routingHeuristics.churnRate(
                Map.of("a", "1", "b", "2", "c", "3"),
                Map.of("a", "1", "b", "x", "d", "4")
            );
            // b changed, c removed, d new → 3 changed / 4 total
            assertEquals(3.0 / 4.0, churn, 1e-9);
        }));
        tests.add(dynamicTest("churn_bothEmpty", () -> {
            double churn = routingHeuristics.churnRate(Map.of(), Map.of());
            assertEquals(0.0, churn, 1e-9);
        }));

        // Parametric tests with varying new key counts
        for (int newKeys = 1; newKeys <= 5; newKeys++) {
            final int nk = newKeys;
            tests.add(dynamicTest("churn_parametric_" + nk + "new_1existing", () -> {
                Map<String, String> prev = new HashMap<>();
                prev.put("existing", "val");
                Map<String, String> curr = new HashMap<>();
                curr.put("existing", "val");
                for (int j = 0; j < nk; j++) {
                    curr.put("new_" + j, "v" + j);
                }
                double churn = routingHeuristics.churnRate(prev, curr);
                assertEquals((double) nk / (1 + nk), churn, 1e-9);
            }));
        }

        // Tests where new keys plus changes both matter
        for (int existing = 1; existing <= 3; existing++) {
            for (int newKeys = 1; newKeys <= 3; newKeys++) {
                final int ex = existing;
                final int nk = newKeys;
                tests.add(dynamicTest("churn_grid_" + ex + "exist_" + nk + "new", () -> {
                    Map<String, String> prev = new HashMap<>();
                    Map<String, String> curr = new HashMap<>();
                    for (int j = 0; j < ex; j++) {
                        prev.put("k" + j, "v" + j);
                        curr.put("k" + j, "v" + j);
                    }
                    for (int j = 0; j < nk; j++) {
                        curr.put("new" + j, "n" + j);
                    }
                    double churn = routingHeuristics.churnRate(prev, curr);
                    assertEquals((double) nk / (ex + nk), churn, 1e-9);
                }));
            }
        }
        return tests;
    }

    // ======================================================================
    // 5. Replay delta ordering (TRN035) ~20 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> replayDeltaOrderingTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // Various inflight/backlog delta combos
        int[][] deltaCombos = {
            {5, 2}, {2, 5}, {10, 0}, {0, 10}, {1, 1},
            {3, 7}, {7, 3}, {100, 1}, {1, 100}, {0, 0},
        };
        for (int[] combo : deltaCombos) {
            final int iDelta = combo[0];
            final int bDelta = combo[1];
            tests.add(dynamicTest("replayDelta_single_" + iDelta + "_" + bDelta, () -> {
                var events = List.of(
                    new ResilienceReplay.ReplayEvent(11, "k1", iDelta, bDelta)
                );
                var snap = resilienceReplay.replay(10, 5, 10, events);
                assertEquals(10 + iDelta, snap.inflight(), "inflight should add inflightDelta");
                assertEquals(5 + bDelta, snap.backlog(), "backlog should add backlogDelta");
            }));
        }

        // Multi-event replay
        tests.add(dynamicTest("replayDelta_twoEvents", () -> {
            var events = List.of(
                new ResilienceReplay.ReplayEvent(11, "k1", 3, 1),
                new ResilienceReplay.ReplayEvent(12, "k2", 2, 4)
            );
            var snap = resilienceReplay.replay(0, 0, 10, events);
            assertEquals(5, snap.inflight());   // 0+3+2
            assertEquals(5, snap.backlog());    // 0+1+4
        }));

        tests.add(dynamicTest("replayDelta_threeEvents", () -> {
            var events = List.of(
                new ResilienceReplay.ReplayEvent(11, "k1", 10, 2),
                new ResilienceReplay.ReplayEvent(12, "k2", -3, 5),
                new ResilienceReplay.ReplayEvent(13, "k3", 1, -1)
            );
            var snap = resilienceReplay.replay(20, 10, 10, events);
            assertEquals(28, snap.inflight());  // 20+10-3+1
            assertEquals(16, snap.backlog());   // 10+2+5-1
        }));

        tests.add(dynamicTest("replayDelta_negativeDeltas", () -> {
            var events = List.of(
                new ResilienceReplay.ReplayEvent(11, "k1", -5, -3)
            );
            var snap = resilienceReplay.replay(20, 15, 10, events);
            assertEquals(15, snap.inflight());
            assertEquals(12, snap.backlog());
        }));

        tests.add(dynamicTest("replayDelta_asymmetric", () -> {
            var events = List.of(
                new ResilienceReplay.ReplayEvent(11, "k1", 100, 1)
            );
            var snap = resilienceReplay.replay(0, 0, 10, events);
            assertEquals(100, snap.inflight());
            assertEquals(1, snap.backlog());
        }));

        tests.add(dynamicTest("replayDelta_asymmetricReverse", () -> {
            var events = List.of(
                new ResilienceReplay.ReplayEvent(11, "k1", 1, 100)
            );
            var snap = resilienceReplay.replay(0, 0, 10, events);
            assertEquals(1, snap.inflight());
            assertEquals(100, snap.backlog());
        }));

        // Verify version is tracked correctly
        tests.add(dynamicTest("replayDelta_versionTracking", () -> {
            var events = List.of(
                new ResilienceReplay.ReplayEvent(15, "k1", 3, 2),
                new ResilienceReplay.ReplayEvent(20, "k2", 1, 4)
            );
            var snap = resilienceReplay.replay(0, 0, 10, events);
            assertEquals(20, snap.version());
            assertEquals(2, snap.applied());
        }));

        // Zero deltas should not change totals
        tests.add(dynamicTest("replayDelta_zeroBoth", () -> {
            var events = List.of(
                new ResilienceReplay.ReplayEvent(11, "k1", 0, 0)
            );
            var snap = resilienceReplay.replay(42, 17, 10, events);
            assertEquals(42, snap.inflight());
            assertEquals(17, snap.backlog());
            assertEquals(1, snap.applied());
        }));

        // Larger chain with mixed deltas
        tests.add(dynamicTest("replayDelta_longChain", () -> {
            var events = List.of(
                new ResilienceReplay.ReplayEvent(11, "a", 5, 1),
                new ResilienceReplay.ReplayEvent(12, "b", -2, 3),
                new ResilienceReplay.ReplayEvent(13, "c", 8, -4),
                new ResilienceReplay.ReplayEvent(14, "d", -1, 2)
            );
            var snap = resilienceReplay.replay(10, 10, 10, events);
            assertEquals(20, snap.inflight());  // 10+5-2+8-1
            assertEquals(12, snap.backlog());   // 10+1+3-4+2
        }));

        return tests;
    }

    // ======================================================================
    // 6. Dispatch route boundaries ~15 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> dispatchRouteBoundaryTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // Tied routes: should pick lexically first
        tests.add(dynamicTest("route_tied_ab", () -> {
            String result = dispatchPlanner.chooseRoute(Map.of("alpha", 10, "beta", 10));
            assertEquals("alpha", result);
        }));
        tests.add(dynamicTest("route_tied_three", () -> {
            String result = dispatchPlanner.chooseRoute(Map.of("c", 5, "a", 5, "b", 5));
            assertEquals("a", result);
        }));

        // Single route
        tests.add(dynamicTest("route_single", () -> {
            String result = dispatchPlanner.chooseRoute(Map.of("only", 99));
            assertEquals("only", result);
        }));

        // Clear winner at different positions
        for (int winner = 1; winner <= 5; winner++) {
            final int w = winner;
            tests.add(dynamicTest("route_winner_at_" + w, () -> {
                Map<String, Integer> routes = new HashMap<>();
                for (int i = 1; i <= 5; i++) {
                    routes.put("route_" + i, i == w ? 1 : 50);
                }
                String result = dispatchPlanner.chooseRoute(routes);
                assertEquals("route_" + w, result);
            }));
        }

        // Priority assignment boundaries
        tests.add(dynamicTest("priority_sev8_sla14", () -> {
            int p = dispatchPlanner.assignPriority(8, 14);
            assertEquals(100, p); // base 90 + boost 15 = 105 → clamped to 100
        }));
        tests.add(dynamicTest("priority_sev5_sla15", () -> {
            int p = dispatchPlanner.assignPriority(5, 15);
            assertEquals(73, p); // base 65 + boost 8 = 73
        }));
        tests.add(dynamicTest("priority_sev4_sla30", () -> {
            int p = dispatchPlanner.assignPriority(4, 30);
            assertEquals(35, p); // base 35 + boost 0 = 35
        }));
        tests.add(dynamicTest("priority_sev7_sla10", () -> {
            int p = dispatchPlanner.assignPriority(7, 10);
            assertEquals(80, p); // base 65 + boost 15 = 80
        }));
        tests.add(dynamicTest("priority_sev10_sla60", () -> {
            int p = dispatchPlanner.assignPriority(10, 60);
            assertEquals(90, p); // base 90 + boost 0 = 90
        }));

        return tests;
    }

    // ======================================================================
    // 7. Capacity reserve boundary (TRN003) ~20 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> capacityReserveBoundaryTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // Reserve floor should be subtracted from available
        int[][] cases = {
            // {available, demand, reserve, expected}
            {10, 5, 3, 5},   // safeAvail=7, min(5,7)=5
            {10, 8, 3, 7},   // safeAvail=7, min(8,7)=7
            {10, 10, 3, 7},  // safeAvail=7, min(10,7)=7
            {5, 5, 5, 0},    // safeAvail=0, min(5,0)=0
            {5, 3, 0, 3},    // safeAvail=5, min(3,5)=3
            {0, 5, 0, 0},    // safeAvail=0, min(5,0)=0
            {20, 15, 5, 15}, // safeAvail=15, min(15,15)=15
            {100, 50, 10, 50}, // safeAvail=90, min(50,90)=50
            {3, 10, 3, 0},   // safeAvail=0, min(10,0)=0
            {7, 4, 2, 4},    // safeAvail=5, min(4,5)=4
        };
        for (int[] c : cases) {
            tests.add(dynamicTest("reserve_" + c[0] + "_" + c[1] + "_" + c[2], () -> {
                int result = capacityBalancer.rebalance(c[0], c[1], c[2]);
                int safeAvailable = Math.max(0, c[0] - c[2]);
                int expected = Math.min(Math.max(c[1], 0), safeAvailable);
                assertEquals(expected, result);
            }));
        }

        // Exact reserve equals available
        tests.add(dynamicTest("reserve_equalsAvailable", () -> {
            assertEquals(0, capacityBalancer.rebalance(5, 10, 5));
        }));

        // Zero demand
        for (int reserve = 0; reserve <= 5; reserve++) {
            final int r = reserve;
            tests.add(dynamicTest("reserve_zeroDemand_r" + r, () -> {
                assertEquals(0, capacityBalancer.rebalance(10, 0, r));
            }));
        }

        // Shed boundary tests
        tests.add(dynamicTest("shed_atLimit", () -> assertTrue(capacityBalancer.shedRequired(10, 10))));
        tests.add(dynamicTest("shed_belowLimit", () -> assertFalse(capacityBalancer.shedRequired(9, 10))));
        tests.add(dynamicTest("shed_aboveLimit", () -> assertTrue(capacityBalancer.shedRequired(11, 10))));

        return tests;
    }

    // ======================================================================
    // 8. Policy escalation exact thresholds (TRN006-008) ~20 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> policyEscalationThresholdTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // Severity boundary at 8
        tests.add(dynamicTest("escalation_sev7", () -> {
            assertEquals(2, policyEngine.escalationLevel(7, 5, false));
        }));
        tests.add(dynamicTest("escalation_sev8", () -> {
            assertEquals(3, policyEngine.escalationLevel(8, 5, false));
        }));
        tests.add(dynamicTest("escalation_sev9", () -> {
            assertEquals(3, policyEngine.escalationLevel(9, 5, false));
        }));

        // Severity boundary at 5
        tests.add(dynamicTest("escalation_sev4", () -> {
            assertEquals(1, policyEngine.escalationLevel(4, 5, false));
        }));
        tests.add(dynamicTest("escalation_sev5", () -> {
            assertEquals(2, policyEngine.escalationLevel(5, 5, false));
        }));
        tests.add(dynamicTest("escalation_sev6", () -> {
            assertEquals(2, policyEngine.escalationLevel(6, 5, false));
        }));

        // Impact boundary at 10
        tests.add(dynamicTest("escalation_impact10", () -> {
            assertEquals(2, policyEngine.escalationLevel(5, 10, false));
        }));
        tests.add(dynamicTest("escalation_impact11", () -> {
            assertEquals(3, policyEngine.escalationLevel(5, 11, false));
        }));

        // Combined: severity 8 + impact 11 + regulatory
        tests.add(dynamicTest("escalation_full_combo", () -> {
            assertEquals(5, policyEngine.escalationLevel(8, 11, true));
        }));
        tests.add(dynamicTest("escalation_sev8_impact11", () -> {
            assertEquals(4, policyEngine.escalationLevel(8, 11, false));
        }));
        tests.add(dynamicTest("escalation_sev8_regulatory", () -> {
            assertEquals(4, policyEngine.escalationLevel(8, 5, true));
        }));

        // Bypass boundary at level 4
        tests.add(dynamicTest("bypass_level3", () -> {
            assertFalse(policyEngine.bypassQueueAllowed(3, 2, 20));
        }));
        tests.add(dynamicTest("bypass_level4", () -> {
            assertTrue(policyEngine.bypassQueueAllowed(4, 2, 20));
        }));
        tests.add(dynamicTest("bypass_level5", () -> {
            assertTrue(policyEngine.bypassQueueAllowed(5, 2, 20));
        }));

        // Bypass approval boundary
        tests.add(dynamicTest("bypass_1approval", () -> {
            assertFalse(policyEngine.bypassQueueAllowed(4, 1, 20));
        }));
        tests.add(dynamicTest("bypass_2approvals", () -> {
            assertTrue(policyEngine.bypassQueueAllowed(4, 2, 20));
        }));

        // Bypass reason length boundary
        tests.add(dynamicTest("bypass_reason11", () -> {
            assertFalse(policyEngine.bypassQueueAllowed(4, 2, 11));
        }));
        tests.add(dynamicTest("bypass_reason12", () -> {
            assertTrue(policyEngine.bypassQueueAllowed(4, 2, 12));
        }));
        tests.add(dynamicTest("bypass_reason13", () -> {
            assertTrue(policyEngine.bypassQueueAllowed(4, 2, 13));
        }));

        return tests;
    }

    // ======================================================================
    // 9. Token freshness at expiry (TRN009) ~15 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> tokenFreshnessExpiryTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // Exact expiry boundary: now == issued + ttl → should be fresh
        tests.add(dynamicTest("token_exactExpiry", () -> {
            assertTrue(securityPolicy.tokenFresh(1000, 500, 1500));
        }));
        tests.add(dynamicTest("token_oneBeforeExpiry", () -> {
            assertTrue(securityPolicy.tokenFresh(1000, 500, 1499));
        }));
        tests.add(dynamicTest("token_oneAfterExpiry", () -> {
            assertFalse(securityPolicy.tokenFresh(1000, 500, 1501));
        }));

        // Various TTL values
        long[] ttls = {60, 300, 900, 1800, 3600};
        for (long ttl : ttls) {
            final long t = ttl;
            tests.add(dynamicTest("token_ttl" + t + "_exact", () -> {
                assertTrue(securityPolicy.tokenFresh(0, t, t));
            }));
            tests.add(dynamicTest("token_ttl" + t + "_expired", () -> {
                assertFalse(securityPolicy.tokenFresh(0, t, t + 1));
            }));
        }

        // Definitely fresh
        tests.add(dynamicTest("token_veryFresh", () -> {
            assertTrue(securityPolicy.tokenFresh(1000, 3600, 1000));
        }));
        // Definitely expired
        tests.add(dynamicTest("token_longExpired", () -> {
            assertFalse(securityPolicy.tokenFresh(1000, 100, 5000));
        }));

        return tests;
    }

    // ======================================================================
    // 10. Circuit breaker threshold (TRN027) ~15 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> circuitBreakerThresholdTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // Exact boundary at 5
        for (int failures = 0; failures <= 10; failures++) {
            final int f = failures;
            tests.add(dynamicTest("circuit_failures_" + f, () -> {
                boolean result = resilienceReplay.circuitOpen(f);
                boolean expected = f >= 5;
                assertEquals(expected, result, "Circuit should open at 5+ failures");
            }));
        }

        // Boundary emphasis
        tests.add(dynamicTest("circuit_exact4", () -> assertFalse(resilienceReplay.circuitOpen(4))));
        tests.add(dynamicTest("circuit_exact5", () -> assertTrue(resilienceReplay.circuitOpen(5))));
        tests.add(dynamicTest("circuit_exact6", () -> assertTrue(resilienceReplay.circuitOpen(6))));
        tests.add(dynamicTest("circuit_zero", () -> assertFalse(resilienceReplay.circuitOpen(0))));

        return tests;
    }

    // ======================================================================
    // 11. Queue governor policy thresholds (TRN013-014) ~15 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> queueGovernorPolicyThresholdTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // High burst boundary at 6
        tests.add(dynamicTest("governor_burst5", () -> {
            var policy = queueGovernor.nextPolicy(5);
            assertEquals(16, policy.maxInflight());
        }));
        tests.add(dynamicTest("governor_burst6", () -> {
            var policy = queueGovernor.nextPolicy(6);
            assertEquals(8, policy.maxInflight());
            assertTrue(policy.dropOldest());
        }));
        tests.add(dynamicTest("governor_burst7", () -> {
            var policy = queueGovernor.nextPolicy(7);
            assertEquals(8, policy.maxInflight());
        }));

        // Medium burst boundary at 3
        tests.add(dynamicTest("governor_burst2", () -> {
            var policy = queueGovernor.nextPolicy(2);
            assertEquals(32, policy.maxInflight());
            assertFalse(policy.dropOldest());
        }));
        tests.add(dynamicTest("governor_burst3", () -> {
            var policy = queueGovernor.nextPolicy(3);
            assertEquals(16, policy.maxInflight());
        }));
        tests.add(dynamicTest("governor_burst4", () -> {
            var policy = queueGovernor.nextPolicy(4);
            assertEquals(16, policy.maxInflight());
        }));

        // Throttle at exact boundary
        for (int total = 13; total <= 17; total++) {
            final int t = total;
            tests.add(dynamicTest("throttle_total" + t + "_limit15", () -> {
                var policy = new QueueGovernor.QueuePolicy(15, false);
                boolean result = queueGovernor.shouldThrottle(t / 2, t - t / 2, policy);
                boolean expected = t >= 15;
                assertEquals(expected, result);
            }));
        }

        // Zero values
        tests.add(dynamicTest("governor_burst0", () -> {
            var policy = queueGovernor.nextPolicy(0);
            assertEquals(32, policy.maxInflight());
            assertFalse(policy.dropOldest());
        }));
        tests.add(dynamicTest("throttle_zero", () -> {
            assertFalse(queueGovernor.shouldThrottle(0, 0, new QueueGovernor.QueuePolicy(15, false)));
        }));

        return tests;
    }

    // ======================================================================
    // 12. SLA breach risk boundary (TRN018) ~20 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> slaBreachRiskBoundaryTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // eta == sla - buffer: NOT a breach risk (boundary)
        tests.add(dynamicTest("breachRisk_atBoundary", () -> {
            assertFalse(slaModel.breachRisk(970, 1000, 30));
        }));
        tests.add(dynamicTest("breachRisk_onePastBoundary", () -> {
            assertTrue(slaModel.breachRisk(971, 1000, 30));
        }));
        tests.add(dynamicTest("breachRisk_oneBeforeBoundary", () -> {
            assertFalse(slaModel.breachRisk(969, 1000, 30));
        }));

        // Various buffer sizes
        long[] buffers = {0, 10, 30, 60, 120};
        for (long buffer : buffers) {
            final long b = buffer;
            tests.add(dynamicTest("breachRisk_buffer" + b + "_exact", () -> {
                assertFalse(slaModel.breachRisk(1000 - b, 1000, b));
            }));
            tests.add(dynamicTest("breachRisk_buffer" + b + "_over", () -> {
                assertTrue(slaModel.breachRisk(1000 - b + 1, 1000, b));
            }));
        }

        // Clearly safe
        tests.add(dynamicTest("breachRisk_safe", () -> {
            assertFalse(slaModel.breachRisk(100, 1000, 30));
        }));
        // Clearly breaching
        tests.add(dynamicTest("breachRisk_breaching", () -> {
            assertTrue(slaModel.breachRisk(1500, 1000, 30));
        }));

        // Zero buffer: eta > sla is breach
        tests.add(dynamicTest("breachRisk_zeroBuffer_atSla", () -> {
            assertFalse(slaModel.breachRisk(1000, 1000, 0));
        }));
        tests.add(dynamicTest("breachRisk_zeroBuffer_overSla", () -> {
            assertTrue(slaModel.breachRisk(1001, 1000, 0));
        }));

        return tests;
    }

    // ======================================================================
    // 13. Compliance override boundary (TRN016-017) ~15 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> complianceOverrideBoundaryTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // Reason length boundary at 12
        tests.add(dynamicTest("override_reason11", () -> {
            assertFalse(complianceLedger.overrideAllowed("eleven_char", 2, 60));
        }));
        tests.add(dynamicTest("override_reason12", () -> {
            assertTrue(complianceLedger.overrideAllowed("twelve_chars", 2, 60));
        }));
        tests.add(dynamicTest("override_reason13", () -> {
            assertTrue(complianceLedger.overrideAllowed("thirteen_char", 2, 60));
        }));

        // TTL boundary at 120
        tests.add(dynamicTest("override_ttl119", () -> {
            assertTrue(complianceLedger.overrideAllowed("long enough reason", 2, 119));
        }));
        tests.add(dynamicTest("override_ttl120", () -> {
            assertTrue(complianceLedger.overrideAllowed("long enough reason", 2, 120));
        }));
        tests.add(dynamicTest("override_ttl121", () -> {
            assertFalse(complianceLedger.overrideAllowed("long enough reason", 2, 121));
        }));

        // Retention boundary at 30
        tests.add(dynamicTest("retention_29", () -> assertEquals("hot", complianceLedger.retentionBucket(29))));
        tests.add(dynamicTest("retention_30", () -> assertEquals("hot", complianceLedger.retentionBucket(30))));
        tests.add(dynamicTest("retention_31", () -> assertEquals("warm", complianceLedger.retentionBucket(31))));

        // Retention boundary at 365
        tests.add(dynamicTest("retention_364", () -> assertEquals("warm", complianceLedger.retentionBucket(364))));
        tests.add(dynamicTest("retention_365", () -> assertEquals("warm", complianceLedger.retentionBucket(365))));
        tests.add(dynamicTest("retention_366", () -> assertEquals("cold", complianceLedger.retentionBucket(366))));

        // Approval boundary
        tests.add(dynamicTest("override_1approval", () -> {
            assertFalse(complianceLedger.overrideAllowed("long enough reason", 1, 60));
        }));
        tests.add(dynamicTest("override_2approvals", () -> {
            assertTrue(complianceLedger.overrideAllowed("long enough reason", 2, 60));
        }));

        return tests;
    }

    // ======================================================================
    // 14. Watermark accept boundary (TRN020) ~15 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> watermarkAcceptBoundaryTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // eventTs + tolerance == watermarkTs → should accept
        tests.add(dynamicTest("accept_exactBoundary", () -> {
            assertTrue(watermarkWindow.accept(100, 105, 5));
        }));
        tests.add(dynamicTest("accept_belowBoundary", () -> {
            assertFalse(watermarkWindow.accept(100, 106, 5));
        }));
        tests.add(dynamicTest("accept_aboveBoundary", () -> {
            assertTrue(watermarkWindow.accept(100, 104, 5));
        }));

        // Zero tolerance: only events at or after watermark
        tests.add(dynamicTest("accept_zeroTolerance_equal", () -> {
            assertTrue(watermarkWindow.accept(100, 100, 0));
        }));
        tests.add(dynamicTest("accept_zeroTolerance_before", () -> {
            assertFalse(watermarkWindow.accept(99, 100, 0));
        }));
        tests.add(dynamicTest("accept_zeroTolerance_after", () -> {
            assertTrue(watermarkWindow.accept(101, 100, 0));
        }));

        // Large tolerance
        tests.add(dynamicTest("accept_largeTolerance", () -> {
            assertTrue(watermarkWindow.accept(0, 1000, 1000));
        }));
        tests.add(dynamicTest("accept_largeTolerance_fail", () -> {
            assertFalse(watermarkWindow.accept(0, 1001, 1000));
        }));

        // Bucket tests
        tests.add(dynamicTest("bucket_exact_division", () -> {
            assertEquals(10, watermarkWindow.bucketFor(3000, 300));
        }));
        tests.add(dynamicTest("bucket_remainder", () -> {
            assertEquals(10, watermarkWindow.bucketFor(3100, 300));
        }));
        tests.add(dynamicTest("bucket_zero_epoch", () -> {
            assertEquals(0, watermarkWindow.bucketFor(0, 300));
        }));
        tests.add(dynamicTest("bucket_unit_window", () -> {
            assertEquals(42, watermarkWindow.bucketFor(42, 1));
        }));
        tests.add(dynamicTest("bucket_invalid_window", () -> {
            assertThrows(IllegalArgumentException.class, () -> watermarkWindow.bucketFor(100, 0));
        }));
        tests.add(dynamicTest("bucket_negative_window", () -> {
            assertThrows(IllegalArgumentException.class, () -> watermarkWindow.bucketFor(100, -1));
        }));

        return tests;
    }

    // ======================================================================
    // 15. Audit ordering with equals (TRN021) ~10 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> auditOrderingWithEqualsTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // Strictly increasing: ordered
        tests.add(dynamicTest("ordered_strict_increase", () -> {
            assertTrue(auditTrail.ordered(List.of(1L, 2L, 3L, 4L)));
        }));

        // Equal consecutive: NOT ordered (strict)
        tests.add(dynamicTest("ordered_equal_start", () -> {
            assertFalse(auditTrail.ordered(List.of(1L, 1L, 2L, 3L)));
        }));
        tests.add(dynamicTest("ordered_equal_middle", () -> {
            assertFalse(auditTrail.ordered(List.of(1L, 2L, 2L, 3L)));
        }));
        tests.add(dynamicTest("ordered_equal_end", () -> {
            assertFalse(auditTrail.ordered(List.of(1L, 2L, 3L, 3L)));
        }));
        tests.add(dynamicTest("ordered_all_equal", () -> {
            assertFalse(auditTrail.ordered(List.of(5L, 5L, 5L)));
        }));

        // Decreasing: NOT ordered
        tests.add(dynamicTest("ordered_decreasing", () -> {
            assertFalse(auditTrail.ordered(List.of(3L, 2L, 1L)));
        }));

        // Single element: always ordered
        tests.add(dynamicTest("ordered_single", () -> {
            assertTrue(auditTrail.ordered(List.of(42L)));
        }));

        // Empty: always ordered
        tests.add(dynamicTest("ordered_empty", () -> {
            assertTrue(auditTrail.ordered(List.of()));
        }));

        // Large gaps: ordered
        tests.add(dynamicTest("ordered_large_gaps", () -> {
            assertTrue(auditTrail.ordered(List.of(1L, 100L, 10000L)));
        }));

        // Mixed: increase then equal
        tests.add(dynamicTest("ordered_increase_then_equal", () -> {
            assertFalse(auditTrail.ordered(List.of(1L, 5L, 10L, 10L, 20L)));
        }));

        return tests;
    }

    // ======================================================================
    // 16. Retry budget boundaries (TRN010, TRN011, TRN028) ~15 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> retryBudgetBoundaryTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // Backoff: attempt 1 should use power 0 (base * 1)
        tests.add(dynamicTest("backoff_attempt1_base50", () -> {
            assertEquals(50, retryBudget.backoffMs(1, 50));
        }));
        tests.add(dynamicTest("backoff_attempt1_base100", () -> {
            assertEquals(100, retryBudget.backoffMs(1, 100));
        }));
        tests.add(dynamicTest("backoff_attempt2_base50", () -> {
            assertEquals(100, retryBudget.backoffMs(2, 50));
        }));
        tests.add(dynamicTest("backoff_attempt3_base50", () -> {
            assertEquals(200, retryBudget.backoffMs(3, 50));
        }));

        // shouldRetry: at max attempts should be false
        tests.add(dynamicTest("retry_atMax", () -> {
            assertFalse(retryBudget.shouldRetry(3, 3, false));
        }));
        tests.add(dynamicTest("retry_belowMax", () -> {
            assertTrue(retryBudget.shouldRetry(2, 3, false));
        }));
        tests.add(dynamicTest("retry_aboveMax", () -> {
            assertFalse(retryBudget.shouldRetry(4, 3, false));
        }));
        tests.add(dynamicTest("retry_circuitOpen", () -> {
            assertFalse(retryBudget.shouldRetry(0, 10, true));
        }));

        // Penalty score: retries * 2 + latencyMs / 250
        tests.add(dynamicTest("penalty_1retry_0latency", () -> {
            assertEquals(2, retryBudget.penaltyScore(1, 0));
        }));
        tests.add(dynamicTest("penalty_0retry_250latency", () -> {
            assertEquals(1, retryBudget.penaltyScore(0, 250));
        }));
        tests.add(dynamicTest("penalty_0retry_500latency", () -> {
            assertEquals(2, retryBudget.penaltyScore(0, 500));
        }));
        tests.add(dynamicTest("penalty_3retry_750latency", () -> {
            assertEquals(9, retryBudget.penaltyScore(3, 750));
        }));
        tests.add(dynamicTest("penalty_1retry_200latency", () -> {
            assertEquals(2, retryBudget.penaltyScore(1, 200));
        }));
        tests.add(dynamicTest("penalty_4retry_750latency", () -> {
            assertEquals(11, retryBudget.penaltyScore(4, 750));
        }));

        return tests;
    }

    // ======================================================================
    // 17. Statistics reducer boundaries (TRN025-026) ~15 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> statisticsReducerBoundaryTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // Percentile with single element
        tests.add(dynamicTest("percentile_single_p0", () -> {
            assertEquals(10.0, statisticsReducer.percentile(new double[]{10.0}, 0.0));
        }));
        tests.add(dynamicTest("percentile_single_p50", () -> {
            assertEquals(10.0, statisticsReducer.percentile(new double[]{10.0}, 0.5));
        }));
        tests.add(dynamicTest("percentile_single_p100", () -> {
            assertEquals(10.0, statisticsReducer.percentile(new double[]{10.0}, 1.0));
        }));

        // Percentile with two elements
        tests.add(dynamicTest("percentile_two_p0", () -> {
            assertEquals(1.0, statisticsReducer.percentile(new double[]{1.0, 2.0}, 0.0));
        }));
        tests.add(dynamicTest("percentile_two_p100", () -> {
            assertEquals(2.0, statisticsReducer.percentile(new double[]{1.0, 2.0}, 1.0));
        }));

        // Unsorted input should still work (method sorts internally)
        tests.add(dynamicTest("percentile_unsorted", () -> {
            assertEquals(1.0, statisticsReducer.percentile(new double[]{3.0, 1.0, 2.0}, 0.0));
        }));

        // Empty array should throw
        tests.add(dynamicTest("percentile_empty", () -> {
            assertThrows(IllegalArgumentException.class, () ->
                statisticsReducer.percentile(new double[]{}, 0.5));
        }));

        // boundedRatio with denominator = 0
        tests.add(dynamicTest("boundedRatio_denomZero", () -> {
            assertEquals(0.0, statisticsReducer.boundedRatio(5.0, 0.0));
        }));

        // boundedRatio with negative denominator
        tests.add(dynamicTest("boundedRatio_denomNegative", () -> {
            assertEquals(0.0, statisticsReducer.boundedRatio(5.0, -1.0));
        }));

        // boundedRatio normal cases
        tests.add(dynamicTest("boundedRatio_half", () -> {
            assertEquals(0.5, statisticsReducer.boundedRatio(5.0, 10.0), 1e-9);
        }));
        tests.add(dynamicTest("boundedRatio_clampHigh", () -> {
            assertEquals(1.0, statisticsReducer.boundedRatio(20.0, 10.0), 1e-9);
        }));
        tests.add(dynamicTest("boundedRatio_clampLow", () -> {
            assertEquals(0.0, statisticsReducer.boundedRatio(-5.0, 10.0), 1e-9);
        }));
        tests.add(dynamicTest("boundedRatio_exact1", () -> {
            assertEquals(1.0, statisticsReducer.boundedRatio(10.0, 10.0), 1e-9);
        }));
        tests.add(dynamicTest("boundedRatio_exact0", () -> {
            assertEquals(0.0, statisticsReducer.boundedRatio(0.0, 10.0), 1e-9);
        }));

        return tests;
    }

    // ======================================================================
    // 18. Workflow state machine exhaustive (TRN024) ~20 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> workflowStateMachineExhaustiveTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // Correct event → state mapping
        Map<String, String> correctMapping = Map.of(
            "validate", "validated",
            "capacity_ok", "capacity_checked",
            "dispatch", "dispatched",
            "publish", "reported",
            "cancel", "canceled"
        );
        for (var entry : correctMapping.entrySet()) {
            final String event = entry.getKey();
            final String expected = entry.getValue();
            tests.add(dynamicTest("nextState_" + event, () -> {
                assertEquals(expected, workflowOrchestrator.nextStateFor(event));
            }));
        }

        // Unknown events should produce "drafted"
        String[] unknownEvents = {"unknown", "rollback", "restart", "expire", ""};
        for (String event : unknownEvents) {
            final String e = event;
            tests.add(dynamicTest("nextState_unknown_" + (e.isEmpty() ? "empty" : e), () -> {
                assertEquals("drafted", workflowOrchestrator.nextStateFor(e));
            }));
        }

        // Valid transitions
        String[][] validTransitions = {
            {"drafted", "validated"},
            {"drafted", "canceled"},
            {"validated", "capacity_checked"},
            {"validated", "canceled"},
            {"capacity_checked", "dispatched"},
            {"capacity_checked", "canceled"},
            {"dispatched", "reported"},
        };
        for (String[] t : validTransitions) {
            tests.add(dynamicTest("transition_valid_" + t[0] + "_to_" + t[1], () -> {
                assertTrue(workflowOrchestrator.transitionAllowed(t[0], t[1]));
            }));
        }

        // Invalid transitions (swapped events should fail)
        tests.add(dynamicTest("transition_invalid_reported_to_dispatched", () -> {
            assertFalse(workflowOrchestrator.transitionAllowed("reported", "dispatched"));
        }));
        tests.add(dynamicTest("transition_invalid_dispatched_to_canceled", () -> {
            assertFalse(workflowOrchestrator.transitionAllowed("dispatched", "canceled"));
        }));
        tests.add(dynamicTest("transition_invalid_canceled_to_drafted", () -> {
            assertFalse(workflowOrchestrator.transitionAllowed("canceled", "drafted"));
        }));

        return tests;
    }

    // ======================================================================
    // 19. Breach severity boundaries (TRN019) ~15 tests
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> breachSeverityBoundaryTests() {
        List<DynamicTest> tests = new ArrayList<>();

        // delta = 0: "none" (on time)
        tests.add(dynamicTest("severity_delta0", () -> {
            assertEquals("none", slaModel.breachSeverity(1000, 1000));
        }));
        // delta = -1: "none"
        tests.add(dynamicTest("severity_deltaNeg1", () -> {
            assertEquals("none", slaModel.breachSeverity(999, 1000));
        }));
        // delta = 1: "minor"
        tests.add(dynamicTest("severity_delta1", () -> {
            assertEquals("minor", slaModel.breachSeverity(1001, 1000));
        }));
        // delta = 299: "minor"
        tests.add(dynamicTest("severity_delta299", () -> {
            assertEquals("minor", slaModel.breachSeverity(1299, 1000));
        }));
        // delta = 300: "minor" (boundary, still minor)
        tests.add(dynamicTest("severity_delta300", () -> {
            assertEquals("minor", slaModel.breachSeverity(1300, 1000));
        }));
        // delta = 301: "major"
        tests.add(dynamicTest("severity_delta301", () -> {
            assertEquals("major", slaModel.breachSeverity(1301, 1000));
        }));
        // delta = 899: "major"
        tests.add(dynamicTest("severity_delta899", () -> {
            assertEquals("major", slaModel.breachSeverity(1899, 1000));
        }));
        // delta = 900: "major" (boundary, still major)
        tests.add(dynamicTest("severity_delta900", () -> {
            assertEquals("major", slaModel.breachSeverity(1900, 1000));
        }));
        // delta = 901: "critical"
        tests.add(dynamicTest("severity_delta901", () -> {
            assertEquals("critical", slaModel.breachSeverity(1901, 1000));
        }));
        // delta = 1800: "critical"
        tests.add(dynamicTest("severity_delta1800", () -> {
            assertEquals("critical", slaModel.breachSeverity(2800, 1000));
        }));

        // Negative deltas (well ahead of SLA)
        tests.add(dynamicTest("severity_wellAhead", () -> {
            assertEquals("none", slaModel.breachSeverity(500, 1000));
        }));

        // Parametric across different SLA values
        long[] slas = {500, 1000, 2000};
        for (long sla : slas) {
            final long s = sla;
            tests.add(dynamicTest("severity_sla" + s + "_boundary300", () -> {
                assertEquals("minor", slaModel.breachSeverity(s + 300, s));
            }));
            tests.add(dynamicTest("severity_sla" + s + "_boundary900", () -> {
                assertEquals("major", slaModel.breachSeverity(s + 900, s));
            }));
        }

        return tests;
    }

    // ======================================================================
    // 20. Extended fingerprint case grid (TRN031) ~40 tests
    //     ALL inputs contain uppercase → ALL fail without toLowerCase
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> extendedFingerprintCaseGrid() {
        List<DynamicTest> tests = new ArrayList<>();
        String[] tenants = {"Alpha", "BETA", "Gamma", "DELTA", "Epsilon", "ZETA", "Eta", "THETA"};
        String[] traces = {"Trace-1", "TRACE-2", "Trace-3", "TRACE-4", "Trace-5"};
        for (String tenant : tenants) {
            for (String trace : traces) {
                final String t = tenant;
                final String tr = trace;
                tests.add(dynamicTest("fp_ext_" + t + "_" + tr, () -> {
                    String result = auditTrail.fingerprint(t, tr, "Dispatch.Event");
                    assertEquals(
                        (t + ":" + tr + ":Dispatch.Event").toLowerCase().trim(),
                        result,
                        "Fingerprint must lowercase all components"
                    );
                }));
            }
        }
        return tests;
    }

    // ======================================================================
    // 21. Extended hash chain grid (TRN032) ~48 tests
    //     ALL use non-zero seed → ALL fail with wrong multiplier
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> extendedHashChainGrid() {
        List<DynamicTest> tests = new ArrayList<>();
        long[] seeds = {1, 7, 42, 100, 999, 5000, 12345, 99999};
        String[] payloads = {"a", "ab", "abc", "test", "hello", "xyz"};

        for (long seed : seeds) {
            for (String payload : payloads) {
                final long s = seed;
                final String p = payload;
                tests.add(dynamicTest("hashGrid_" + s + "_" + p, () -> {
                    long charSum = 0;
                    for (char c : p.toCharArray()) charSum += c;
                    long expected = (s * 31 + charSum) % 1_000_000_007L;
                    long result = auditTrail.appendHash(s, p);
                    assertEquals(expected, result,
                        "Hash chain with seed=" + s + " payload='" + p + "' should use multiplier 31");
                }));
            }
        }
        return tests;
    }

    // ======================================================================
    // 22. Extended lag future timestamps (TRN033) ~40 tests
    //     ALL have processedTs > nowTs → ALL fail with Math.abs
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> extendedLagFutureTimestamps() {
        List<DynamicTest> tests = new ArrayList<>();
        // Parametric: various (nowTs, processedTs) where processedTs > nowTs
        for (long now = 0; now <= 900; now += 100) {
            for (long gap = 1; gap <= 100; gap += 25) {
                final long n = now;
                final long processed = now + gap;
                tests.add(dynamicTest("lagFuture_" + n + "_+" + gap, () -> {
                    long result = watermarkWindow.lagSeconds(n, processed);
                    assertEquals(0L, result,
                        "Lag should be 0 when processedTs(" + processed + ") > nowTs(" + n + ")");
                }));
            }
        }
        return tests;
    }

    // ======================================================================
    // 23. Extended churn new keys grid (TRN034) ~45 tests
    //     ALL have new keys → ALL fail without total+=1
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> extendedChurnNewKeysGrid() {
        List<DynamicTest> tests = new ArrayList<>();
        // Grid: existingKeys x newKeys
        for (int existing = 0; existing <= 4; existing++) {
            for (int newKeys = 1; newKeys <= 5; newKeys++) {
                final int ex = existing;
                final int nk = newKeys;
                for (int changedExisting = 0; changedExisting <= Math.min(existing, 2); changedExisting++) {
                    final int ch = changedExisting;
                    tests.add(dynamicTest("churnGrid_" + ex + "e_" + nk + "n_" + ch + "c", () -> {
                        Map<String, String> prev = new HashMap<>();
                        Map<String, String> curr = new HashMap<>();
                        for (int j = 0; j < ex; j++) {
                            prev.put("key" + j, "val" + j);
                            if (j < ch) {
                                curr.put("key" + j, "changed" + j);
                            } else {
                                curr.put("key" + j, "val" + j);
                            }
                        }
                        for (int j = 0; j < nk; j++) {
                            curr.put("newkey" + j, "newval" + j);
                        }
                        double churn = routingHeuristics.churnRate(prev, curr);
                        int totalKeys = ex + nk;
                        int changedKeys = ch + nk;
                        double expected = totalKeys == 0 ? 0.0 : (double) changedKeys / totalKeys;
                        assertEquals(expected, churn, 1e-9,
                            "Churn with " + ex + " existing, " + nk + " new, " + ch + " changed");
                    }));
                }
            }
        }
        return tests;
    }

    // ======================================================================
    // 24. Extended replay delta grid (TRN035) ~50 tests
    //     ALL have inflightDelta != backlogDelta → ALL fail with swap
    // ======================================================================
    @TestFactory
    Collection<DynamicTest> extendedReplayDeltaGrid() {
        List<DynamicTest> tests = new ArrayList<>();
        int[] inflightDeltas = {1, 3, 5, 10, 20};
        int[] backlogDeltas = {0, 2, 4, 8, 15};
        long[] bases = {0, 10};

        for (int iDelta : inflightDeltas) {
            for (int bDelta : backlogDeltas) {
                if (iDelta == bDelta) continue; // skip equal (swap wouldn't be detected)
                for (long base : bases) {
                    final int id = iDelta;
                    final int bd = bDelta;
                    final long b = base;
                    tests.add(dynamicTest("replayGrid_i" + id + "_b" + bd + "_base" + b, () -> {
                        var events = List.of(
                            new ResilienceReplay.ReplayEvent(11, "k1", id, bd)
                        );
                        var snap = resilienceReplay.replay(b, b, 10, events);
                        assertEquals(b + id, snap.inflight(),
                            "inflight should add inflightDelta(" + id + "), not backlogDelta(" + bd + ")");
                        assertEquals(b + bd, snap.backlog(),
                            "backlog should add backlogDelta(" + bd + "), not inflightDelta(" + id + ")");
                    }));
                }
            }
        }
        return tests;
    }
}
