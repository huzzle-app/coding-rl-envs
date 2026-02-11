package com.helixops.shared

import kotlinx.coroutines.*
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNotEquals

/**
 * Tests for delegation patterns: companion serializers, interface delegation.
 *
 * Bug-specific tests:
 *   G4 - Companion object KSerializer has mutable lastDecoded state (race condition)
 *   G5 - Interface delegation with `this`: default method returns delegate's class, not wrapper's
 */
class DelegationTests {

    // =========================================================================
    // G4: Companion serializer with shared mutable state
    // =========================================================================

    @Test
    fun test_companion_serializer_stateless() {
        
        // Concurrent deserialization overwrites lastDecoded, causing races
        val serializer = EventSerializerFixture()
        assertFalse(
            serializer.hasMutableState(),
            "Companion KSerializer should be stateless; shared mutable state causes race conditions"
        )
    }

    @Test
    fun test_no_shared_mutable_state() = runTest {
        
        val serializer = EventSerializerFixture()
        val results = (1..20).map { i ->
            async(Dispatchers.Default) {
                val event = serializer.deserialize("""{"type":"type_$i","data":"data_$i"}""")
                // Check that the returned event matches what was deserialized
                event.type == "type_$i" && event.data == "data_$i"
            }
        }
        val allCorrect = results.awaitAll().all { it }
        assertTrue(
            allCorrect,
            "Concurrent deserialization should return correct results; shared mutable state causes corruption"
        )
    }

    // =========================================================================
    // G5: Interface delegation - `this` refers to delegate, not wrapper
    // =========================================================================

    @Test
    fun test_interface_delegation_this() {
        
        // refers to the delegate object, not the wrapping class
        val delegate = ListRepositoryFixture()
        val wrapper = DocumentRepositoryFixture(delegate)
        val className = wrapper.className()
        assertEquals(
            "DocumentRepositoryFixture",
            className,
            "className() should return wrapper's class name, not delegate's ('$className')"
        )
    }

    @Test
    fun test_delegation_correct_receiver() {
        
        // but className() uses `this` which resolves to delegate in `by` delegation
        val delegate = ListRepositoryFixture()
        val wrapper = DocumentRepositoryFixture(delegate)

        // count() should work correctly (delegates findAll() to delegate)
        assertEquals(3, wrapper.count(), "count() should return delegate's list size")

        // But className() returns the wrong class name because `this` is the delegate
        assertNotEquals(
            "ListRepositoryFixture",
            wrapper.className(),
            "className() should NOT return delegate's class name"
        )
    }

    // =========================================================================
    // Baseline: Delegation fundamentals
    // =========================================================================

    @Test
    fun test_delegate_findAll() {
        val delegate = ListRepositoryFixture()
        val items = delegate.findAll()
        assertEquals(3, items.size, "Delegate should return its items")
    }

    @Test
    fun test_wrapper_delegates_findAll() {
        val delegate = ListRepositoryFixture()
        val wrapper = DocumentRepositoryFixture(delegate)
        assertEquals(delegate.findAll(), wrapper.findAll(), "Wrapper should delegate findAll()")
    }

    @Test
    fun test_delegate_count_uses_findAll() {
        val delegate = ListRepositoryFixture()
        assertEquals(delegate.findAll().size, delegate.count(), "count() should match findAll().size")
    }

    @Test
    fun test_serializer_serialize_roundtrip() {
        val serializer = EventSerializerFixture()
        val event = EventFixture("test_type", "test_data")
        val json = serializer.serialize(event)
        val restored = serializer.deserialize(json)
        assertEquals(event.type, restored.type, "Type should survive serialization roundtrip")
        assertEquals(event.data, restored.data, "Data should survive serialization roundtrip")
    }

    @Test
    fun test_serializer_handles_special_chars() {
        val serializer = EventSerializerFixture()
        val event = EventFixture("type", "data with \"quotes\" and \\backslash")
        val json = serializer.serialize(event)
        assertNotNull(json, "Serializer should handle special characters")
    }

    @Test
    fun test_empty_repository() {
        val delegate = object : RepositoryFixture<String> {
            override fun findAll(): List<String> = emptyList()
        }
        assertEquals(0, delegate.count(), "Empty repository should have count 0")
    }

    @Test
    fun test_delegate_class_name_correct() {
        val delegate = ListRepositoryFixture()
        assertEquals("ListRepositoryFixture", delegate.className(), "Direct delegate className should be correct")
    }

    @Test
    fun test_serializer_deserialize_empty_fields() {
        val serializer = EventSerializerFixture()
        val json = """{"type":"","data":""}"""
        val event = serializer.deserialize(json)
        assertEquals("", event.type, "Empty type should deserialize to empty string")
        assertEquals("", event.data, "Empty data should deserialize to empty string")
    }

    @Test
    fun test_wrapper_count_matches_delegate() {
        val delegate = ListRepositoryFixture()
        val wrapper = DocumentRepositoryFixture(delegate)
        assertEquals(delegate.count(), wrapper.count(), "Wrapper count should match delegate count")
    }

    @Test
    fun test_serializer_serialize_produces_json() {
        val serializer = EventSerializerFixture()
        val event = EventFixture("my_type", "my_data")
        val json = serializer.serialize(event)
        assertTrue(json.contains("my_type"), "Serialized JSON should contain event type")
        assertTrue(json.contains("my_data"), "Serialized JSON should contain event data")
    }

    @Test
    fun test_delegate_findAll_returns_consistent_results() {
        val delegate = ListRepositoryFixture()
        val first = delegate.findAll()
        val second = delegate.findAll()
        assertEquals(first, second, "findAll() should return the same results on repeated calls")
    }

    @Test
    fun test_serializer_deserialize_known_json() {
        val serializer = EventSerializerFixture()
        val json = """{"type":"known","data":"payload"}"""
        val event = serializer.deserialize(json)
        assertEquals("known", event.type, "Deserialized type should match input JSON")
        assertEquals("payload", event.data, "Deserialized data should match input JSON")
    }

    // =========================================================================
    // Deterministic fixtures mirroring buggy production paths
    // =========================================================================

    data class EventFixture(val type: String, val data: String)

    class EventSerializerFixture {
        
        private var lastDecoded: EventFixture? = null 

        fun hasMutableState(): Boolean {
            
            return true 
        }

        fun serialize(event: EventFixture): String {
            return """{"type":"${event.type}","data":"${event.data}"}"""
        }

        fun deserialize(json: String): EventFixture {
            val typeMatch = Regex("\"type\":\"(.*?)\"").find(json)
            val dataMatch = Regex("\"data\":\"(.*?)\"").find(json)
            val event = EventFixture(
                typeMatch?.groupValues?.get(1) ?: "",
                dataMatch?.groupValues?.get(1) ?: ""
            )
            lastDecoded = event 
            return event
        }
    }

    
    interface RepositoryFixture<T> {
        fun findAll(): List<T>
        fun count(): Int = findAll().size
        fun className(): String = this::class.simpleName ?: "Unknown"
    }

    class ListRepositoryFixture : RepositoryFixture<String> {
        override fun findAll(): List<String> = listOf("doc1", "doc2", "doc3")
    }

    
    class DocumentRepositoryFixture(
        private val delegate: ListRepositoryFixture
    ) : RepositoryFixture<String> by delegate
    // className() will return "ListRepositoryFixture" instead of "DocumentRepositoryFixture"
}
