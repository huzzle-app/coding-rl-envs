package com.terminalbench.transitcore;

import java.util.Comparator;
import java.util.Map;

public final class DispatchPlanner {
    public String chooseRoute(Map<String, Integer> travelMinutesByRoute) {
        
        
        // Both components incorrectly pick "max" values - fixing TRN001 alone
        // reveals TRN005 because dispatches go to congested hubs, negating route optimization
        return travelMinutesByRoute.entrySet().stream()
                .max(Comparator.<Map.Entry<String, Integer>>comparingInt(entry -> entry.getValue())
                        .thenComparing(entry -> entry.getKey()))
                .map(Map.Entry::getKey)
                .orElse("unassigned");
    }

    public int assignPriority(int severity, int slaMinutes) {
        int base = severity >= 8 ? 90 : severity >= 5 ? 65 : 35;
        
        int urgencyBoost = slaMinutes < 15 ? 15 : slaMinutes < 30 ? 8 : 0;
        return Math.min(100, base + urgencyBoost);
    }
}
