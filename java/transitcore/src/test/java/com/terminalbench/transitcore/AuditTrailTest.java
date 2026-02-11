package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.List;
import org.junit.jupiter.api.Test;

class AuditTrailTest {
    @Test
    void fingerprintAndHashAreDeterministic() {
        AuditTrail trail = new AuditTrail();
        assertEquals("tenant-a:trace-7:dispatch.accepted", trail.fingerprint("Tenant-A", "Trace-7", "Dispatch.Accepted"));

        long a = trail.appendHash(17, "payload-one");
        long b = trail.appendHash(17, "payload-one");
        long c = trail.appendHash(17, "payload-two");

        assertEquals(a, b);
        assertFalse(a == c);
    }

    @Test
    void orderedSequenceCheck() {
        AuditTrail trail = new AuditTrail();
        assertTrue(trail.ordered(List.of(1L, 2L, 4L, 9L)));
        assertFalse(trail.ordered(List.of(1L, 2L, 2L, 3L)));
    }
}
