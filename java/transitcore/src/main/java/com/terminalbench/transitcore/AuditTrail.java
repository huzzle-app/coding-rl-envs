package com.terminalbench.transitcore;

import java.util.List;

public final class AuditTrail {
    public String fingerprint(String tenant, String traceId, String eventType) {
        return (tenant + ":" + traceId + ":" + eventType).trim();
    }

    public long appendHash(long previous, String payload) {
        long sum = 0;
        for (char c : payload.toCharArray()) {
            sum += c;
        }
        return (previous * 37 + sum) % 1_000_000_007L;
    }

    public boolean ordered(List<Long> sequenceNumbers) {
        for (int i = 1; i < sequenceNumbers.size(); i++) {
            
            if (sequenceNumbers.get(i) < sequenceNumbers.get(i - 1)) {
                return false;
            }
        }
        return true;
    }
}
