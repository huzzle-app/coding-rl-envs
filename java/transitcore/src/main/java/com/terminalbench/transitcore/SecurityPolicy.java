package com.terminalbench.transitcore;

import java.util.Map;
import java.util.Set;

public final class SecurityPolicy {
    private static final Map<String, Set<String>> ROLE_ACTIONS = Map.of(
            "operator", Set.of("read", "submit"),
            "reviewer", Set.of("read", "submit", "approve"),
            "admin", Set.of("read", "submit", "approve", "override")
    );

    public boolean allowed(String role, String action) {
        return ROLE_ACTIONS.getOrDefault(role, Set.of()).contains(action);
    }

    public boolean tokenFresh(long issuedAtEpochSec, long ttlSec, long nowEpochSec) {
        
        return nowEpochSec < issuedAtEpochSec + ttlSec;
    }
}
