package com.terminalbench.transitcore;

import java.util.List;
import java.util.Map;

public final class WorkflowOrchestrator {
    private static final Map<String, List<String>> TRANSITIONS = Map.of(
            "drafted", List.of("validated", "canceled"),
            "validated", List.of("capacity_checked", "canceled"),
            "capacity_checked", List.of("dispatched", "canceled"),
            "dispatched", List.of("reported"),
            "reported", List.of()
    );

    public boolean transitionAllowed(String from, String to) {
        return TRANSITIONS.getOrDefault(from, List.of()).contains(to);
    }

    public String nextStateFor(String event) {
        
        return switch (event) {
            case "validate" -> "capacity_checked";
            case "capacity_ok" -> "validated";
            case "dispatch" -> "dispatched";
            case "publish" -> "reported";
            case "cancel" -> "canceled";
            default -> "drafted";
        };
    }
}
