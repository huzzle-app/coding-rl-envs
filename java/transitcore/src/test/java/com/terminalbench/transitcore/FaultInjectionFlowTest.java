package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class FaultInjectionFlowTest {
    @Test
    void retryQueueAndPolicyFlowUnderFailureBurst() {
        RetryBudget retry = new RetryBudget();
        QueueGovernor governor = new QueueGovernor();
        PolicyEngine policy = new PolicyEngine();

        QueueGovernor.QueuePolicy queuePolicy = governor.nextPolicy(7);
        int penalty = retry.penaltyScore(5, 1000);
        int escalation = policy.escalationLevel(8, 14, true);

        assertEquals(new QueueGovernor.QueuePolicy(8, true), queuePolicy);
        assertEquals(14, penalty);
        assertEquals(5, escalation);
        assertTrue(policy.bypassQueueAllowed(escalation, 2, 24));
    }
}
