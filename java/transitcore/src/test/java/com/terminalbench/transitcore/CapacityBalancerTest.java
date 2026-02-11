package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class CapacityBalancerTest {
    @Test
    void rebalanceHonorsReserveFloor() {
        CapacityBalancer balancer = new CapacityBalancer();
        assertEquals(6, balancer.rebalance(10, 8, 4));
        assertEquals(0, balancer.rebalance(2, 9, 4));
    }

    @Test
    void shedRequiredAtOrAboveHardLimit() {
        CapacityBalancer balancer = new CapacityBalancer();
        assertFalse(balancer.shedRequired(7, 8));
        assertTrue(balancer.shedRequired(8, 8));
    }
}
