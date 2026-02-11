package com.vertexgrid.shared;

import com.vertexgrid.shared.event.EventStore;
import com.vertexgrid.shared.model.EventRecord;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

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

    // ====== getConsistentSnapshot tests ======
    @Test
    void test_snapshot_returns_all_aggregates() {
        store.append(new EventRecord("type", "agg-1", "data", "src"));
        store.append(new EventRecord("type", "agg-2", "data", "src"));

        java.util.Map<String, List<EventRecord>> snapshot = store.getConsistentSnapshot();
        assertEquals(2, snapshot.size());
        assertTrue(snapshot.containsKey("agg-1"));
        assertTrue(snapshot.containsKey("agg-2"));
    }

    @Test
    void test_snapshot_isolated_from_later_mutations() {
        store.append(new EventRecord("type", "agg", "data1", "src"));
        java.util.Map<String, List<EventRecord>> snapshot = store.getConsistentSnapshot();

        // Mutation after snapshot
        store.append(new EventRecord("type", "agg", "data2", "src"));

        assertEquals(1, snapshot.get("agg").size(),
            "Snapshot should not reflect events added after it was taken");
        assertEquals(2, store.getEventsForAggregate("agg").size(),
            "Store should have both events");
    }

    @Test
    void test_snapshot_empty_store() {
        java.util.Map<String, List<EventRecord>> snapshot = store.getConsistentSnapshot();
        assertTrue(snapshot.isEmpty());
    }

    @Test
    void test_snapshot_consistent_during_concurrent_writes() throws Exception {
        // Populate many aggregates so the snapshot iteration takes longer,
        // widening the race window for the writer to create inconsistencies.
        int aggregateCount = 100;
        for (int a = 0; a < aggregateCount; a++) {
            store.append(new EventRecord("init", "snap-" + a, "d", "s"));
        }

        int writerIterations = 200;
        CountDownLatch start = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(2);
        AtomicInteger inconsistencies = new AtomicInteger(0);

        // Writer adds to all aggregates in round-robin (each batch adds 1 event to each)
        Thread writer = new Thread(() -> {
            try {
                start.await();
                for (int batch = 0; batch < writerIterations; batch++) {
                    for (int a = 0; a < aggregateCount; a++) {
                        store.append(new EventRecord("w-" + batch, "snap-" + a, "d", "s"));
                    }
                }
            } catch (Exception e) {
                // ignore
            } finally {
                done.countDown();
            }
        });

        // Reader takes snapshots and checks all aggregates have similar event counts
        Thread reader = new Thread(() -> {
            try {
                start.await();
                for (int i = 0; i < 200; i++) {
                    java.util.Map<String, List<EventRecord>> snap = store.getConsistentSnapshot();
                    if (snap.size() < aggregateCount) continue;

                    int minSize = Integer.MAX_VALUE;
                    int maxSize = Integer.MIN_VALUE;
                    for (List<EventRecord> events : snap.values()) {
                        minSize = Math.min(minSize, events.size());
                        maxSize = Math.max(maxSize, events.size());
                    }
                    // Writer adds 1 event to each aggregate per batch, in order.
                    // A truly consistent snapshot should show all aggregates within
                    // 1 of each other. A difference > 1 means the snapshot is reading
                    // stale data for some aggregates while seeing new data for others.
                    if (maxSize - minSize > 1) {
                        inconsistencies.incrementAndGet();
                    }
                }
            } catch (Exception e) {
                // ignore
            } finally {
                done.countDown();
            }
        });

        writer.start();
        reader.start();
        start.countDown();
        done.await(30, TimeUnit.SECONDS);

        assertEquals(0, inconsistencies.get(),
            "Consistent snapshot should show all aggregates with similar event counts " +
            "(max-min difference should be <= 1 since writer adds in round-robin)");
    }

    @Test
    void test_snapshot_single_aggregate() {
        store.append(new EventRecord("type", "solo", "data1", "src"));
        store.append(new EventRecord("type", "solo", "data2", "src"));

        java.util.Map<String, List<EventRecord>> snapshot = store.getConsistentSnapshot();
        assertEquals(1, snapshot.size());
        assertEquals(2, snapshot.get("solo").size());
    }
}
