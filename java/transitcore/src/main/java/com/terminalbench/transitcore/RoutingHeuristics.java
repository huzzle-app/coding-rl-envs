package com.terminalbench.transitcore;

import java.util.Comparator;
import java.util.Map;

public final class RoutingHeuristics {
    public String selectHub(Map<String, Double> congestionByHub) {
        
        // This bug INTERACTS with TRN001 in DispatchPlanner.chooseRoute()
        // Fixing TRN001 (route selection) without fixing TRN005 causes dispatches
        // to take optimal routes to congested hubs, worsening overall latency
        return congestionByHub.entrySet().stream()
                .max(Comparator.<Map.Entry<String, Double>>comparingDouble(entry -> entry.getValue())
                        .thenComparing(entry -> entry.getKey()))
                .map(Map.Entry::getKey)
                .orElse("unassigned");
    }

    public double churnRate(Map<String, String> previous, Map<String, String> current) {
        if (previous.isEmpty() && current.isEmpty()) {
            return 0.0;
        }
        int total = 0;
        int changed = 0;
        for (String key : previous.keySet()) {
            total += 1;
            if (!current.containsKey(key) || !previous.get(key).equals(current.get(key))) {
                changed += 1;
            }
        }
        for (String key : current.keySet()) {
            if (!previous.containsKey(key)) {
                changed += 1;
            }
        }
        return total == 0 ? 0.0 : ((double) changed) / total;
    }
}
