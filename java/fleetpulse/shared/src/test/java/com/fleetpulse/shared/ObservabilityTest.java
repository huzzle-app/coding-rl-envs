package com.fleetpulse.shared;

import com.fleetpulse.shared.util.MdcPropagator;
import com.fleetpulse.shared.util.MetricsCollector;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.slf4j.MDC;

import java.util.Map;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicReference;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class ObservabilityTest {

    @BeforeEach
    void setUp() {
        MDC.clear();
    }

    
    @Test
    void test_mdc_in_thread() throws Exception {
        MDC.put("traceId", "trace-123");
        MDC.put("spanId", "span-456");

        AtomicReference<String> threadTraceId = new AtomicReference<>();

        Runnable wrapped = MdcPropagator.wrap(() -> {
            threadTraceId.set(MDC.get("traceId"));
        });

        Thread t = new Thread(wrapped);
        t.start();
        t.join(5000);

        
        assertEquals("trace-123", threadTraceId.get(),
            "MDC traceId should be propagated to child thread");
    }

    @Test
    void test_context_preserved() throws Exception {
        MDC.put("traceId", "trace-abc");

        AtomicReference<String> result = new AtomicReference<>();

        Callable<String> wrapped = MdcPropagator.wrap(() -> {
            result.set(MDC.get("traceId"));
            return MDC.get("traceId");
        });

        ExecutorService executor = Executors.newSingleThreadExecutor();
        String callResult = executor.submit(wrapped).get(5, TimeUnit.SECONDS);
        executor.shutdown();

        assertEquals("trace-abc", callResult,
            "MDC context should be preserved in Callable");
    }

    
    @Test
    void test_kafka_trace_header() {
        MdcPropagator.setTraceContext("trace-kafka-123", "span-kafka-456");

        Map<String, String> headers = MdcPropagator.getTraceHeaders();

        
        assertTrue(headers.containsKey("X-Trace-Id"),
            "Kafka headers should contain X-Trace-Id");
        assertEquals("trace-kafka-123", headers.get("X-Trace-Id"));
    }

    @Test
    void test_trace_in_message() {
        MdcPropagator.setTraceContext("t1", "s1");
        Map<String, String> headers = MdcPropagator.getTraceHeaders();
        assertFalse(headers.isEmpty(), "Trace headers should not be empty");
    }

    @Test
    void test_clear_trace_context() {
        MdcPropagator.setTraceContext("trace", "span");
        assertNotNull(MDC.get("traceId"));

        MdcPropagator.clearTraceContext();
        assertNull(MDC.get("traceId"));
        assertNull(MDC.get("spanId"));
    }

    
    @Test
    void test_log_level_case_insensitive() {
        MetricsCollector collector = new MetricsCollector();

        
        assertTrue(collector.isLevelEnabled("INFO", "INFO"));
        assertTrue(collector.isLevelEnabled("info", "info"),
            "Log level comparison should be case-insensitive");
        assertTrue(collector.isLevelEnabled("Info", "INFO"),
            "Mixed case should work");
    }

    @Test
    void test_info_equals_INFO() {
        MetricsCollector collector = new MetricsCollector();
        
        assertEquals(
            collector.isLevelEnabled("INFO", "WARN"),
            collector.isLevelEnabled("info", "warn"),
            "Case should not affect log level comparison"
        );
    }

    @Test
    void test_log_level_ordering() {
        MetricsCollector collector = new MetricsCollector();
        assertTrue(collector.isLevelEnabled("DEBUG", "INFO"));
        assertTrue(collector.isLevelEnabled("DEBUG", "ERROR"));
        assertFalse(collector.isLevelEnabled("ERROR", "DEBUG"));
    }

    
    @Test
    void test_span_closed_on_error() throws Exception {
        MetricsCollector collector = new MetricsCollector();

        
        try (AutoCloseable span = collector.startSpan("test-span")) {
            throw new RuntimeException("Processing error");
        } catch (RuntimeException e) {
            // Expected
        }

        // After closing, active span count should be 0
        assertEquals(0, collector.getCounter("test-span.active"),
            "Span should be closed after exception");
    }

    @Test
    void test_no_span_leak() throws Exception {
        MetricsCollector collector = new MetricsCollector();

        for (int i = 0; i < 10; i++) {
            try (AutoCloseable span = collector.startSpan("leak-test")) {
                // Process
            }
        }

        assertEquals(0, collector.getCounter("leak-test.active"),
            "No spans should be leaked");
    }

    @Test
    void test_counter_increment() {
        MetricsCollector collector = new MetricsCollector();
        collector.incrementCounter("requests");
        collector.incrementCounter("requests");
        assertEquals(2, collector.getCounter("requests"));
    }

    @Test
    void test_all_counters() {
        MetricsCollector collector = new MetricsCollector();
        collector.incrementCounter("a");
        collector.incrementCounter("b");
        Map<String, Long> all = collector.getAllCounters();
        assertEquals(2, all.size());
    }
}
