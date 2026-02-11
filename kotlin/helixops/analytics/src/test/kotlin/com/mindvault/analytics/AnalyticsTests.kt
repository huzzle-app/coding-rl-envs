package com.helixops.analytics

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
        val service = AnalyticsServiceFixture()
        val loggerName = service.getLoggerName()

        assertFalse(
            loggerName.contains("Companion"),
            "Logger name should NOT contain 'Companion', but was: $loggerName"
        )
    }

    @Test
    fun test_log_correct_class_name() {
        
        val service = AnalyticsServiceFixture()
        val loggerName = service.getLoggerName()

        assertTrue(
            loggerName.endsWith("AnalyticsServiceFixture"),
            "Logger name should end with 'AnalyticsServiceFixture', but was: $loggerName"
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
        val service = AnalyticsServiceFixture()
        service.recordEvent("page_view", "u1")
        service.recordEvent("page_view", "u2")
        service.recordEvent("click", "u1")
        assertEquals(3, service.getEventCount(), "Should count 3 events")
    }

    @Test
    fun test_metric_aggregation() {
        val service = AnalyticsServiceFixture()
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
        val service = AnalyticsServiceFixture()
        val metric = service.getMetric("events.nonexistent")
        assertNull(metric, "Non-existent metric should return null")
    }

    @Test
    fun test_multiple_event_types() {
        val service = AnalyticsServiceFixture()
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
        val service = AnalyticsServiceFixture()
        service.recordEvent("a", "u1")
        service.recordEvent("b", "u2")
        val all = service.getAllMetrics()
        assertEquals(2, all.size, "Should have 2 distinct metric types")
    }

    @Test
    fun test_report_generation() {
        val service = AnalyticsServiceFixture()
        service.recordEvent("view", "u1")
        service.recordEvent("click", "u1")

        val report = service.generateReport("u1", Instant.MIN, Instant.MAX)
        assertEquals("u1", report["userId"])
        assertNotNull(report["metrics"])
        assertNotNull(report["generatedAt"])
    }

    @Test
    fun test_report_empty_period() {
        val service = AnalyticsServiceFixture()
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
        val event = AnalyticsEventFixture(
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
        val metric = AggregateMetricFixture("test.metric", 0.0, 0)
        assertEquals(0.0, metric.value)
        assertEquals(0, metric.count)
        assertNotNull(metric.lastUpdated)
    }

    @Test
    fun test_concurrent_event_recording() = runTest {
        val service = AnalyticsServiceFixture()
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
        val service = AnalyticsServiceFixture()
        service.recordEvent("download", "u1")
        val metric = service.getMetric("events.download")
        assertNotNull(metric)
        assertTrue(metric.metricName.contains("download"), "Metric name should contain event type")
    }

    @Test
    fun test_report_contains_user_id() {
        val service = AnalyticsServiceFixture()
        val report = service.generateReport("user-xyz", Instant.MIN, Instant.MAX)
        assertEquals("user-xyz", report["userId"])
    }

    @Test
    fun test_metric_last_updated_recent() {
        val before = Instant.now()
        val service = AnalyticsServiceFixture()
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
        val service = AnalyticsServiceFixture()
        assertEquals(0, service.getEventCount(), "Event count should start at 0")
    }

    @Test
    fun test_get_all_metrics_empty() {
        val service = AnalyticsServiceFixture()
        val all = service.getAllMetrics()
        assertTrue(all.isEmpty(), "New service should have no metrics")
    }

    @Test
    fun test_metric_count_increments() {
        val service = AnalyticsServiceFixture()
        service.recordEvent("click", "u1")
        service.recordEvent("click", "u2")
        service.recordEvent("click", "u3")
        val metric = service.getMetric("events.click")
        assertNotNull(metric)
        assertEquals(3, metric.count, "Metric count should be 3 after 3 events")
    }

    @Test
    fun test_report_structure_keys() {
        val service = AnalyticsServiceFixture()
        service.recordEvent("view", "u1")
        val report = service.generateReport("u1", Instant.MIN, Instant.MAX)
        assertTrue(report.containsKey("userId"), "Report should contain userId key")
        assertTrue(report.containsKey("period"), "Report should contain period key")
        assertTrue(report.containsKey("metrics"), "Report should contain metrics key")
        assertTrue(report.containsKey("generatedAt"), "Report should contain generatedAt key")
    }

    @Test
    fun test_event_properties_default_empty() {
        val event = AnalyticsEventFixture(eventType = "view", userId = "u1")
        assertTrue(event.properties.isEmpty(), "Default properties should be empty")
        assertNull(event.documentId, "Default documentId should be null")
    }

    @Test
    fun test_event_timestamp_set() {
        val before = Instant.now()
        val event = AnalyticsEventFixture(eventType = "action", userId = "u1")
        val after = Instant.now()
        assertTrue(!event.timestamp.isBefore(before), "Timestamp should be at or after creation")
        assertTrue(!event.timestamp.isAfter(after), "Timestamp should be at or before check time")
    }

    @Test
    fun test_multiple_metric_types_independent() {
        val service = AnalyticsServiceFixture()
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
    // Deterministic fixtures mirroring buggy production paths
    // =========================================================================

    data class AnalyticsEventFixture(
        val eventType: String,
        val userId: String,
        val documentId: String? = null,
        val timestamp: Instant = Instant.now(),
        val properties: Map<String, String> = emptyMap()
    )

    data class AggregateMetricFixture(
        val metricName: String,
        val value: Double,
        val count: Long,
        val lastUpdated: Instant = Instant.now()
    )

    class AnalyticsServiceFixture {

        
        companion object {
            
            private val logger = LoggerFactory.getLogger(this::class.java)
        }

        private val eventCounter = AtomicLong(0)
        private val metrics = ConcurrentHashMap<String, AggregateMetricFixture>()

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
                    AggregateMetricFixture(metricName, 1.0, 1)
                }
            }
        }

        fun getEventCount(): Long = eventCounter.get()

        fun getMetric(name: String): AggregateMetricFixture? = metrics[name]

        fun getAllMetrics(): Map<String, AggregateMetricFixture> = metrics.toMap()

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

    // =========================================================================
    // Domain Logic: Percentile calculation index formula
    // =========================================================================

    @Test
    fun test_p90_not_maximum() {
        val fixture = PercentilesFixture()
        val data = (1..10).map { it * 10.0 }
        val result = fixture.computePercentiles(data, listOf(90.0))
        assertTrue(result[90.0]!! < 100.0,
            "P90 of 10 evenly spaced values should be less than the maximum; got ${result[90.0]}")
    }

    @Test
    fun test_p50_is_median() {
        val fixture = PercentilesFixture()
        val data = listOf(1.0, 2.0, 3.0, 4.0, 5.0)
        val result = fixture.computePercentiles(data, listOf(50.0))
        assertEquals(3.0, result[50.0]!!, 0.001, "P50 should be the median value")
    }

    // =========================================================================
    // Domain Logic: Retention rate calculation
    // =========================================================================

    @Test
    fun test_retention_rate_excludes_new_users() {
        val fixture = RetentionFixture()
        val rate = fixture.computeRetentionRate(totalUsers = 100, returningUsers = 60, newUsers = 20)
        assertEquals(
            0.75, rate, 0.01,
            "Retention should be returning / (total - new), not returning / total"
        )
    }

    @Test
    fun test_retention_rate_all_new_users() {
        val fixture = RetentionFixture()
        val rate = fixture.computeRetentionRate(totalUsers = 50, returningUsers = 0, newUsers = 50)
        assertEquals(0.0, rate, 0.01, "All new users means 0% retention")
    }

    @Test
    fun test_retention_rate_no_new_users() {
        val fixture = RetentionFixture()
        val rate = fixture.computeRetentionRate(totalUsers = 100, returningUsers = 80, newUsers = 0)
        assertEquals(0.80, rate, 0.01, "With no new users, retention = returning / total")
    }

    // =========================================================================
    // Integration: Cross-service event correlation timestamp mismatch
    // =========================================================================

    @Test
    fun test_event_correlation_finds_matching_events() {
        val fixture = EventCorrelationFixture()
        val analyticsMs = mapOf("evt1" to 1700000000000L, "evt2" to 1700000001000L)
        val auditSeconds = mapOf("evt1" to 1700000000L, "evt2" to 1700000001L)
        val correlated = fixture.correlateEvents(analyticsMs, auditSeconds)
        assertTrue(
            correlated.contains("evt1"),
            "Events with matching IDs and timestamps should be correlated"
        )
        assertTrue(
            correlated.contains("evt2"),
            "Both matching events should be found"
        )
    }

    @Test
    fun test_event_correlation_no_false_positives() {
        val fixture = EventCorrelationFixture()
        val analyticsMs = mapOf("evt1" to 1700000000000L)
        val auditSeconds = mapOf("evt1" to 1700050000L)
        val correlated = fixture.correlateEvents(analyticsMs, auditSeconds)
        assertFalse(
            correlated.contains("evt1"),
            "Events with very different timestamps should not be correlated"
        )
    }

    // =========================================================================
    // Concurrency: Moving average sliding window off-by-one
    // =========================================================================

    @Test
    fun test_moving_average_correct_values() {
        val fixture = MovingAverageFixture()
        val result = fixture.computeMovingAverage(listOf(1.0, 2.0, 3.0, 4.0, 5.0), windowSize = 3)
        assertEquals(3, result.size, "5 values with window 3 should produce 3 averages")
        assertEquals(2.0, result[0], 0.001, "First window [1,2,3] should average 2.0")
        assertEquals(3.0, result[1], 0.001, "Second window [2,3,4] should average 3.0")
        assertEquals(4.0, result[2], 0.001, "Third window [3,4,5] should average 4.0")
    }

    @Test
    fun test_moving_average_window_larger_than_data() {
        val fixture = MovingAverageFixture()
        val result = fixture.computeMovingAverage(listOf(1.0, 2.0), windowSize = 5)
        assertTrue(result.isEmpty(), "Window larger than data should return empty list")
    }

    class PercentilesFixture {
        fun computePercentiles(
            measurements: List<Double>,
            percentiles: List<Double>
        ): Map<Double, Double> {
            if (measurements.isEmpty()) return percentiles.associateWith { 0.0 }
            val sorted = measurements.sorted()
            val result = mutableMapOf<Double, Double>()
            for (p in percentiles) {
                val rank = (p / 100.0) * sorted.size
                val index = rank.toInt().coerceIn(0, sorted.size - 1)
                result[p] = sorted[index]
            }
            return result
        }
    }

    class RetentionFixture {
        fun computeRetentionRate(totalUsers: Int, returningUsers: Int, newUsers: Int): Double {
            if (totalUsers == 0) return 0.0
            val eligibleUsers = totalUsers - newUsers
            if (eligibleUsers <= 0) return 0.0
            return returningUsers.toDouble() / totalUsers
        }
    }

    class EventCorrelationFixture {
        fun correlateEvents(
            analyticsTimestampsMs: Map<String, Long>,
            auditTimestampsS: Map<String, Long>
        ): List<String> {
            val correlated = mutableListOf<String>()
            for ((eventId, analyticsTs) in analyticsTimestampsMs) {
                val auditTs = auditTimestampsS[eventId] ?: continue
                if (Math.abs(analyticsTs - auditTs) < 1000) {
                    correlated.add(eventId)
                }
            }
            return correlated
        }
    }

    class MovingAverageFixture {
        fun computeMovingAverage(values: List<Double>, windowSize: Int): List<Double> {
            if (values.size < windowSize) return emptyList()
            val result = mutableListOf<Double>()
            var runningSum = values.take(windowSize).sum()
            result.add(runningSum / windowSize)
            for (i in windowSize until values.size) {
                runningSum += values[i] - values[i - windowSize + 1]
                result.add(runningSum / windowSize)
            }
            return result
        }
    }
}
