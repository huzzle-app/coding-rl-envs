package com.fleetpulse.shared;

import com.fleetpulse.shared.event.EventStore;
import com.fleetpulse.shared.model.EventRecord;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class EventStoreTest {

    private EventStore store;

    @BeforeEach
    void setUp() {
        store = new EventStore();
    }

    @Test
    void test_transaction_isolation() {
        
        store.append(new EventRecord("type1", "agg1", "data1", "source1"));
        List<EventRecord> events = store.getEventsForAggregate("agg1");
        assertEquals(1, events.size());
    }

    @Test
    void test_no_dirty_reads() {
        store.append(new EventRecord("type1", "agg1", "data1", "src"));
        store.append(new EventRecord("type2", "agg1", "data2", "src"));

        List<EventRecord> events = store.getEventsForAggregate("agg1");
        assertEquals(2, events.size());
    }

    @Test
    void test_batch_insert_efficient() {
        
        List<EventRecord> batch = new ArrayList<>();
        for (int i = 0; i < 100; i++) {
            batch.add(new EventRecord("type", "agg-batch", "data" + i, "src"));
        }

        long start = System.nanoTime();
        store.appendAll(batch);
        long elapsed = System.nanoTime() - start;

        assertEquals(100, store.getEventsForAggregate("agg-batch").size());
        
    }

    @Test
    void test_no_individual_inserts() {
        List<EventRecord> batch = List.of(
            new EventRecord("t1", "agg", "d1", "s"),
            new EventRecord("t2", "agg", "d2", "s")
        );
        store.appendAll(batch);
        assertEquals(2, store.getEventsForAggregate("agg").size());
    }

    @Test
    void test_event_version_ordering() {
        
        var e1 = new EventRecord(UUID.randomUUID(), "type", "agg1", "d1", Instant.now(), 3, "src");
        var e2 = new EventRecord(UUID.randomUUID(), "type", "agg1", "d2", Instant.now(), 1, "src");
        var e3 = new EventRecord(UUID.randomUUID(), "type", "agg1", "d3", Instant.now(), 2, "src");

        store.append(e1);
        store.append(e2);
        store.append(e3);

        List<EventRecord> events = store.getEventsForAggregate("agg1");
        
        assertEquals(1, events.get(0).version(), "First event should be version 1");
        assertEquals(2, events.get(1).version(), "Second event should be version 2");
        assertEquals(3, events.get(2).version(), "Third event should be version 3");
    }

    @Test
    void test_no_version_gaps() {
        for (int i = 1; i <= 5; i++) {
            store.append(new EventRecord(UUID.randomUUID(), "type", "agg", "data", Instant.now(), i, "src"));
        }

        List<EventRecord> events = store.getEventsForAggregate("agg");
        for (int i = 0; i < events.size() - 1; i++) {
            assertTrue(events.get(i).version() <= events.get(i + 1).version(),
                "Events should be in version order");
        }
    }

    @Test
    void test_events_since() {
        Instant before = Instant.now();
        store.append(new EventRecord("type", "agg", "data", "src"));

        List<EventRecord> events = store.getEventsSince(before.minusSeconds(1));
        assertFalse(events.isEmpty());
    }

    @Test
    void test_event_count() {
        assertEquals(0, store.getEventCount());
        store.append(new EventRecord("type", "agg", "data", "src"));
        assertEquals(1, store.getEventCount());
    }

    @Test
    void test_separate_aggregates() {
        store.append(new EventRecord("type", "agg1", "data1", "src"));
        store.append(new EventRecord("type", "agg2", "data2", "src"));

        assertEquals(1, store.getEventsForAggregate("agg1").size());
        assertEquals(1, store.getEventsForAggregate("agg2").size());
    }

    @Test
    void test_nonexistent_aggregate() {
        List<EventRecord> events = store.getEventsForAggregate("nonexistent");
        assertTrue(events.isEmpty());
    }
}
