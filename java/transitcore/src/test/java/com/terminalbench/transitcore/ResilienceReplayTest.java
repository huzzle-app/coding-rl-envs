package com.terminalbench.transitcore;

import static org.junit.jupiter.api.Assertions.assertEquals;

import java.util.List;
import org.junit.jupiter.api.Test;

class ResilienceReplayTest {
    @Test
    void orderedAndShuffledReplayConverges() {
        ResilienceReplay replay = new ResilienceReplay();
        List<ResilienceReplay.ReplayEvent> ordered = List.of(
                new ResilienceReplay.ReplayEvent(11, "k1", 3, 2),
                new ResilienceReplay.ReplayEvent(12, "k2", -1, 1),
                new ResilienceReplay.ReplayEvent(13, "k3", 2, -1)
        );
        List<ResilienceReplay.ReplayEvent> shuffled = List.of(ordered.get(2), ordered.get(0), ordered.get(1));

        ResilienceReplay.ReplaySnapshot a = replay.replay(20, 14, 10, ordered);
        ResilienceReplay.ReplaySnapshot b = replay.replay(20, 14, 10, shuffled);

        assertEquals(a, b);
    }

    @Test
    void staleVersionsAreIgnored() {
        ResilienceReplay replay = new ResilienceReplay();
        List<ResilienceReplay.ReplayEvent> events = List.of(
                new ResilienceReplay.ReplayEvent(9, "old", 50, 50),
                new ResilienceReplay.ReplayEvent(10, "eq", 2, 1)
        );

        ResilienceReplay.ReplaySnapshot snapshot = replay.replay(20, 10, 10, events);
        assertEquals(1, snapshot.applied());
        assertEquals(22, snapshot.inflight());
        assertEquals(11, snapshot.backlog());
    }

    @Test
    void staleDuplicateDoesNotShadowFreshEvent() {
        ResilienceReplay replay = new ResilienceReplay();
        List<ResilienceReplay.ReplayEvent> events = List.of(
                new ResilienceReplay.ReplayEvent(9, "dup", 99, 99),
                new ResilienceReplay.ReplayEvent(11, "dup", 4, 3)
        );

        ResilienceReplay.ReplaySnapshot snapshot = replay.replay(15, 7, 10, events);
        assertEquals(1, snapshot.applied());
        assertEquals(19, snapshot.inflight());
        assertEquals(10, snapshot.backlog());
    }

    @Test
    void retryAndCircuitRules() {
        ResilienceReplay replay = new ResilienceReplay();
        assertEquals(50, replay.retryBackoffMs(1, 50));
        assertEquals(200, replay.retryBackoffMs(3, 50));
        assertEquals(true, replay.circuitOpen(5));
        assertEquals(false, replay.circuitOpen(4));
    }
}
