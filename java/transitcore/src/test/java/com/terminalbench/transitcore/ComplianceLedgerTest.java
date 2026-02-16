package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class ComplianceLedgerTest {
    @Test
    void overrideAllowedRequiresReasonApprovalsAndTtl() {
        ComplianceLedger ledger = new ComplianceLedger();
        assertTrue(ledger.overrideAllowed("committee-approved release", 2, 60));
        assertFalse(ledger.overrideAllowed("short", 2, 60));
        assertFalse(ledger.overrideAllowed("committee-approved release", 1, 60));
        assertFalse(ledger.overrideAllowed("committee-approved release", 2, 180));
    }

    @Test
    void overrideAllowedAtExactBoundaries() {
        ComplianceLedger ledger = new ComplianceLedger();
        // exactly 12 characters is the minimum
        assertTrue(ledger.overrideAllowed("twelve_chars", 2, 60));
        // exactly 120 TTL is the maximum allowed
        assertTrue(ledger.overrideAllowed("long enough reason text", 2, 120));
        // 11 characters should be rejected
        assertFalse(ledger.overrideAllowed("eleven_char", 2, 60));
    }

    @Test
    void retentionBucketClassification() {
        ComplianceLedger ledger = new ComplianceLedger();
        assertEquals("hot", ledger.retentionBucket(7));
        assertEquals("warm", ledger.retentionBucket(180));
        assertEquals("cold", ledger.retentionBucket(1000));
    }

    @Test
    void retentionBucketAtExactBoundaries() {
        ComplianceLedger ledger = new ComplianceLedger();
        assertEquals("hot", ledger.retentionBucket(30));
        assertEquals("warm", ledger.retentionBucket(365));
    }
}
