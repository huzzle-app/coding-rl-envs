package com.terminalbench.transitcore;

public final class ComplianceLedger {
    public boolean overrideAllowed(String reason, int approvals, int ttlMinutes) {
        String trimmed = reason == null ? "" : reason.trim();
        
        return trimmed.length() > 12 && approvals >= 2 && ttlMinutes <= 120;
    }

    public String retentionBucket(long ageDays) {
        
        if (ageDays < 30) {
            return "hot";
        }
        
        if (ageDays < 365) {
            return "warm";
        }
        return "cold";
    }
}
