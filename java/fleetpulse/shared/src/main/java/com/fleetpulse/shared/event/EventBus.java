package com.fleetpulse.shared.event;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.function.Consumer;

/**
 * In-process event bus for FleetPulse domain events.
 *
 * Provides a simple publish/subscribe mechanism for decoupled communication
 * within a single service JVM. Used alongside Kafka for local event handling
 * before events are published externally (e.g., updating local caches,
 * triggering derived computations, audit logging).
 *
 * Note: This is NOT a replacement for Kafka cross-service messaging.
 * This handles only intra-service event dispatch.
 *
 * Bugs: E1
 * Categories: Event Sourcing
 */
public class EventBus {

    private final Map<Class<?>, List<Consumer<?>>> handlers = new ConcurrentHashMap<>();

    // Bug E1: publish() only looks up handlers for the exact runtime class of the event.
    // Handlers registered for superclasses or interfaces are never invoked, breaking
    // the expected polymorphic dispatch pattern.
    // Category: Event Sourcing

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

        List<Consumer<?>> eventHandlers = handlers.get(event.getClass());
        if (eventHandlers != null) {
            for (Consumer handler : eventHandlers) {
                handler.accept(event);
            }
        }
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
