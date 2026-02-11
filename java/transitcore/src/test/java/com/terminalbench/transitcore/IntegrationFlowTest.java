package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

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
}
