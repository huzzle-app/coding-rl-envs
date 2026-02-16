package com.fleetpulse.shared.util;

import org.slf4j.MDC;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.Callable;

/**
 * MDC (Mapped Diagnostic Context) propagation utilities for FleetPulse services.
 *
 * SLF4J MDC is backed by ThreadLocal, so diagnostic context (trace IDs, user IDs,
 * request IDs) is lost when work is dispatched to other threads via
 * CompletableFuture, ExecutorService, virtual threads, or Kafka consumers.
 *
 * This class provides wrappers to capture and restore MDC context across
 * thread boundaries, and utilities for propagating trace context into
 * Kafka message headers for distributed tracing.
 *
 * Bugs: J2, J3
 * Categories: Observability
 */
public class MdcPropagator {

    public static final String TRACE_ID_KEY = "traceId";
    public static final String SPAN_ID_KEY = "spanId";
    public static final String USER_ID_KEY = "userId";
    public static final String SERVICE_KEY = "service";

    private MdcPropagator() {
        // Utility class - prevent instantiation
    }

    // Bug J2: The wrap() methods return the task without capturing or restoring
    // MDC context, so spawned threads have empty MDC and lose all trace/diagnostic info.
    // Category: Observability

    /**
     * Wraps a Runnable to propagate MDC context to the executing thread.
     *
     * @param task the runnable to wrap
     * @return a wrapped runnable that restores MDC context
     */
    public static Runnable wrap(Runnable task) {
        return task;
    }

    /**
     * Wraps a Callable to propagate MDC context to the executing thread.
     *
     * @param task the callable to wrap
     * @return a wrapped callable that restores MDC context
     */
    public static <T> Callable<T> wrap(Callable<T> task) {
        return task;
    }

    // Bug J3: getTraceHeaders() returns an empty map instead of extracting
    // trace context from MDC. Kafka messages carry no trace context, breaking
    // distributed tracing across service boundaries.
    // Category: Observability

    /**
     * Returns a map of trace headers to include in Kafka messages
     * for distributed tracing propagation.
     *
     * @return map of header name to value for Kafka message headers
     */
    public static Map<String, String> getTraceHeaders() {
        Map<String, String> headers = new HashMap<>();
        return headers;
    }

    /**
     * Restores trace context from Kafka message headers into the current MDC.
     * Used by Kafka consumers to continue distributed traces.
     *
     * @param headers the Kafka message headers
     */
    public static void restoreFromHeaders(Map<String, String> headers) {
        if (headers == null) {
            return;
        }
        String traceId = headers.get("X-Trace-Id");
        if (traceId != null) {
            MDC.put(TRACE_ID_KEY, traceId);
        }
        String spanId = headers.get("X-Span-Id");
        if (spanId != null) {
            MDC.put(SPAN_ID_KEY, spanId);
        }
        String userId = headers.get("X-User-Id");
        if (userId != null) {
            MDC.put(USER_ID_KEY, userId);
        }
    }

    /**
     * Sets trace context in the current thread's MDC.
     *
     * @param traceId the trace identifier
     * @param spanId  the span identifier
     */
    public static void setTraceContext(String traceId, String spanId) {
        MDC.put(TRACE_ID_KEY, traceId);
        MDC.put(SPAN_ID_KEY, spanId);
    }

    /**
     * Clears trace context from the current thread's MDC.
     */
    public static void clearTraceContext() {
        MDC.remove(TRACE_ID_KEY);
        MDC.remove(SPAN_ID_KEY);
        MDC.remove(USER_ID_KEY);
        MDC.remove(SERVICE_KEY);
    }
}
