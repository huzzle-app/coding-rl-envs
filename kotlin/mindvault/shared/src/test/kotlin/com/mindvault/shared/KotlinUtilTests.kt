package com.mindvault.shared

import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull

/**
 * Tests for Kotlin-specific utilities: typealias SAM conversion, value class syntax, sequences.
 *
 * Bug-specific tests:
 *   K2 - Sequence eagerly materialized with toList() instead of lazy terminal operation
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
        val handler = LocalEventHandlerFactory()
        assertTrue(
            handler.usesFunInterface(),
            "Suspend handler should use fun interface, not typealias, for SAM conversion support"
        )
    }

    @Test
    fun test_sam_conversion_correct() = runTest {
        
        // using SAM conversion syntax
        val handler = LocalEventHandlerFactory()
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
        val classInfo = LocalValueClassInfo()
        assertTrue(
            classInfo.usesJvmInlineAnnotation("UserId"),
            "UserId should use @JvmInline value class, not deprecated inline class syntax"
        )
    }

    @Test
    fun test_no_boxing_on_boundary() {
        
        val classInfo = LocalValueClassInfo()
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
    // K2: Sequence eagerly materialized instead of using terminal operation
    // =========================================================================

    @Test
    fun test_sequence_terminal_operation() {
        // Using .toList() in the middle of a sequence pipeline forces eager evaluation
        // Should use sequence terminal operations (first, count, take) to stay lazy
        val pipeline = LocalDocumentPipeline()
        val result = pipeline.findFirstMatch(List(10_000) { "doc_$it" }, "doc_9999")
        assertTrue(
            result.usedLazyEvaluation,
            "Pipeline should use lazy sequence evaluation, not eagerly materialize with toList()"
        )
    }

    @Test
    fun test_no_eager_collection_in_pipeline() {
        // Calling .toList() on a sequence of 100k items allocates the full list in memory
        // before filtering. Use .filter{}.first() on the sequence directly.
        val pipeline = LocalDocumentPipeline()
        val result = pipeline.findFirstMatch(List(100) { "item_$it" }, "item_0")
        assertTrue(
            result.evaluatedCount < 100,
            "Lazy pipeline should short-circuit after finding match; evaluated ${result.evaluatedCount} of 100"
        )
    }

    // =========================================================================
    // Baseline: Value class and utility fundamentals
    // =========================================================================

    @Test
    fun test_user_id_wraps_string() {
        val id = LocalUserId("user-123")
        assertEquals("user-123", id.value, "UserId should wrap the string value")
    }

    @Test
    fun test_document_id_wraps_string() {
        val id = LocalDocumentId("doc-456")
        assertEquals("doc-456", id.value, "DocumentId should wrap the string value")
    }

    @Test
    fun test_value_class_equality() {
        val a = LocalDocumentId("id1")
        val b = LocalDocumentId("id1")
        assertEquals(a, b, "Value classes with same value should be equal")
    }

    @Test
    fun test_value_class_different() {
        val a = LocalDocumentId("id1")
        val b = LocalDocumentId("id2")
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
        val id = LocalNodeId("node-789")
        assertEquals("node-789", id.value, "NodeId should wrap the string value")
    }

    @Test
    fun test_user_id_equality() {
        val a = LocalUserId("user-1")
        val b = LocalUserId("user-1")
        assertEquals(a, b, "UserIds with same value should be equal")
    }

    @Test
    fun test_document_id_different_values() {
        val a = LocalDocumentId("doc-1")
        val b = LocalDocumentId("doc-2")
        assertFalse(a == b, "DocumentIds with different values should not be equal")
    }

    @Test
    fun test_node_id_equality() {
        val a = LocalNodeId("node-1")
        val b = LocalNodeId("node-1")
        assertEquals(a, b, "NodeIds with the same value should be equal")
    }

    @Test
    fun test_user_id_different_values() {
        val a = LocalUserId("user-a")
        val b = LocalUserId("user-b")
        assertFalse(a == b, "UserIds with different values should not be equal")
    }

    @Test
    fun test_document_id_toString_contains_value() {
        val id = LocalDocumentId("doc-99")
        assertTrue(id.toString().contains("doc-99"), "DocumentId toString should contain its value")
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    class LocalEventHandlerFactory {
        fun usesFunInterface(): Boolean {
            
            return false 
        }

        fun supportsJavaSamConversion(): Boolean {
            
            return false 
        }
    }

    class LocalValueClassInfo {
        
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
    data class LocalUserId(val value: String)

    @JvmInline
    value class LocalDocumentId(val value: String) // Correct

    @JvmInline
    value class LocalNodeId(val value: String) // Correct

    // K2 bug: Sequence eagerly materialized with toList() before filtering
    data class PipelineResult(val usedLazyEvaluation: Boolean, val evaluatedCount: Int)

    class LocalDocumentPipeline {
        fun findFirstMatch(items: List<String>, target: String): PipelineResult {
            // BUG: calls .toList() on sequence, forcing eager materialization
            // Should use sequence terminal operations directly
            var evaluated = 0
            val result = items.asSequence()
                .map { evaluated++; it }
                .toList()  // BUG: materializes entire sequence eagerly
                .first { it == target }
            return PipelineResult(
                usedLazyEvaluation = false,  // BUG: should be true with lazy evaluation
                evaluatedCount = evaluated
            )
        }
    }
}
