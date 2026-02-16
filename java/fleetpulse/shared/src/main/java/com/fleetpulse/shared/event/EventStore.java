package com.fleetpulse.shared.event;

import com.fleetpulse.shared.model.EventRecord;

import java.time.Instant;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.stream.Collectors;

/**
 * In-memory event store for FleetPulse event sourcing infrastructure.
 *
 * Stores domain events for aggregate reconstruction, event replay, and
 * audit trails. Used by dispatch (ticket lifecycle), tracking (GPS
 * event streams), billing (charge events), and compliance (audit log).
 *
 * In production, this would be backed by PostgreSQL with the events
 * table, but this in-memory implementation is used for testing and
 * as the contract definition for the persistence layer.
 *
 * Bugs: E5, E6, E8
 * Categories: Event Sourcing
 */
public class EventStore {

    private final Map<String, List<EventRecord>> eventsByAggregate = new ConcurrentHashMap<>();
    private final List<EventRecord> allEvents = new CopyOnWriteArrayList<>();

    // Bug E5: No isolation between concurrent readers and writers.
    // A reader calling getEventsForAggregate() while a writer is in the
    // middle of appendAll() can see a partial batch of events.
    // Category: Event Sourcing

    /**
     * Appends a single event to the store.
     *
     * @param event the event to store
     */
    public void append(EventRecord event) {
        allEvents.add(event);
        eventsByAggregate.computeIfAbsent(event.aggregateId(), k -> new CopyOnWriteArrayList<>())
            .add(event);
    }

    // Bug E6: appendAll iterates and calls append() individually instead of
    // using batch operations, resulting in N CopyOnWriteArrayList copy operations.
    // Category: Event Sourcing

    /**
     * Appends a batch of events to the store.
     *
     * @param events the events to store
     */
    public void appendAll(List<EventRecord> events) {
        if (events == null || events.isEmpty()) {
            return;
        }
        for (EventRecord event : events) {
            append(event);
        }
    }

    // Bug E8: Events may be stored in arrival order rather than version order
    // when concurrent writes occur for the same aggregate. Replaying events
    // in the wrong order produces incorrect aggregate state.
    // Category: Event Sourcing

    /**
     * Returns all events for a given aggregate, for state reconstruction.
     *
     * @param aggregateId the aggregate identifier
     * @return list of events for the aggregate (may be in wrong order)
     */
    public List<EventRecord> getEventsForAggregate(String aggregateId) {
        List<EventRecord> events = eventsByAggregate.getOrDefault(aggregateId, List.of());
        return new ArrayList<>(events);
    }

    /**
     * Returns all events that occurred after the given timestamp.
     * Used for incremental projections and catch-up subscriptions.
     *
     * @param since the cutoff timestamp (exclusive)
     * @return events with timestamp after 'since'
     */
    public List<EventRecord> getEventsSince(Instant since) {
        return allEvents.stream()
            .filter(e -> e.timestamp().isAfter(since))
            .collect(Collectors.toList());
    }

    /**
     * Returns all events of a specific type across all aggregates.
     *
     * @param eventType the event type to filter by
     * @return all events matching the type
     */
    public List<EventRecord> getEventsByType(String eventType) {
        return allEvents.stream()
            .filter(e -> eventType.equals(e.eventType()))
            .collect(Collectors.toList());
    }

    /**
     * Returns the total number of events in the store.
     */
    public int getEventCount() {
        return allEvents.size();
    }

    /**
     * Returns the number of distinct aggregates that have events.
     */
    public int getAggregateCount() {
        return eventsByAggregate.size();
    }

    /**
     * Clears all events from the store. Used in testing.
     */
    public void clear() {
        allEvents.clear();
        eventsByAggregate.clear();
    }
}
