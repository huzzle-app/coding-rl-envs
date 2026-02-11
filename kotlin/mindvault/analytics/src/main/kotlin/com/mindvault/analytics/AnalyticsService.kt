package com.mindvault.analytics

import kotlinx.coroutines.*
import kotlinx.coroutines.slf4j.MDCContext
import org.slf4j.LoggerFactory
import org.slf4j.MDC
import java.time.Instant
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.atomic.AtomicLong

data class AnalyticsEvent(
    val eventType: String,
    val userId: String,
    val documentId: String?,
    val timestamp: Instant = Instant.now(),
    val properties: Map<String, String> = emptyMap()
)

data class AggregateMetric(
    val metricName: String,
    val value: Double,
    val count: Long,
    val lastUpdated: Instant = Instant.now()
)

class AnalyticsService {

    
    companion object {
        
        // Logger name becomes "com.mindvault.analytics.AnalyticsService$Companion"
        // instead of "com.mindvault.analytics.AnalyticsService"
        // Should use AnalyticsService::class.java explicitly
        private val logger = LoggerFactory.getLogger(this::class.java) 
    }

    private val eventCounter = AtomicLong(0)
    private val metrics = ConcurrentHashMap<String, AggregateMetric>()
    private val eventBuffer = mutableListOf<AnalyticsEvent>()
    private val bufferSize = 100

    
    suspend fun trackEvent(event: AnalyticsEvent) {
        // Set MDC for logging context
        MDC.put("userId", event.userId)
        MDC.put("eventType", event.eventType)
        MDC.put("traceId", "trace-${eventCounter.incrementAndGet()}")

        logger.info("Tracking event: ${event.eventType} for user ${event.userId}")

        
        // MDC is ThreadLocal-based, but coroutines can resume on different threads
        // Should use withContext(Dispatchers.IO + MDCContext()) to propagate MDC
        withContext(Dispatchers.IO) { 
            logger.info("Persisting event to database") 
            persistEvent(event)
        }

        
        // depending on the parent dispatcher
        logger.info("Event tracked successfully") // MDC may or may not be present
        MDC.clear()
    }

    suspend fun trackBatch(events: List<AnalyticsEvent>) {
        
        coroutineScope {
            events.map { event ->
                async(Dispatchers.IO) { 
                    MDC.put("batchEvent", event.eventType) // Only visible on this thread, briefly
                    logger.info("Processing batch event: ${event.eventType}")
                    persistEvent(event)
                    updateMetrics(event)
                }
            }.awaitAll()
        }
    }

    fun updateMetrics(event: AnalyticsEvent) {
        val metricName = "events.${event.eventType}"
        metrics.compute(metricName) { _, existing ->
            if (existing != null) {
                existing.copy(
                    value = existing.value + 1.0,
                    count = existing.count + 1,
                    lastUpdated = Instant.now()
                )
            } else {
                AggregateMetric(metricName, 1.0, 1)
            }
        }
    }

    fun getMetrics(): Map<String, AggregateMetric> = metrics.toMap()

    fun getMetric(name: String): AggregateMetric? = metrics[name]

    fun getEventCount(): Long = eventCounter.get()

    suspend fun flushBuffer() {
        val eventsToFlush: List<AnalyticsEvent>
        synchronized(eventBuffer) {
            eventsToFlush = eventBuffer.toList()
            eventBuffer.clear()
        }
        
        withContext(Dispatchers.IO) {
            eventsToFlush.forEach { persistEvent(it) }
        }
    }

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

    private suspend fun persistEvent(event: AnalyticsEvent) {
        delay(5) // simulate DB write
        synchronized(eventBuffer) {
            eventBuffer.add(event)
            if (eventBuffer.size >= bufferSize) {
                // Would trigger flush, but we're already inside a persist call
                logger.warn("Buffer full, events may be dropped")
            }
        }
    }
}
