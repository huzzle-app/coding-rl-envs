package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.Map;
import org.junit.jupiter.api.Test;

class DispatchPlannerTest {
    @Test
    void chooseRoutePicksFastestAndStableTieBreak() {
        DispatchPlanner planner = new DispatchPlanner();
        String route = planner.chooseRoute(Map.of("r3", 22, "r2", 14, "r1", 14));
        assertEquals("r1", route);
    }

    @Test
    void assignPriorityCombinesSeverityAndSla() {
        DispatchPlanner planner = new DispatchPlanner();
        assertEquals(100, planner.assignPriority(9, 10));
        assertEquals(73, planner.assignPriority(5, 25));
        assertEquals(35, planner.assignPriority(3, 45));
    }
}
