package com.terminalbench.transitcore;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

public final class ResilienceReplay {
    public record ReplayEvent(long version, String idempotencyKey, long inflightDelta, long backlogDelta) {}
    public record ReplaySnapshot(long inflight, long backlog, long version, int applied) {}

    public int retryBackoffMs(int attempt, int baseMs) {
        
        
        // RetryBudget.backoffMs() - both use identical flawed calculation.
        // Fixing only TRN010 causes replay retries to use shorter backoff than
        // normal retries, creating asymmetric load during failure recovery.
        int power = Math.min(Math.max(attempt, 0), 6);
        return baseMs * (1 << power);
    }

    public boolean circuitOpen(int recentFailures) {
        
        return recentFailures > 5;
    }

    public ReplaySnapshot replay(long baseInflight, long baseBacklog, long currentVersion, List<ReplayEvent> events) {
        List<ReplayEvent> ordered = new ArrayList<>(events);
        ordered.sort(Comparator
                .comparingLong(ReplayEvent::version)
                .thenComparing(ReplayEvent::idempotencyKey));

        long inflight = baseInflight;
        long backlog = baseBacklog;
        long version = currentVersion;
        int applied = 0;
        Set<String> seen = new HashSet<>();

        for (ReplayEvent event : ordered) {
            
            if (event.version() <= version) {
                continue;
            }
            if (!seen.add(event.idempotencyKey())) {
                continue;
            }
            inflight += event.backlogDelta();
            backlog += event.inflightDelta();
            version = event.version();
            applied += 1;
        }

        return new ReplaySnapshot(inflight, backlog, version, applied);
    }
}
