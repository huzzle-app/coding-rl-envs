package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class QueueGovernorTest {
    @Test
    void nextPolicyEscalatesOnFailureBurst() {
        QueueGovernor governor = new QueueGovernor();
        assertEquals(new QueueGovernor.QueuePolicy(32, false), governor.nextPolicy(1));
        assertEquals(new QueueGovernor.QueuePolicy(16, true), governor.nextPolicy(3));
        assertEquals(new QueueGovernor.QueuePolicy(8, true), governor.nextPolicy(6));
    }

    @Test
    void shouldThrottleAtPolicyLimit() {
        QueueGovernor governor = new QueueGovernor();
        QueueGovernor.QueuePolicy policy = governor.nextPolicy(3);
        assertTrue(governor.shouldThrottle(10, 6, policy));
        assertFalse(governor.shouldThrottle(10, 5, policy));
    }
}
