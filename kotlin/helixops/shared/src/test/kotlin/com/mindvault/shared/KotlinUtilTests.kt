package com.helixops.shared

import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull

/**
 * Tests for Kotlin-specific utilities: typealias SAM conversion, value class syntax.
 *
 * Bug-specific tests:
 *   K7 - typealias for suspend lambda breaks SAM conversion from Java interop
 *   K8 - Uses deprecated `inline class` syntax instead of @JvmInline value class
 */
class KotlinUtilTests {

    // =========================================================================
    // K7: typealias suspend lambda SAM conversion
    // =========================================================================

    @Test
    fun test_suspend_lambda_wrapper() = runTest {
        
        // typealiases for suspend lambdas don't support SAM conversion from Java
        // Should use a functional interface (fun interface) instead
        val handler = EventHandlerFactoryFixture()
        assertTrue(
            handler.usesFunInterface(),
            "Suspend handler should use fun interface, not typealias, for SAM conversion support"
        )
    }

    @Test
    fun test_sam_conversion_correct() = runTest {
        
        // using SAM conversion syntax
        val handler = EventHandlerFactoryFixture()
        val canConvertFromJava = handler.supportsJavaSamConversion()
        assertTrue(
            canConvertFromJava,
            "Handler type should support SAM conversion from Java callers"
        )
    }

    // =========================================================================
    // K8: Deprecated inline class syntax
    // =========================================================================

    @Test
    fun test_value_class_jvm_inline() {
        
        // Should use @JvmInline value class
        val classInfo = ValueClassInfoFixture()
        assertTrue(
            classInfo.usesJvmInlineAnnotation("UserId"),
            "UserId should use @JvmInline value class, not deprecated inline class syntax"
        )
    }

    @Test
    fun test_no_boxing_on_boundary() {
        
        val classInfo = ValueClassInfoFixture()
        assertFalse(
            classInfo.usesDeprecatedInlineKeyword("UserId"),
            "UserId should NOT use deprecated 'inline class' keyword"
        )
        assertTrue(
            classInfo.usesJvmInlineAnnotation("DocumentId"),
            "DocumentId should use @JvmInline value class (correct pattern)"
        )
    }

    // =========================================================================
    // Baseline: Value class and utility fundamentals
    // =========================================================================

    @Test
    fun test_user_id_wraps_string() {
        val id = UserIdFixture("user-123")
        assertEquals("user-123", id.value, "UserId should wrap the string value")
    }

    @Test
    fun test_document_id_wraps_string() {
        val id = DocumentIdFixture("doc-456")
        assertEquals("doc-456", id.value, "DocumentId should wrap the string value")
    }

    @Test
    fun test_value_class_equality() {
        val a = DocumentIdFixture("id1")
        val b = DocumentIdFixture("id1")
        assertEquals(a, b, "Value classes with same value should be equal")
    }

    @Test
    fun test_value_class_different() {
        val a = DocumentIdFixture("id1")
        val b = DocumentIdFixture("id2")
        assertFalse(a == b, "Value classes with different values should not be equal")
    }

    @Test
    fun test_event_handler_callable() = runTest {
        var called = false
        val handler: suspend (String) -> Unit = { called = true }
        handler("test")
        assertTrue(called, "Suspend lambda handler should be callable")
    }

    @Test
    fun test_node_id_wraps_string() {
        val id = NodeIdFixture("node-789")
        assertEquals("node-789", id.value, "NodeId should wrap the string value")
    }

    @Test
    fun test_user_id_equality() {
        val a = UserIdFixture("user-1")
        val b = UserIdFixture("user-1")
        assertEquals(a, b, "UserIds with same value should be equal")
    }

    @Test
    fun test_document_id_different_values() {
        val a = DocumentIdFixture("doc-1")
        val b = DocumentIdFixture("doc-2")
        assertFalse(a == b, "DocumentIds with different values should not be equal")
    }

    @Test
    fun test_node_id_equality() {
        val a = NodeIdFixture("node-1")
        val b = NodeIdFixture("node-1")
        assertEquals(a, b, "NodeIds with the same value should be equal")
    }

    @Test
    fun test_user_id_different_values() {
        val a = UserIdFixture("user-a")
        val b = UserIdFixture("user-b")
        assertFalse(a == b, "UserIds with different values should not be equal")
    }

    @Test
    fun test_document_id_toString_contains_value() {
        val id = DocumentIdFixture("doc-99")
        assertTrue(id.toString().contains("doc-99"), "DocumentId toString should contain its value")
    }

    // =========================================================================
    // Deterministic fixtures mirroring buggy production paths
    // =========================================================================

    class EventHandlerFactoryFixture {
        fun usesFunInterface(): Boolean {
            
            return false 
        }

        fun supportsJavaSamConversion(): Boolean {
            
            return false 
        }
    }

    class ValueClassInfoFixture {
        
        private val classAnnotations = mapOf(
            "UserId" to setOf("inline"), 
            "DocumentId" to setOf("JvmInline", "value"), // Correct
            "NodeId" to setOf("JvmInline", "value") // Correct
        )

        fun usesJvmInlineAnnotation(className: String): Boolean {
            val annotations = classAnnotations[className] ?: return false
            
            return "JvmInline" in annotations
        }

        fun usesDeprecatedInlineKeyword(className: String): Boolean {
            val annotations = classAnnotations[className] ?: return false
            
            return "inline" in annotations && "JvmInline" !in annotations
        }
    }

    // Simulating value classes locally
    data class UserIdFixture(val value: String) 

    @JvmInline
    value class DocumentIdFixture(val value: String) // Correct

    @JvmInline
    value class NodeIdFixture(val value: String) // Correct
}
