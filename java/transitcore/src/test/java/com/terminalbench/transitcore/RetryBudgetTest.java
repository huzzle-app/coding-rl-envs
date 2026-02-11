package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class RetryBudgetTest {
    @Test
    void backoffAndRetryDecisions() {
        RetryBudget budget = new RetryBudget();
        assertEquals(40, budget.backoffMs(1, 40));
        assertEquals(160, budget.backoffMs(3, 40));

        assertTrue(budget.shouldRetry(1, 4, false));
        assertFalse(budget.shouldRetry(4, 4, false));
        assertFalse(budget.shouldRetry(1, 4, true));
    }

    @Test
    void penaltyScoreScalesWithLatencyAndRetries() {
        RetryBudget budget = new RetryBudget();
        assertEquals(2, budget.penaltyScore(1, 200));
        assertEquals(11, budget.penaltyScore(4, 750));
    }
}
