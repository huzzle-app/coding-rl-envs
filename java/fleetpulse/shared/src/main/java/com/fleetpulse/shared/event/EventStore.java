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
 */
public class EventStore {

    private final Map<String, List<EventRecord>> eventsByAggregate = new ConcurrentHashMap<>();
    private final List<EventRecord> allEvents = new CopyOnWriteArrayList<>();

    
    // There is no isolation between concurrent readers and writers.
    // A reader calling getEventsForAggregate() while a writer is in the
    // middle of appendAll() can see a partial batch of events, leading to
    // inconsistent aggregate state reconstruction. For example, a dispatch
    // ticket that requires both "assigned" and "route-set" events to be
    // valid could be reconstructed with only "assigned", causing the
    // dispatch service to send a driver without a route.
    // Category: Event Sourcing
    // Fix: Use ReadWriteLock to provide snapshot isolation, or use
    //      synchronized blocks around batch operations, or implement
    //      event version validation in getEventsForAggregate().

    /**
     * Appends a single event to the store.
     *
     * @param event the event to store
     */
    public void append(EventRecord event) {
        
        // before the full batch in appendAll() completes
        allEvents.add(event);
        eventsByAggregate.computeIfAbsent(event.aggregateId(), k -> new CopyOnWriteArrayList<>())
            .add(event);
    }

    
    // instead of using batch operations. Each call to append() adds to both
    // allEvents and the per-aggregate list individually, resulting in N
    // CopyOnWriteArrayList copy operations for N events. For the tracking
    // service processing 1000 GPS events per second, this creates massive
    // garbage collection pressure and throughput bottlenecks.
    // Category: Event Sourcing
    // Fix: Collect all events, then add them in bulk:
    //   allEvents.addAll(events);
    //   events.stream().collect(Collectors.groupingBy(EventRecord::aggregateId))
    //       .forEach((aggId, aggEvents) ->
    //           eventsByAggregate.computeIfAbsent(aggId, k -> new CopyOnWriteArrayList<>())
    //               .addAll(aggEvents));

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
            
            // Each append() triggers a full array copy in CopyOnWriteArrayList,
            // making this O(n^2) for n events.
            append(event);
        }
    }

    
    // When concurrent writes occur for the same aggregate, events may be
    // stored in arrival order rather than version order. Replaying events
    // in the wrong order produces incorrect aggregate state. For example,
    // a vehicle's "fuel-level-updated(80%)" at version 3 followed by
    // "fuel-level-updated(50%)" at version 2 would show 50% instead of 80%.
    // Category: Event Sourcing
    // Fix: Sort events by version before returning:
    //   return events.stream()
    //       .sorted(Comparator.comparingInt(EventRecord::version))
    //       .collect(Collectors.toList());

    /**
     * Returns all events for a given aggregate, for state reconstruction.
     *
     * @param aggregateId the aggregate identifier
     * @return list of events for the aggregate (may be in wrong order - see BUG E8)
     */
    public List<EventRecord> getEventsForAggregate(String aggregateId) {
        List<EventRecord> events = eventsByAggregate.getOrDefault(aggregateId, List.of());
        
        // order which could differ from version order if concurrent writes occurred.
        return new ArrayList<>(events);
        // Fix: return events.stream()
        //          .sorted(Comparator.comparingInt(EventRecord::version))
        //          .collect(Collectors.toList());
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
