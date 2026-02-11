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
 */
public class MdcPropagator {

    public static final String TRACE_ID_KEY = "traceId";
    public static final String SPAN_ID_KEY = "spanId";
    public static final String USER_ID_KEY = "userId";
    public static final String SERVICE_KEY = "service";

    private MdcPropagator() {
        // Utility class - prevent instantiation
    }

    
    // When spawning new threads, using CompletableFuture, or submitting tasks
    // to ExecutorService, MDC context is lost because MDC is ThreadLocal-based.
    // In FleetPulse, this means trace IDs are lost in async processing:
    //   - Dispatch ticket assignment runs async but loses the request trace ID
    //   - Analytics aggregation in CompletableFuture chains has empty MDC
    //   - Virtual thread tasks spawned by VirtualThreadExecutor lose context
    // Without trace IDs, log correlation across async operations is impossible,
    // making production debugging extremely difficult.
    // Category: Observability
    // Fix: Capture MDC context map before spawning and restore it in the new thread:
    //   Map<String, String> context = MDC.getCopyOfContextMap();
    //   return () -> {
    //       if (context != null) MDC.setContextMap(context);
    //       try { task.run(); }
    //       finally { MDC.clear(); }
    //   };

    /**
     * Wraps a Runnable to propagate MDC context to the executing thread.
     *
     * @param task the runnable to wrap
     * @return a wrapped runnable that restores MDC context
     */
    public static Runnable wrap(Runnable task) {
        
        // The spawned thread will have an empty MDC, losing all trace
        // and diagnostic information.
        return task;
        // Fix:
        // Map<String, String> context = MDC.getCopyOfContextMap();
        // return () -> {
        //     Map<String, String> previous = MDC.getCopyOfContextMap();
        //     if (context != null) {
        //         MDC.setContextMap(context);
        //     }
        //     try {
        //         task.run();
        //     } finally {
        //         if (previous != null) {
        //             MDC.setContextMap(previous);
        //         } else {
        //             MDC.clear();
        //         }
        //     }
        // };
    }

    /**
     * Wraps a Callable to propagate MDC context to the executing thread.
     *
     * @param task the callable to wrap
     * @return a wrapped callable that restores MDC context
     */
    public static <T> Callable<T> wrap(Callable<T> task) {
        
        return task;
        // Fix:
        // Map<String, String> context = MDC.getCopyOfContextMap();
        // return () -> {
        //     Map<String, String> previous = MDC.getCopyOfContextMap();
        //     if (context != null) {
        //         MDC.setContextMap(context);
        //     }
        //     try {
        //         return task.call();
        //     } finally {
        //         if (previous != null) {
        //             MDC.setContextMap(previous);
        //         } else {
        //             MDC.clear();
        //         }
        //     }
        // };
    }

    
    // When publishing Kafka messages, the trace/correlation IDs stored in MDC
    // are not included in the Kafka message headers. This breaks distributed
    // tracing across service boundaries:
    //   - Tracking service publishes GPS events without trace ID
    //   - Analytics service consuming those events cannot correlate them
    //   - Billing events lose the originating request context
    // Category: Observability
    // Fix: Extract trace ID from MDC and include it in returned headers map:
    //   String traceId = MDC.get(TRACE_ID_KEY);
    //   if (traceId != null) headers.put("X-Trace-Id", traceId);
    //   String spanId = MDC.get(SPAN_ID_KEY);
    //   if (spanId != null) headers.put("X-Span-Id", spanId);

    /**
     * Returns a map of trace headers to include in Kafka messages
     * for distributed tracing propagation.
     *
     * @return map of header name to value for Kafka message headers
     */
    public static Map<String, String> getTraceHeaders() {
        Map<String, String> headers = new HashMap<>();
        
        // The returned map is always empty, so Kafka messages carry no trace context.
        // Fix:
        // String traceId = MDC.get(TRACE_ID_KEY);
        // if (traceId != null) {
        //     headers.put("X-Trace-Id", traceId);
        // }
        // String spanId = MDC.get(SPAN_ID_KEY);
        // if (spanId != null) {
        //     headers.put("X-Span-Id", spanId);
        // }
        // String userId = MDC.get(USER_ID_KEY);
        // if (userId != null) {
        //     headers.put("X-User-Id", userId);
        // }
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
