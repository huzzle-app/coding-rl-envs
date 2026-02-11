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
    void retentionBucketClassification() {
        ComplianceLedger ledger = new ComplianceLedger();
        assertEquals("hot", ledger.retentionBucket(7));
        assertEquals("warm", ledger.retentionBucket(180));
        assertEquals("cold", ledger.retentionBucket(1000));
    }
}
