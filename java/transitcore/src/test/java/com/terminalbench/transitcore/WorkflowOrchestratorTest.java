package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class WorkflowOrchestratorTest {
    @Test
    void transitionGraphIsEnforced() {
        WorkflowOrchestrator orchestrator = new WorkflowOrchestrator();
        assertTrue(orchestrator.transitionAllowed("drafted", "validated"));
        assertFalse(orchestrator.transitionAllowed("drafted", "dispatched"));
        assertTrue(orchestrator.transitionAllowed("capacity_checked", "dispatched"));
    }

    @Test
    void nextStateForEvent() {
        WorkflowOrchestrator orchestrator = new WorkflowOrchestrator();
        assertEquals("validated", orchestrator.nextStateFor("validate"));
        assertEquals("reported", orchestrator.nextStateFor("publish"));
        assertEquals("drafted", orchestrator.nextStateFor("unknown"));
    }
}
