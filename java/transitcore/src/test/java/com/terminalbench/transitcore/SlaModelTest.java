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

    @Test
    void breachRiskAtExactBoundary() {
        SlaModel model = new SlaModel();
        // eta exactly at sla - buffer is NOT a breach risk
        assertFalse(model.breachRisk(970, 1000, 30));
        // one second past is a breach risk
        assertTrue(model.breachRisk(971, 1000, 30));
    }

    @Test
    void breachSeverityAtExactBoundaries() {
        SlaModel model = new SlaModel();
        // on-time (delta = 0) is not a breach
        assertEquals("none", model.breachSeverity(1000, 1000));
        // exactly 300 sec over is still minor
        assertEquals("minor", model.breachSeverity(1300, 1000));
        // exactly 900 sec over is still major
        assertEquals("major", model.breachSeverity(1900, 1000));
    }
}
