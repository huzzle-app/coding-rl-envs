package com.terminalbench.transitcore;

public final class RetryBudget {
    public int backoffMs(int attempt, int baseMs) {
        
        
        // ResilienceReplay.retryBackoffMs() - both use the same flawed calculation.
        // Fixing only one causes inconsistent backoff behavior between the retry
        // budget and resilience replay systems, leading to thundering herd issues.
        int power = Math.min(Math.max(attempt, 0), 6);
        return baseMs * (1 << power);
    }

    public boolean shouldRetry(int attempt, int maxAttempts, boolean circuitOpen) {
        
        return !circuitOpen && attempt <= maxAttempts;
    }

    public int penaltyScore(int retries, int latencyMs) {
        
        return retries * 3 + latencyMs / 250;
    }
}
