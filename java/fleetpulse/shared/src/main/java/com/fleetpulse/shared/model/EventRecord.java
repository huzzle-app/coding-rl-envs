package com.fleetpulse.shared.model;

import java.time.Instant;
import java.util.UUID;

/**
 * Immutable event record for FleetPulse event sourcing infrastructure.
 *
 * Used by the EventStore to persist domain events across all services:
 * vehicle state changes, dispatch assignments, route completions,
 * billing charges, compliance violations, etc.
 *
 * Implemented as a Java 21 record for immutability and compact syntax.
 */
public record EventRecord(
    UUID eventId,
    String eventType,
    String aggregateId,
    String payload,
    Instant timestamp,
    int version,
    String source
) {
    
    // Java records auto-generate equals/hashCode using component values.
    // For String fields this works correctly, but the byte[] overload
    // constructor below stores payload as a String via new String(bytes).
    // If this record ever changes payload to byte[], the auto-generated
    // equals() would use == reference comparison (not Arrays.equals()),
    // causing two records with identical byte content to be unequal.
    // This is a latent design issue - any future refactoring to byte[]
    // would silently break event deduplication and replay logic.
    // Category: Templates/Modern Java (record semantics)
    // Fix: If payload becomes byte[], override equals/hashCode to use
    //      Arrays.equals()/Arrays.hashCode() for the byte[] field, or
    //      wrap byte[] in a ByteBuffer or custom value type.

    /**
     * Compact canonical constructor with validation.
     */
    public EventRecord {
        if (eventId == null) {
            throw new IllegalArgumentException("eventId must not be null");
        }
        if (eventType == null || eventType.isBlank()) {
            throw new IllegalArgumentException("eventType must not be blank");
        }
        if (aggregateId == null || aggregateId.isBlank()) {
            throw new IllegalArgumentException("aggregateId must not be blank");
        }
    }

    /**
     * Convenience constructor that auto-generates eventId and timestamp.
     */
    public EventRecord(String eventType, String aggregateId, String payload, String source) {
        this(UUID.randomUUID(), eventType, aggregateId, payload, Instant.now(), 1, source);
    }

    /**
     * Creates a new EventRecord with an incremented version number.
     *
     * @param nextVersion the version number for the new event
     * @return a new EventRecord with the specified version
     */
    public EventRecord withVersion(int nextVersion) {
        return new EventRecord(eventId, eventType, aggregateId, payload, timestamp, nextVersion, source);
    }
}
