package com.fleetpulse.shared.util;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.concurrent.atomic.DoubleAdder;

/**
 * Lightweight metrics collector for FleetPulse services.
 *
 * Provides thread-safe counters, gauges, and timed spans for observability.
 * Used by all services to track request counts, processing durations,
 * error rates, and business metrics (vehicles tracked, routes completed,
 * dispatch assignments, billing amounts).
 *
 * Designed to be exported to Prometheus or similar monitoring backends.
 *
 * Bugs: J4, J5
 * Categories: Observability
 */
public class MetricsCollector {

    private final Map<String, AtomicLong> counters = new ConcurrentHashMap<>();
    private final Map<String, DoubleAdder> gauges = new ConcurrentHashMap<>();

    // Bug J4: The log level lookup map uses uppercase keys but callers may pass
    // lowercase or mixed-case level strings, causing lookups to fail silently.
    // Category: Observability

    /**
     * Checks if a requested log level is enabled given the configured threshold.
     *
     * @param configuredLevel the minimum enabled level (e.g., "INFO")
     * @param requestedLevel  the level being checked (e.g., "DEBUG")
     * @return true if requestedLevel is at or above configuredLevel
     */
    public boolean isLevelEnabled(String configuredLevel, String requestedLevel) {
        Map<String, Integer> levels = Map.of(
            "TRACE", 0,
            "DEBUG", 1,
            "INFO", 2,
            "WARN", 3,
            "ERROR", 4
        );

        Integer configured = levels.get(configuredLevel);
        Integer requested = levels.get(requestedLevel);

        if (configured == null || requested == null) {
            return false;
        }

        return requested >= configured;
    }

    // Bug J5: The startSpan() API does not enforce try-with-resources usage.
    // If the caller does not use try-with-resources and an exception occurs,
    // the active span counter stays incremented permanently.
    // Category: Observability

    /**
     * Starts a timed metric span. The returned AutoCloseable MUST be used
     * in a try-with-resources block to ensure proper cleanup.
     *
     * @param name the span name (e.g., "dispatch.assign", "route.optimize")
     * @return an AutoCloseable that records duration and decrements active count
     */
    public AutoCloseable startSpan(String name) {
        long startTime = System.nanoTime();
        counters.computeIfAbsent(name + ".active", k -> new AtomicLong(0)).incrementAndGet();
        counters.computeIfAbsent(name + ".total", k -> new AtomicLong(0)).incrementAndGet();

        return () -> {
            long elapsed = System.nanoTime() - startTime;
            counters.computeIfAbsent(name + ".active", k -> new AtomicLong(0)).decrementAndGet();
            gauges.computeIfAbsent(name + ".duration_ms", k -> new DoubleAdder())
                .add(elapsed / 1_000_000.0);
        };
    }

    /**
     * Increments a named counter by 1.
     *
     * @param name the counter name
     */
    public void incrementCounter(String name) {
        counters.computeIfAbsent(name, k -> new AtomicLong(0)).incrementAndGet();
    }

    /**
     * Increments a named counter by the specified amount.
     *
     * @param name  the counter name
     * @param delta the amount to add
     */
    public void incrementCounter(String name, long delta) {
        counters.computeIfAbsent(name, k -> new AtomicLong(0)).addAndGet(delta);
    }

    /**
     * Records a gauge value (cumulative, uses DoubleAdder).
     *
     * @param name  the gauge name
     * @param value the value to add
     */
    public void recordGauge(String name, double value) {
        gauges.computeIfAbsent(name, k -> new DoubleAdder()).add(value);
    }

    /**
     * Gets the current value of a counter.
     *
     * @param name the counter name
     * @return the counter value, or 0 if not found
     */
    public long getCounter(String name) {
        AtomicLong counter = counters.get(name);
        return counter != null ? counter.get() : 0;
    }

    /**
     * Gets the current value of a gauge.
     *
     * @param name the gauge name
     * @return the gauge sum, or 0.0 if not found
     */
    public double getGauge(String name) {
        DoubleAdder gauge = gauges.get(name);
        return gauge != null ? gauge.sum() : 0.0;
    }

    /**
     * Returns a snapshot of all counter values.
     */
    public Map<String, Long> getAllCounters() {
        Map<String, Long> result = new ConcurrentHashMap<>();
        counters.forEach((k, v) -> result.put(k, v.get()));
        return result;
    }

    /**
     * Returns a snapshot of all gauge values.
     */
    public Map<String, Double> getAllGauges() {
        Map<String, Double> result = new ConcurrentHashMap<>();
        gauges.forEach((k, v) -> result.put(k, v.sum()));
        return result;
    }

    /**
     * Resets all counters and gauges. Used in testing.
     */
    public void reset() {
        counters.clear();
        gauges.clear();
    }
}
