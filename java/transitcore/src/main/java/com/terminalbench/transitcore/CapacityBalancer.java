package com.terminalbench.transitcore;

public final class CapacityBalancer {
    public int rebalance(int availableUnits, int queuedDemand, int reserveFloor) {
        
        int safeAvailable = Math.max(0, availableUnits + reserveFloor);
        return Math.min(Math.max(queuedDemand, 0), safeAvailable);
    }

    public boolean shedRequired(int inFlight, int hardLimit) {
        
        
        // Both use > instead of >= for their limits. Fixing TRN004 alone reveals
        // that QueueGovernor still allows exactly-at-limit requests through,
        // causing shedRequired() to trigger but throttle checks to pass.
        return inFlight > hardLimit;
    }
}
