package com.mindvault.shared

import kotlinx.coroutines.*
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNotEquals

/**
 * Tests for the EventBus publish/subscribe system.
 *
 * Bug-specific tests:
 *   A9 - callbackFlow missing awaitClose: flow completes immediately instead of staying open
 *   A10 - Dispatchers.Unconfined in publish: handler runs on calling thread, not thread-safe
 */
class EventBusTests {

    // =========================================================================
    // A9: callbackFlow without awaitClose
    // =========================================================================

    @Test
    fun test_callback_flow_await_close() = runTest {
        
        // completes immediately after subscribe - no events are ever received
        val bus = LocalEventBus()
        val hasAwaitClose = bus.eventFlowHasAwaitClose("test_event")
        assertTrue(
            hasAwaitClose,
            "callbackFlow must call awaitClose {} to keep the flow open for events"
        )
    }

    @Test
    fun test_flow_completes_properly() = runTest {
        
        val bus = LocalEventBus()
        val events = mutableListOf<LocalDomainEvent>()

        val collectJob = launch {
            bus.eventFlow("test_event")
                .take(1)
                .collect { events.add(it) }
        }

        delay(50)
        bus.publish(LocalDomainEvent("1", "test_event", "payload1"))
        delay(50)
        collectJob.cancelAndJoin()

        assertTrue(
            events.isNotEmpty(),
            "Flow should receive events after subscribing; got ${events.size} events (expected >= 1)"
        )
    }

    // =========================================================================
    // A10: Dispatchers.Unconfined for handler execution
    // =========================================================================

    @Test
    fun test_no_unconfined_dispatcher() = runTest {
        
        // Making handler execution non-deterministic and not thread-safe
        val bus = LocalEventBus()
        assertFalse(
            bus.usesUnconfinedDispatcher(),
            "EventBus.publish() should NOT use Dispatchers.Unconfined; use Default or IO"
        )
    }

    @Test
    fun test_thread_safe_state_access() = runTest {
        
        // can cause data races in handlers that access shared mutable state
        val bus = LocalEventBus()
        val counter = java.util.concurrent.atomic.AtomicInteger(0)
        var raceDetected = false

        bus.subscribe("counter_event") {
            val current = counter.get()
            // Yield to expose potential race condition with Unconfined
            delay(1)
            if (counter.compareAndSet(current, current + 1).not()) {
                raceDetected = true
            }
            counter.incrementAndGet()
        }

        val jobs = (1..20).map { i ->
            launch(Dispatchers.Default) {
                bus.publish(LocalDomainEvent("$i", "counter_event", "data"))
            }
        }
        jobs.forEach { it.join() }

        assertFalse(
            bus.usesUnconfinedDispatcher(),
            "Dispatcher should be confined to prevent thread-safety issues"
        )
    }

    // =========================================================================
    // Baseline: EventBus publish/subscribe fundamentals
    // =========================================================================

    @Test
    fun test_subscribe_and_publish() = runTest {
        val bus = LocalEventBus()
        var received: LocalDomainEvent? = null
        bus.subscribe("user_joined") { received = it }
        bus.publish(LocalDomainEvent("1", "user_joined", "user123"))
        assertNotNull(received, "Handler should receive published event")
        assertEquals("user_joined", received?.type)
    }

    @Test
    fun test_multiple_subscribers() = runTest {
        val bus = LocalEventBus()
        val received = mutableListOf<String>()
        bus.subscribe("document_created") { received.add("handler1") }
        bus.subscribe("document_created") { received.add("handler2") }
        bus.publish(LocalDomainEvent("1", "document_created", "doc1"))
        assertEquals(2, received.size, "Both subscribers should receive the event")
    }

    @Test
    fun test_events_filtered_by_type() = runTest {
        val bus = LocalEventBus()
        val received = mutableListOf<String>()
        bus.subscribe("type_a") { received.add("a") }
        bus.subscribe("type_b") { received.add("b") }
        bus.publish(LocalDomainEvent("1", "type_a", "data"))
        assertEquals(listOf("a"), received, "Only type_a handler should fire")
    }

    @Test
    fun test_event_has_timestamp() {
        val event = LocalDomainEvent("1", "test", "payload")
        assertTrue(event.timestamp > 0, "Event should have a valid timestamp")
    }

    @Test
    fun test_event_id_unique() {
        val event1 = LocalDomainEvent("1", "test", "a")
        val event2 = LocalDomainEvent("2", "test", "b")
        assertNotEquals(event1.id, event2.id, "Events should have unique IDs")
    }

    @Test
    fun test_no_subscribers_no_error() = runTest {
        val bus = LocalEventBus()
        // Publishing with no subscribers should not throw
        bus.publish(LocalDomainEvent("1", "orphan_event", "data"))
    }

    @Test
    fun test_subscribe_returns_unit() = runTest {
        val bus = LocalEventBus()
        val result = bus.subscribe("test") { /* noop */ }
        // Just verifying it doesn't throw or return unexpected type
        assertEquals(Unit, result)
    }

    @Test
    fun test_event_payload_preserved() = runTest {
        val bus = LocalEventBus()
        var receivedPayload = ""
        bus.subscribe("payload_test") { receivedPayload = it.payload }
        bus.publish(LocalDomainEvent("1", "payload_test", "important_data"))
        assertEquals("important_data", receivedPayload, "Event payload should be preserved")
    }

    @Test
    fun test_publish_multiple_events() = runTest {
        val bus = LocalEventBus()
        val events = mutableListOf<String>()
        bus.subscribe("multi") { events.add(it.payload) }
        bus.publish(LocalDomainEvent("1", "multi", "first"))
        bus.publish(LocalDomainEvent("2", "multi", "second"))
        bus.publish(LocalDomainEvent("3", "multi", "third"))
        assertEquals(3, events.size, "All three events should be received")
    }

    @Test
    fun test_event_type_is_string() {
        val event = LocalDomainEvent("1", "document_created", "payload")
        assertEquals("document_created", event.type, "Event type should be a string")
    }

    @Test
    fun test_subscribe_different_types_independent() = runTest {
        val bus = LocalEventBus()
        val typeA = mutableListOf<String>()
        val typeB = mutableListOf<String>()
        bus.subscribe("a") { typeA.add(it.id) }
        bus.subscribe("b") { typeB.add(it.id) }
        bus.publish(LocalDomainEvent("1", "a", ""))
        bus.publish(LocalDomainEvent("2", "b", ""))
        assertEquals(1, typeA.size)
        assertEquals(1, typeB.size)
    }

    @Test
    fun test_event_creation_defaults() {
        val event = LocalDomainEvent("id1", "type1", "pay1")
        assertTrue(event.timestamp > 0, "Timestamp should default to current time")
    }

    @Test
    fun test_event_id_preserved_through_handler() = runTest {
        val bus = LocalEventBus()
        var receivedId = ""
        bus.subscribe("id_test") { receivedId = it.id }
        bus.publish(LocalDomainEvent("evt-42", "id_test", "data"))
        assertEquals("evt-42", receivedId, "Event ID should be preserved through the handler")
    }

    @Test
    fun test_handler_receives_correct_type() = runTest {
        val bus = LocalEventBus()
        var receivedType = ""
        bus.subscribe("specific_type") { receivedType = it.type }
        bus.publish(LocalDomainEvent("1", "specific_type", "data"))
        assertEquals("specific_type", receivedType, "Handler should receive the correct event type")
    }

    @Test
    fun test_publish_order_preserved() = runTest {
        val bus = LocalEventBus()
        val order = mutableListOf<String>()
        bus.subscribe("ordered") { order.add(it.payload) }
        bus.publish(LocalDomainEvent("1", "ordered", "first"))
        bus.publish(LocalDomainEvent("2", "ordered", "second"))
        bus.publish(LocalDomainEvent("3", "ordered", "third"))
        assertEquals(listOf("first", "second", "third"), order, "Events should be received in publish order")
    }

    @Test
    fun test_event_timestamp_positive() {
        val event = LocalDomainEvent("id", "type", "payload")
        assertTrue(event.timestamp > 0, "Event timestamp should be a positive value")
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    data class LocalDomainEvent(
        val id: String,
        val type: String,
        val payload: String,
        val timestamp: Long = System.currentTimeMillis()
    )

    class LocalEventBus {
        private val listeners = mutableMapOf<String, MutableList<suspend (LocalDomainEvent) -> Unit>>()

        fun subscribe(eventType: String, handler: suspend (LocalDomainEvent) -> Unit) {
            listeners.getOrPut(eventType) { mutableListOf() }.add(handler)
        }

        
        fun eventFlow(eventType: String): Flow<LocalDomainEvent> = callbackFlow {
            val handler: suspend (LocalDomainEvent) -> Unit = { event ->
                trySend(event)
            }
            subscribe(eventType, handler)
            
        }

        fun eventFlowHasAwaitClose(eventType: String): Boolean {
            
            return false 
        }

        fun usesUnconfinedDispatcher(): Boolean {
            
            return true 
        }

        
        suspend fun publish(event: LocalDomainEvent) {
            withContext(Dispatchers.Unconfined) { 
                listeners[event.type]?.forEach { handler ->
                    handler(event)
                }
            }
        }
    }
}
