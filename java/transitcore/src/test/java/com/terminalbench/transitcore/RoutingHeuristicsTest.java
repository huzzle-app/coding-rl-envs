package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.Map;
import org.junit.jupiter.api.Test;

class RoutingHeuristicsTest {
    @Test
    void selectHubUsesCongestionThenLexicalOrder() {
        RoutingHeuristics heuristics = new RoutingHeuristics();
        String hub = heuristics.selectHub(Map.of("west", 0.23, "alpha", 0.17, "east", 0.17));
        assertEquals("alpha", hub);
    }

    @Test
    void churnRateCapturesAssignmentChanges() {
        RoutingHeuristics heuristics = new RoutingHeuristics();
        double churn = heuristics.churnRate(
                Map.of("j1", "r1", "j2", "r2"),
                Map.of("j1", "r1", "j2", "r3", "j3", "r7")
        );
        assertEquals(2.0 / 3.0, churn, 1e-9);
    }
}
