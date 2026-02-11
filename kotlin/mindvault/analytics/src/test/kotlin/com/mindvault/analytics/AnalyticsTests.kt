package com.mindvault.analytics

import kotlinx.coroutines.*
import kotlinx.coroutines.test.runTest
import org.junit.jupiter.api.Test
import org.slf4j.LoggerFactory
import org.slf4j.MDC
import java.time.Instant
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertNotNull
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertContains

/**
 * Tests for AnalyticsService: aggregation, reporting, dashboard queries.
 *
 * Bug-specific tests:
 *   G3 - companion logger: this::class.java in companion resolves to Companion, not enclosing class
 *   J1 - MDC coroutine context: MDC (ThreadLocal) not propagated across withContext/async
 */
class AnalyticsTests {

    // =========================================================================
    // G3: companion logger uses wrong class name
    // =========================================================================

    @Test
    fun test_companion_logger_class() {
        
        // returns the companion class name (AnalyticsService$Companion), not the
        // enclosing class name (AnalyticsService).
        val service = AnalyticsServiceStub()
        val loggerName = service.getLoggerName()

        assertFalse(
            loggerName.contains("Companion"),
            "Logger name should NOT contain 'Companion', but was: $loggerName"
        )
    }

    @Test
    fun test_log_correct_class_name() {
        
        val service = AnalyticsServiceStub()
        val loggerName = service.getLoggerName()

        assertTrue(
            loggerName.endsWith("AnalyticsServiceStub"),
            "Logger name should end with 'AnalyticsServiceStub', but was: $loggerName"
        )
    }

    // =========================================================================
    // J1: MDC not propagated to coroutines
    // =========================================================================

    @Test
    fun test_mdc_propagated_in_coroutine() = runTest {
        
        // threads, the MDC values set in the original thread are lost.
        MDC.put("traceId", "trace-123")
        MDC.put("userId", "user-abc")

        var traceIdInIO: String? = null
        withContext(Dispatchers.IO) {
            
            traceIdInIO = MDC.get("traceId")
        }

        assertNotNull(
            traceIdInIO,
            "MDC traceId should be propagated to IO dispatcher (use MDCContext())"
        )
        assertEquals(
            "trace-123",
            traceIdInIO,
            "MDC traceId should retain its value across dispatcher switch"
        )
        MDC.clear()
    }

    @Test
    fun test_trace_id_preserved() = runTest {
        
        // Each async block starts with an empty MDC.
        MDC.put("requestId", "req-999")

        val results = coroutineScope {
            (1..3).map { i ->
                async(Dispatchers.IO) { 
                    val reqId = MDC.get("requestId")
                    "task-$i:$reqId"
                }
            }.map { it.await() }
        }

        
        for (result in results) {
            assertFalse(
                result.endsWith(":null"),
                "MDC requestId should be propagated to async blocks, but got: $result"
            )
        }
        MDC.clear()
    }

    // =========================================================================
    // Baseline: analytics aggregation, reporting, dashboard queries
    // =========================================================================

    @Test
    fun test_event_counter_increments() {
        val service = AnalyticsServiceStub()
        service.recordEvent("page_view", "u1")
        service.recordEvent("page_view", "u2")
        service.recordEvent("click", "u1")
        assertEquals(3, service.getEventCount(), "Should count 3 events")
    }

    @Test
    fun test_metric_aggregation() {
        val service = AnalyticsServiceStub()
        service.recordEvent("search", "u1")
        service.recordEvent("search", "u1")
        service.recordEvent("search", "u2")

        val metric = service.getMetric("events.search")
        assertNotNull(metric, "Metric for 'events.search' should exist")
        assertEquals(3.0, metric.value, "Metric value should be 3.0")
        assertEquals(3, metric.count, "Metric count should be 3")
    }

    @Test
    fun test_metric_not_found() {
        val service = AnalyticsServiceStub()
        val metric = service.getMetric("events.nonexistent")
        assertNull(metric, "Non-existent metric should return null")
    }

    @Test
    fun test_multiple_event_types() {
        val service = AnalyticsServiceStub()
        service.recordEvent("view", "u1")
        service.recordEvent("click", "u1")
        service.recordEvent("view", "u2")

        val viewMetric = service.getMetric("events.view")
        val clickMetric = service.getMetric("events.click")

        assertNotNull(viewMetric)
        assertNotNull(clickMetric)
        assertEquals(2.0, viewMetric.value)
        assertEquals(1.0, clickMetric.value)
    }

    @Test
    fun test_get_all_metrics() {
        val service = AnalyticsServiceStub()
        service.recordEvent("a", "u1")
        service.recordEvent("b", "u2")
        val all = service.getAllMetrics()
        assertEquals(2, all.size, "Should have 2 distinct metric types")
    }

    @Test
    fun test_report_generation() {
        val service = AnalyticsServiceStub()
        service.recordEvent("view", "u1")
        service.recordEvent("click", "u1")

        val report = service.generateReport("u1", Instant.MIN, Instant.MAX)
        assertEquals("u1", report["userId"])
        assertNotNull(report["metrics"])
        assertNotNull(report["generatedAt"])
    }

    @Test
    fun test_report_empty_period() {
        val service = AnalyticsServiceStub()
        service.recordEvent("view", "u1")

        // Query a period that excludes all events
        val futureStart = Instant.now().plusSeconds(3600)
        val futureEnd = Instant.now().plusSeconds(7200)
        val report = service.generateReport("u1", futureStart, futureEnd)

        @Suppress("UNCHECKED_CAST")
        val metrics = report["metrics"] as List<*>
        assertTrue(metrics.isEmpty(), "Report for future period should have no metrics")
    }

    @Test
    fun test_event_properties_stored() {
        val event = AnalyticsEventLocal(
            eventType = "purchase",
            userId = "u1",
            documentId = "doc1",
            properties = mapOf("amount" to "49.99", "currency" to "USD")
        )
        assertEquals("purchase", event.eventType)
        assertEquals("49.99", event.properties["amount"])
        assertEquals("USD", event.properties["currency"])
    }

    @Test
    fun test_aggregate_metric_defaults() {
        val metric = AggregateMetricLocal("test.metric", 0.0, 0)
        assertEquals(0.0, metric.value)
        assertEquals(0, metric.count)
        assertNotNull(metric.lastUpdated)
    }

    @Test
    fun test_concurrent_event_recording() = runTest {
        val service = AnalyticsServiceStub()
        coroutineScope {
            repeat(100) { i ->
                launch {
                    service.recordEvent("concurrent", "user-$i")
                }
            }
        }
        assertEquals(100, service.getEventCount(), "All 100 concurrent events should be recorded")
    }

    @Test
    fun test_event_type_in_metric_name() {
        val service = AnalyticsServiceStub()
        service.recordEvent("download", "u1")
        val metric = service.getMetric("events.download")
        assertNotNull(metric)
        assertTrue(metric.metricName.contains("download"), "Metric name should contain event type")
    }

    @Test
    fun test_report_contains_user_id() {
        val service = AnalyticsServiceStub()
        val report = service.generateReport("user-xyz", Instant.MIN, Instant.MAX)
        assertEquals("user-xyz", report["userId"])
    }

    @Test
    fun test_metric_last_updated_recent() {
        val before = Instant.now()
        val service = AnalyticsServiceStub()
        service.recordEvent("timing", "u1")
        val metric = service.getMetric("events.timing")
        assertNotNull(metric)
        assertTrue(
            !metric.lastUpdated.isBefore(before),
            "lastUpdated should be at or after the time the event was recorded"
        )
    }

    @Test
    fun test_event_count_starts_at_zero() {
        val service = AnalyticsServiceStub()
        assertEquals(0, service.getEventCount(), "Event count should start at 0")
    }

    @Test
    fun test_get_all_metrics_empty() {
        val service = AnalyticsServiceStub()
        val all = service.getAllMetrics()
        assertTrue(all.isEmpty(), "New service should have no metrics")
    }

    @Test
    fun test_metric_count_increments() {
        val service = AnalyticsServiceStub()
        service.recordEvent("click", "u1")
        service.recordEvent("click", "u2")
        service.recordEvent("click", "u3")
        val metric = service.getMetric("events.click")
        assertNotNull(metric)
        assertEquals(3, metric.count, "Metric count should be 3 after 3 events")
    }

    @Test
    fun test_report_structure_keys() {
        val service = AnalyticsServiceStub()
        service.recordEvent("view", "u1")
        val report = service.generateReport("u1", Instant.MIN, Instant.MAX)
        assertTrue(report.containsKey("userId"), "Report should contain userId key")
        assertTrue(report.containsKey("period"), "Report should contain period key")
        assertTrue(report.containsKey("metrics"), "Report should contain metrics key")
        assertTrue(report.containsKey("generatedAt"), "Report should contain generatedAt key")
    }

    @Test
    fun test_event_properties_default_empty() {
        val event = AnalyticsEventLocal(eventType = "view", userId = "u1")
        assertTrue(event.properties.isEmpty(), "Default properties should be empty")
        assertNull(event.documentId, "Default documentId should be null")
    }

    @Test
    fun test_event_timestamp_set() {
        val before = Instant.now()
        val event = AnalyticsEventLocal(eventType = "action", userId = "u1")
        val after = Instant.now()
        assertTrue(!event.timestamp.isBefore(before), "Timestamp should be at or after creation")
        assertTrue(!event.timestamp.isAfter(after), "Timestamp should be at or before check time")
    }

    @Test
    fun test_multiple_metric_types_independent() {
        val service = AnalyticsServiceStub()
        service.recordEvent("view", "u1")
        service.recordEvent("view", "u1")
        service.recordEvent("click", "u1")
        val allMetrics = service.getAllMetrics()
        assertEquals(2, allMetrics.size, "Should have 2 distinct metric types: view and click")
        val viewMetric = allMetrics["events.view"]
        val clickMetric = allMetrics["events.click"]
        assertNotNull(viewMetric)
        assertNotNull(clickMetric)
        assertEquals(2.0, viewMetric.value)
        assertEquals(1.0, clickMetric.value)
    }

    // =========================================================================
    // Local stubs simulating buggy production code
    // =========================================================================

    data class AnalyticsEventLocal(
        val eventType: String,
        val userId: String,
        val documentId: String? = null,
        val timestamp: Instant = Instant.now(),
        val properties: Map<String, String> = emptyMap()
    )

    data class AggregateMetricLocal(
        val metricName: String,
        val value: Double,
        val count: Long,
        val lastUpdated: Instant = Instant.now()
    )

    class AnalyticsServiceStub {

        
        companion object {
            
            private val logger = LoggerFactory.getLogger(this::class.java)
        }

        private val eventCounter = AtomicLong(0)
        private val metrics = ConcurrentHashMap<String, AggregateMetricLocal>()

        fun getLoggerName(): String = logger.name 

        fun recordEvent(eventType: String, userId: String) {
            eventCounter.incrementAndGet()
            val metricName = "events.$eventType"
            metrics.compute(metricName) { _, existing ->
                if (existing != null) {
                    existing.copy(
                        value = existing.value + 1.0,
                        count = existing.count + 1,
                        lastUpdated = Instant.now()
                    )
                } else {
                    AggregateMetricLocal(metricName, 1.0, 1)
                }
            }
        }

        fun getEventCount(): Long = eventCounter.get()

        fun getMetric(name: String): AggregateMetricLocal? = metrics[name]

        fun getAllMetrics(): Map<String, AggregateMetricLocal> = metrics.toMap()

        fun generateReport(userId: String, from: Instant, to: Instant): Map<String, Any> {
            logger.info("Generating report for user $userId") 
            val userMetrics = metrics.filter { (_, metric) ->
                metric.lastUpdated.isAfter(from) && metric.lastUpdated.isBefore(to)
            }
            return mapOf(
                "userId" to userId,
                "period" to "${from}_${to}",
                "metrics" to userMetrics.map { (name, metric) ->
                    mapOf("name" to name, "value" to metric.value, "count" to metric.count)
                },
                "generatedAt" to Instant.now().toString()
            )
        }
    }
}
