package com.vertexgrid.shared.event;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.function.Consumer;

/**
 * In-process event bus for VertexGrid domain events.
 *
 * Provides a simple publish/subscribe mechanism for decoupled communication
 * within a single service JVM. Used alongside Kafka for local event handling
 * before events are published externally (e.g., updating local caches,
 * triggering derived computations, audit logging).
 *
 * Note: This is NOT a replacement for Kafka cross-service messaging.
 * This handles only intra-service event dispatch.
 */
public class EventBus {

    private final Map<Class<?>, List<Consumer<?>>> handlers = new ConcurrentHashMap<>();

    
    // When a handler is registered for a base type (e.g., DomainEvent interface),
    // publish() only looks up handlers for the exact runtime class of the event
    // (e.g., VehicleMovedEvent). Handlers registered for superclasses or interfaces
    // are never invoked, breaking the expected polymorphic dispatch pattern.
    //
    // Example: subscribe(DomainEvent.class, auditLogger) will never receive a
    // VehicleMovedEvent even though VehicleMovedEvent implements DomainEvent.
    //
    // This affects the compliance service's audit trail (registers for DomainEvent
    // but never receives concrete events) and analytics aggregation.
    // Category: Event Sourcing
    // Fix: Walk the class hierarchy and interface tree in publish():
    //   Set<Class<?>> types = new HashSet<>();
    //   for (Class<?> c = event.getClass(); c != null; c = c.getSuperclass()) {
    //       types.add(c);
    //       Collections.addAll(types, c.getInterfaces());
    //   }
    //   for (Class<?> type : types) { /* invoke handlers for type */ }

    /**
     * Registers a handler for events of the specified type.
     *
     * @param eventType the event class to subscribe to
     * @param handler   the consumer to invoke when events of this type are published
     */
    @SuppressWarnings("unchecked")
    public <T> void subscribe(Class<T> eventType, Consumer<T> handler) {
        handlers.computeIfAbsent(eventType, k -> new CopyOnWriteArrayList<>())
            .add(handler);
    }

    /**
     * Publishes an event to all registered handlers.
     *
     * @param event the event to publish
     */
    @SuppressWarnings("unchecked")
    public <T> void publish(T event) {
        if (event == null) {
            return;
        }

        
        // Handlers registered for superclasses or interfaces are never invoked.
        List<Consumer<?>> eventHandlers = handlers.get(event.getClass());
        if (eventHandlers != null) {
            for (Consumer handler : eventHandlers) {
                handler.accept(event);
            }
        }
        // Fix: Walk the class hierarchy:
        // Set<Class<?>> types = new LinkedHashSet<>();
        // for (Class<?> c = event.getClass(); c != null; c = c.getSuperclass()) {
        //     types.add(c);
        //     Collections.addAll(types, c.getInterfaces());
        // }
        // for (Class<?> type : types) {
        //     List<Consumer<?>> h = handlers.get(type);
        //     if (h != null) {
        //         for (Consumer handler : h) {
        //             handler.accept(event);
        //         }
        //     }
        // }
    }

    /**
     * Removes all registered handlers.
     */
    public void clear() {
        handlers.clear();
    }

    /**
     * Returns the number of event types that have registered handlers.
     */
    public int getRegisteredTypeCount() {
        return handlers.size();
    }

    /**
     * Returns the number of handlers registered for a specific event type.
     *
     * @param eventType the event class to check
     * @return the number of handlers, or 0 if none registered
     */
    public int getHandlerCount(Class<?> eventType) {
        List<Consumer<?>> eventHandlers = handlers.get(eventType);
        return eventHandlers != null ? eventHandlers.size() : 0;
    }
}
