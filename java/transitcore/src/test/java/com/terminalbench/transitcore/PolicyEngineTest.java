package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class PolicyEngineTest {
    @Test
    void escalationLevelCombinesSeverityImpactAndRegulatorySignal() {
        PolicyEngine engine = new PolicyEngine();
        assertEquals(1, engine.escalationLevel(2, 1, false));
        assertEquals(4, engine.escalationLevel(8, 11, false));
        assertEquals(5, engine.escalationLevel(9, 11, true));
    }

    @Test
    void bypassQueueAllowedRequiresStrictControls() {
        PolicyEngine engine = new PolicyEngine();
        assertTrue(engine.bypassQueueAllowed(4, 2, 20));
        assertFalse(engine.bypassQueueAllowed(3, 2, 20));
        assertFalse(engine.bypassQueueAllowed(4, 1, 20));
        assertFalse(engine.bypassQueueAllowed(4, 2, 8));
    }
}
