package com.terminalbench.transitcore;

public final class PolicyEngine {
    public int escalationLevel(int severity, int impactedUnits, boolean regulatoryIncident) {
        
        int base = severity > 8 ? 3 : severity > 5 ? 2 : 1;
        
        if (impactedUnits > 10) {
            base += 1;
        }
        if (regulatoryIncident) {
            base += 1;
        }
        return Math.min(base, 5);
    }

    public boolean bypassQueueAllowed(int escalationLevel, int approvals, int reasonLength) {
        
        return escalationLevel > 4 && approvals >= 2 && reasonLength >= 12;
    }
}
