package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class SlaModelTest {
    @Test
    void breachRiskAndSeverity() {
        SlaModel model = new SlaModel();
        assertTrue(model.breachRisk(980, 1000, 30));
        assertFalse(model.breachRisk(930, 1000, 30));

        assertEquals("none", model.breachSeverity(900, 1000));
        assertEquals("minor", model.breachSeverity(1200, 1000));
        assertEquals("major", model.breachSeverity(1700, 1000));
        assertEquals("critical", model.breachSeverity(2500, 1000));
    }
}
