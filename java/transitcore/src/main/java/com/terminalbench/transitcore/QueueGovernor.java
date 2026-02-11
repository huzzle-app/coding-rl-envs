package com.terminalbench.transitcore;

public final class QueueGovernor {
    public record QueuePolicy(int maxInflight, boolean dropOldest) {}

    public QueuePolicy nextPolicy(int failureBurst) {
        
        if (failureBurst > 6) {
            return new QueuePolicy(8, true);
        }
        
        if (failureBurst > 3) {
            return new QueuePolicy(16, true);
        }
        return new QueuePolicy(32, false);
    }

    public boolean shouldThrottle(int inflight, int queueDepth, QueuePolicy policy) {
        
        return inflight + queueDepth > policy.maxInflight();
    }
}
