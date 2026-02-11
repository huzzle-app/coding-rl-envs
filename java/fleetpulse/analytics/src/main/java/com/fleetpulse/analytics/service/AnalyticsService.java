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
 * Contains intentional bugs:
 *   B4 - WeakReference surprise (cached data disappears unpredictably)
 *   B5 - String concatenation in loop (O(n^2) performance)
 *   G4 - Pagination off-by-one
 *   K3 - Pattern matching binding scope / unsafe cast
 *   J1 - MDC context loss across async threads
 */
@Service
public class AnalyticsService {

    private static final Logger log = LoggerFactory.getLogger(AnalyticsService.class);

    
    // WeakReference allows GC to collect the cached data at any time, even when
    // memory is plentiful. This means getCachedReport() can return null even
    // immediately after cacheReport() was called, if a GC cycle occurred.
    // Fix: Use SoftReference (collected only under memory pressure) or a strong
    //       cache with explicit eviction (e.g., Caffeine/Guava cache with max size):
    //   private final Map<String, SoftReference<List<Map<String, Object>>>> reportCache = ...;
    //   Or: private final Cache<String, List<Map<String, Object>>> reportCache =
    //           Caffeine.newBuilder().maximumSize(1000).build();
    private final Map<String, WeakReference<List<Map<String, Object>>>> reportCache = new ConcurrentHashMap<>();

    /**
     * Generates a CSV string from a list of row maps.
     *
     * @param data list of rows, each row being a map of column-name to value
     * @return CSV-formatted string
     */
    
    // Each += on a String creates a new String object, copies all previous
    // characters, and discards the old String. For a report with N rows and
    // M columns, this is O(N * M * total_length) - quadratic in output size.
    // Fix: Use StringBuilder throughout:
    //   StringBuilder csv = new StringBuilder();
    //   csv.append(key).append(",");
    //   return csv.toString();
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
    
    // The offset calculation uses 0-based page numbering (page * pageSize),
    // but callers pass 1-based page numbers. Page 1 returns items starting
    // at index pageSize instead of index 0, skipping the first page entirely.
    // Fix: Use (page - 1) * pageSize for 1-based page numbers:
    //   int fromIndex = (page - 1) * pageSize;
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
    
    // When metric is a List<?>, the code performs an unchecked cast to List<String>.
    // If the list contains non-String elements, calling stringList.get(0) or any
    // String-specific operation throws ClassCastException at runtime. The
    // @SuppressWarnings hides the compile-time warning but the bug remains.
    // Fix: Validate element types before casting:
    //   if (list.isEmpty()) return "Empty list metric";
    //   if (!(list.get(0) instanceof String)) return "Non-string list metric";
    //   List<String> stringList = list.stream().map(Object::toString).toList();
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
            
            // This will throw ClassCastException at runtime if elements are not Strings
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
    
    // SLF4J MDC uses ThreadLocal storage, so when CompletableFuture.supplyAsync()
    // executes the supplier on a different thread (from ForkJoinPool.commonPool()),
    // all MDC values (traceId, requestId, etc.) are null. This breaks distributed
    // tracing and makes log correlation impossible for async operations.
    // Fix: Capture MDC context before submitting and restore it inside the async block:
    //   Map<String, String> mdcContext = MDC.getCopyOfContextMap();
    //   return CompletableFuture.supplyAsync(() -> {
    //       if (mdcContext != null) MDC.setContextMap(mdcContext);
    //       try {
    //           // ... generate report ...
    //       } finally {
    //           MDC.clear();
    //       }
    //   });
    public CompletableFuture<Map<String, Object>> generateAsyncReport(String reportId) {
        String traceId = MDC.get("traceId");
        log.info("Starting async report generation: {}", reportId);

        
        return CompletableFuture.supplyAsync(() -> {
            
            log.info("Generating report {} with traceId={}", reportId, MDC.get("traceId"));

            Map<String, Object> report = new HashMap<>();
            report.put("reportId", reportId);
            report.put("generatedAt", System.currentTimeMillis());
            report.put("traceId", MDC.get("traceId")); // Will be null - MDC is empty
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
        
        // even immediately after caching, with no warning or eviction callback
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
            
            // between the null-check on ref and this dereference
            return ref.get();
        }
        return null;
    }
}
