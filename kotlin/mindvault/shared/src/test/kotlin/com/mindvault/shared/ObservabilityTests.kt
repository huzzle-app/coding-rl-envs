package com.mindvault.shared

import kotlinx.coroutines.*
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertFailsWith

/**
 * Tests for observability: logging levels, CancellationException handling, plugin ordering.
 *
 * Bug-specific tests:
 *   J2 - Exception handler logs at DEBUG level instead of ERROR
 *   J4 - runCatching swallows CancellationException, breaking structured concurrency
 *   J3 - Kafka trace header not extracted, breaking distributed tracing
 *   J5 - CallLogging installed after StatusPages, so error responses are not logged
 */
class ObservabilityTests {

    // =========================================================================
    // J2: Exception handler logs at wrong level
    // =========================================================================

    @Test
    fun test_exception_handler_error_level() {
        
        // where log level is typically INFO or WARN
        val logging = LocalLogging()
        logging.handleException(RuntimeException("test error"))
        val lastLevel = logging.getLastLogLevel()
        assertEquals(
            "ERROR",
            lastLevel,
            "Exception handler should log at ERROR level, but logged at $lastLevel"
        )
    }

    @Test
    fun test_errors_visible() {
        
        val logging = LocalLogging()
        logging.setMinLogLevel("INFO")
        logging.handleException(IllegalStateException("critical failure"))
        assertTrue(
            logging.wasLastMessageVisible(),
            "Error messages should be visible at INFO log level (requires ERROR level logging)"
        )
    }

    // =========================================================================
    // J4: runCatching swallows CancellationException
    // =========================================================================

    @Test
    fun test_run_catching_rethrows_cancel() = runTest {
        
        // This breaks structured concurrency - cancelled coroutines continue running
        val logging = LocalLogging()
        assertFailsWith<CancellationException> {
            logging.safeCatching {
                throw CancellationException("coroutine cancelled")
            }
        }
    }

    @Test
    fun test_cancellation_not_swallowed() = runTest {
        
        val logging = LocalLogging()
        var cancellationSwallowed = true

        val job = launch {
            try {
                logging.safeCatching {
                    throw CancellationException("cancel me")
                }
                // If we get here, CancellationException was swallowed
                cancellationSwallowed = true
            } catch (e: CancellationException) {
                cancellationSwallowed = false
                throw e
            }
        }

        try { job.join() } catch (_: CancellationException) { }

        assertFalse(
            cancellationSwallowed,
            "safeCatching should rethrow CancellationException, not swallow it"
        )
    }

    // =========================================================================
    // J3: Kafka trace header extraction
    // =========================================================================

    @Test
    fun test_kafka_trace_header_extracted() {
        
        // Distributed trace context is lost when messages cross service boundaries
        val tracing = LocalKafkaTracing()
        val headers = mapOf("traceparent" to "00-abcdef1234567890-0123456789abcdef-01")
        val result = tracing.extractTraceContext(headers)
        assertTrue(
            result.traceExtracted,
            "Kafka consumer should extract trace headers from message for distributed tracing"
        )
    }

    @Test
    fun test_distributed_trace_continues() {
        
        val tracing = LocalKafkaTracing()
        val headers = mapOf("traceparent" to "00-abcdef1234567890-0123456789abcdef-01")
        val result = tracing.extractTraceContext(headers)
        assertNotNull(
            result.traceId,
            "Trace ID should be extracted from Kafka headers to continue distributed trace"
        )
        assertEquals(
            "abcdef1234567890",
            result.traceId,
            "Extracted trace ID should match the one from Kafka headers"
        )
    }

    // =========================================================================
    // J5: CallLogging plugin order
    // =========================================================================

    @Test
    fun test_call_logging_before_status() {
        
        // transformed by StatusPages are not logged
        val pipeline = LocalPipelineConfig()
        val loggingIndex = pipeline.getPluginInstallOrder("CallLogging")
        val statusPagesIndex = pipeline.getPluginInstallOrder("StatusPages")
        assertTrue(
            loggingIndex < statusPagesIndex,
            "CallLogging should be installed BEFORE StatusPages (order: $loggingIndex vs $statusPagesIndex)"
        )
    }

    @Test
    fun test_error_responses_logged() {
        
        val pipeline = LocalPipelineConfig()
        val result = pipeline.simulateErrorResponse(500)
        assertTrue(
            result.wasLogged,
            "500 error responses should be captured by CallLogging"
        )
    }

    // =========================================================================
    // Baseline: Logging fundamentals
    // =========================================================================

    @Test
    fun test_log_info_level() {
        val logging = LocalLogging()
        logging.info("test message")
        assertEquals("INFO", logging.getLastLogLevel())
    }

    @Test
    fun test_log_warn_level() {
        val logging = LocalLogging()
        logging.warn("warning message")
        assertEquals("WARN", logging.getLastLogLevel())
    }

    @Test
    fun test_safe_catching_returns_result_on_success() {
        val logging = LocalLogging()
        val result = logging.safeCatching { 42 }
        assertEquals(42, result.getOrNull(), "safeCatching should return result on success")
    }

    @Test
    fun test_safe_catching_wraps_exception() {
        val logging = LocalLogging()
        val result = logging.safeCatching { throw IllegalArgumentException("bad arg") }
        assertTrue(result.isFailure, "safeCatching should wrap non-cancellation exceptions")
    }

    @Test
    fun test_pipeline_has_call_logging() {
        val pipeline = LocalPipelineConfig()
        assertTrue(
            pipeline.hasPlugin("CallLogging"),
            "Pipeline should have CallLogging plugin installed"
        )
    }

    @Test
    fun test_pipeline_has_status_pages() {
        val pipeline = LocalPipelineConfig()
        assertTrue(
            pipeline.hasPlugin("StatusPages"),
            "Pipeline should have StatusPages plugin installed"
        )
    }

    @Test
    fun test_logging_message_preserved() {
        val logging = LocalLogging()
        logging.info("test message content")
        assertEquals("INFO", logging.getLastLogLevel())
    }

    @Test
    fun test_safe_catching_non_cancel_exception_wrapped() {
        val logging = LocalLogging()
        val result = logging.safeCatching { throw RuntimeException("runtime error") }
        assertTrue(result.isFailure, "Non-cancellation exception should be wrapped in Result.failure")
        assertTrue(result.exceptionOrNull() is RuntimeException)
    }

    @Test
    fun test_kafka_tracing_with_missing_header() {
        val tracing = LocalKafkaTracing()
        val headers = mapOf("other-header" to "value")
        val result = tracing.extractTraceContext(headers)
        // Without traceparent header, trace extraction should gracefully handle absence
        assertNotNull(result, "Should return a result even without trace headers")
    }

    @Test
    fun test_log_levels_ordered() {
        val levelOrder = mapOf("DEBUG" to 0, "INFO" to 1, "WARN" to 2, "ERROR" to 3)
        assertTrue(levelOrder["DEBUG"]!! < levelOrder["INFO"]!!, "DEBUG should be lower than INFO")
        assertTrue(levelOrder["INFO"]!! < levelOrder["WARN"]!!, "INFO should be lower than WARN")
        assertTrue(levelOrder["WARN"]!! < levelOrder["ERROR"]!!, "WARN should be lower than ERROR")
    }

    @Test
    fun test_pipeline_plugin_count() {
        val pipeline = LocalPipelineConfig()
        assertTrue(pipeline.hasPlugin("CallLogging"), "Pipeline should have CallLogging")
        assertTrue(pipeline.hasPlugin("StatusPages"), "Pipeline should have StatusPages")
    }

    @Test
    fun test_safe_catching_returns_success_value() {
        val logging = LocalLogging()
        val result = logging.safeCatching { "hello" }
        assertEquals("hello", result.getOrNull(), "safeCatching should return the value on success")
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    class LocalLogging {
        private var lastLogLevel = ""
        private var lastMessage = ""
        private var minLogLevel = "DEBUG"

        private val levelOrder = mapOf("DEBUG" to 0, "INFO" to 1, "WARN" to 2, "ERROR" to 3)

        
        fun handleException(e: Throwable) {
            lastLogLevel = "DEBUG" 
            lastMessage = "Unhandled exception: ${e.message}"
        }

        fun info(msg: String) { lastLogLevel = "INFO"; lastMessage = msg }
        fun warn(msg: String) { lastLogLevel = "WARN"; lastMessage = msg }

        fun getLastLogLevel(): String = lastLogLevel

        fun setMinLogLevel(level: String) { minLogLevel = level }

        fun wasLastMessageVisible(): Boolean {
            val lastOrd = levelOrder[lastLogLevel] ?: 0
            val minOrd = levelOrder[minLogLevel] ?: 0
            return lastOrd >= minOrd
        }

        
        inline fun <T> safeCatching(block: () -> T): Result<T> {
            return runCatching(block)
            
        }
    }

    
    data class TraceResult(val traceExtracted: Boolean, val traceId: String? = null)

    class LocalKafkaTracing {
        fun extractTraceContext(headers: Map<String, String>): TraceResult {
            
            return TraceResult(
                traceExtracted = false, 
                traceId = null 
            )
        }
    }

    data class ResponseLogResult(val wasLogged: Boolean, val statusCode: Int)

    class LocalPipelineConfig {
        
        private val pluginOrder = mapOf(
            "StatusPages" to 0, 
            "CallLogging" to 1  
        )

        fun getPluginInstallOrder(pluginName: String): Int {
            return pluginOrder[pluginName] ?: -1
        }

        fun hasPlugin(name: String): Boolean = name in pluginOrder

        fun simulateErrorResponse(statusCode: Int): ResponseLogResult {
            
            return ResponseLogResult(
                wasLogged = false, 
                statusCode = statusCode
            )
        }
    }
}
