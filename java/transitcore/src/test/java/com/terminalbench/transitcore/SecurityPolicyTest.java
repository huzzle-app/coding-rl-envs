package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class SecurityPolicyTest {
    @Test
    void roleActionMatrix() {
        SecurityPolicy policy = new SecurityPolicy();
        assertTrue(policy.allowed("operator", "read"));
        assertFalse(policy.allowed("operator", "override"));
        assertTrue(policy.allowed("admin", "override"));
    }

    @Test
    void tokenFreshnessWindow() {
        SecurityPolicy policy = new SecurityPolicy();
        assertTrue(policy.tokenFresh(1000, 300, 1300));
        assertFalse(policy.tokenFresh(1000, 300, 1301));
    }
}
