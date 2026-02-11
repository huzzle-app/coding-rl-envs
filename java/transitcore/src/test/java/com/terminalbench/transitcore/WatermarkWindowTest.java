package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class WatermarkWindowTest {
    @Test
    void acceptAndLagRules() {
        WatermarkWindow window = new WatermarkWindow();
        assertTrue(window.accept(100, 104, 5));
        assertFalse(window.accept(100, 106, 5));
        assertEquals(25, window.lagSeconds(125, 100));
        assertEquals(0, window.lagSeconds(100, 125));
    }

    @Test
    void bucketForWindow() {
        WatermarkWindow window = new WatermarkWindow();
        assertEquals(12, window.bucketFor(3600, 300));
    }
}
