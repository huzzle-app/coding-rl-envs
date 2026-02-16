package com.fleetpulse.analytics.service;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.stereotype.Service;

import java.lang.ref.WeakReference;
import java.util.*;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Service providing fleet analytics: report generation, CSV export,
 * pagination, metric classification, and async report building.
 *
 * Bugs: B4, B5, G4, K3, J1
 * Categories: Memory/Data Structures, Algorithm, Templates, Observability
 */
@Service
public class AnalyticsService {

    private static final Logger log = LoggerFactory.getLogger(AnalyticsService.class);

    // Bug B4: WeakReference allows GC to collect the cached data at any time,
    // even when memory is plentiful. getCachedReport() can return null immediately
    // after cacheReport() was called.
    // Category: Memory/Data Structures
    private final Map<String, WeakReference<List<Map<String, Object>>>> reportCache = new ConcurrentHashMap<>();

    /**
     * Generates a CSV string from a list of row maps.
     *
     * @param data list of rows, each row being a map of column-name to value
     * @return CSV-formatted string
     */
    // Bug B5: String concatenation in loop creates O(n^2) performance.
    // Category: Memory/Data Structures
    public String generateCsvReport(List<Map<String, Object>> data) {
        String csv = "";

        // Header
        if (!data.isEmpty()) {
            for (String key : data.get(0).keySet()) {
                csv += key + ",";
            }
            csv += "\n";
        }

        // Rows
        for (Map<String, Object> row : data) {
            for (Object value : row.values()) {
                csv += (value != null ? value.toString() : "") + ",";
            }
            csv += "\n";
        }

        return csv;
    }

    /**
     * Returns a sublist representing a single page of results.
     *
     * @param items    the full list of items
     * @param page     the page number (intended to be 1-based by callers)
     * @param pageSize the number of items per page
     * @param <T>      element type
     * @return the items on the requested page, or empty list if out of range
     */
    // Bug G4: Pagination uses 0-based offset calculation but callers pass 1-based
    // page numbers, skipping the first page entirely.
    // Category: Algorithm
    public <T> List<T> paginate(List<T> items, int page, int pageSize) {
        int fromIndex = page * pageSize;
        int toIndex = fromIndex + pageSize;

        if (fromIndex >= items.size()) {
            return List.of();
        }

        toIndex = Math.min(toIndex, items.size());

        return new ArrayList<>(items.subList(fromIndex, toIndex));
    }

    /**
     * Produces a human-readable description of a metric value based on its runtime type.
     *
     * @param metric the metric value (String, Integer, Double, List, or other)
     * @return a description string
     */
    // Bug K3: Unchecked cast of List<?> to List<String> throws ClassCastException
    // at runtime if elements are not Strings.
    // Category: Templates
    public String describeMetric(Object metric) {
        if (metric instanceof String s) {
            return "String metric: " + s;
        }
        if (metric instanceof Integer n) {
            return "Integer metric: " + n;
        }
        if (metric instanceof Double d) {
            return "Double metric: " + d;
        }
        if (metric instanceof List<?> list) {
            @SuppressWarnings("unchecked")
            List<String> stringList = (List<String>) list;
            return "List metric with " + stringList.size() + " items: " + stringList.get(0);
        }
        return "Unknown metric type: " + metric.getClass().getSimpleName();
    }

    /**
     * Generates a report asynchronously, returning a CompletableFuture.
     *
     * @param reportId identifier for the report to generate
     * @return a future that completes with the report data map
     */
    // Bug J1: MDC context is lost when CompletableFuture.supplyAsync() executes
    // on a different thread from ForkJoinPool.commonPool().
    // Category: Observability
    public CompletableFuture<Map<String, Object>> generateAsyncReport(String reportId) {
        String traceId = MDC.get("traceId");
        log.info("Starting async report generation: {}", reportId);

        return CompletableFuture.supplyAsync(() -> {
            log.info("Generating report {} with traceId={}", reportId, MDC.get("traceId"));

            Map<String, Object> report = new HashMap<>();
            report.put("reportId", reportId);
            report.put("generatedAt", System.currentTimeMillis());
            report.put("traceId", MDC.get("traceId"));
            return report;
        });
    }

    /**
     * Caches a report under the given key using a WeakReference.
     *
     * @param key  the cache key
     * @param data the report data to cache
     */
    public void cacheReport(String key, List<Map<String, Object>> data) {
        reportCache.put(key, new WeakReference<>(data));
    }

    /**
     * Retrieves a previously cached report.
     *
     * @param key the cache key
     * @return the cached report data, or null if not found or already collected by GC
     */
    public List<Map<String, Object>> getCachedReport(String key) {
        WeakReference<List<Map<String, Object>>> ref = reportCache.get(key);
        if (ref != null) {
            return ref.get();
        }
        return null;
    }
}
