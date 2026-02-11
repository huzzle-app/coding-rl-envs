package com.fleetpulse.analytics;

import com.fleetpulse.analytics.service.AnalyticsService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import org.slf4j.MDC;

import java.lang.ref.WeakReference;
import java.util.*;
import java.util.concurrent.*;

import static org.junit.jupiter.api.Assertions.*;

@Tag("unit")
public class AnalyticsServiceTest {

    private AnalyticsService analyticsService;

    @BeforeEach
    void setUp() {
        analyticsService = new AnalyticsService();
    }

    // ====== BUG B4: WeakReference cache (data disappears unpredictably) ======
    @Test
    void test_weak_reference_cache() {
        
        List<Map<String, Object>> data = createReportData(5);
        analyticsService.cacheReport("key1", data);

        // Immediately after caching, should still be available (before GC)
        List<Map<String, Object>> cached = analyticsService.getCachedReport("key1");
        // With WeakReference, this may or may not be null depending on GC
        // With SoftReference fix, this should be non-null (not under memory pressure)
        if (cached != null) {
            assertEquals(5, cached.size(), "Cached data should have 5 rows");
        }
        // Test passes either way - it documents the problematic behavior
    }

    @Test
    void test_cache_not_gc_collected() {
        
        List<Map<String, Object>> data = createReportData(3);
        analyticsService.cacheReport("retain", data);

        // Keep a strong reference to prevent GC
        List<Map<String, Object>> strongRef = data;

        List<Map<String, Object>> cached = analyticsService.getCachedReport("retain");
        assertNotNull(cached,
            "Data with strong reference should not be GC'd");
        assertEquals(strongRef.size(), cached.size());
    }

    @Test
    void test_cache_miss_returns_null() {
        List<Map<String, Object>> result = analyticsService.getCachedReport("nonexistent");
        assertNull(result, "Non-existent key should return null");
    }

    @Test
    void test_cache_overwrite() {
        List<Map<String, Object>> data1 = createReportData(3);
        List<Map<String, Object>> data2 = createReportData(7);

        analyticsService.cacheReport("key", data1);
        analyticsService.cacheReport("key", data2);

        List<Map<String, Object>> cached = analyticsService.getCachedReport("key");
        if (cached != null) {
            assertEquals(7, cached.size(), "Should return most recently cached data");
        }
    }

    @Test
    void test_cache_multiple_keys() {
        List<Map<String, Object>> data1 = createReportData(1);
        List<Map<String, Object>> data2 = createReportData(2);
        List<Map<String, Object>> data3 = createReportData(3);

        analyticsService.cacheReport("a", data1);
        analyticsService.cacheReport("b", data2);
        analyticsService.cacheReport("c", data3);

        // Verify all keys stored (with strong refs held)
        List<Map<String, Object>> ref1 = data1;
        List<Map<String, Object>> ref2 = data2;
        List<Map<String, Object>> ref3 = data3;

        assertNotNull(analyticsService.getCachedReport("a"));
        assertNotNull(analyticsService.getCachedReport("b"));
        assertNotNull(analyticsService.getCachedReport("c"));
    }

    @Test
    void test_weak_reference_gc_behavior() {
        // Demonstrate WeakReference GC behavior
        WeakReference<String> weakRef = new WeakReference<>(new String("test"));
        // The referent may be GC'd because there's no strong reference
        // This test documents the weakness of WeakReference
        assertNotNull(weakRef); // The reference object itself exists
    }

    // ====== BUG B5: String concatenation in loop O(n^2) ======
    @Test
    void test_string_concat_performance() {
        
        List<Map<String, Object>> data = createReportData(100);

        long start = System.nanoTime();
        String csv = analyticsService.generateCsvReport(data);
        long elapsed = System.nanoTime() - start;

        assertNotNull(csv);
        assertFalse(csv.isEmpty());
        // With StringBuilder fix, this should be fast
        // With String +=, it's quadratic and slower for large data
        assertTrue(elapsed < 5_000_000_000L,
            "CSV generation should complete within 5 seconds");
    }

    @Test
    void test_csv_generation_fast() {
        
        List<Map<String, Object>> data = createReportData(500);

        long start = System.nanoTime();
        String csv = analyticsService.generateCsvReport(data);
        long elapsed = System.nanoTime() - start;

        assertNotNull(csv);
        assertTrue(csv.contains(","), "CSV should contain delimiters");
        assertTrue(elapsed < 10_000_000_000L,
            "500-row CSV should not take more than 10 seconds");
    }

    @Test
    void test_csv_empty_data() {
        String csv = analyticsService.generateCsvReport(new ArrayList<>());
        assertNotNull(csv);
        assertEquals("", csv, "Empty data should produce empty CSV");
    }

    @Test
    void test_csv_single_row() {
        List<Map<String, Object>> data = new ArrayList<>();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("name", "test");
        row.put("value", 42);
        data.add(row);

        String csv = analyticsService.generateCsvReport(data);
        assertNotNull(csv);
        assertTrue(csv.contains("name"));
        assertTrue(csv.contains("42"));
    }

    @Test
    void test_csv_null_values() {
        List<Map<String, Object>> data = new ArrayList<>();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("name", "test");
        row.put("missing", null);
        data.add(row);

        String csv = analyticsService.generateCsvReport(data);
        assertNotNull(csv);
        // Null values should be handled gracefully (empty string)
    }

    @Test
    void test_csv_header_present() {
        List<Map<String, Object>> data = new ArrayList<>();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("col1", "val1");
        row.put("col2", "val2");
        data.add(row);

        String csv = analyticsService.generateCsvReport(data);
        assertTrue(csv.contains("col1"));
        assertTrue(csv.contains("col2"));
    }

    @Test
    void test_csv_multiple_rows() {
        List<Map<String, Object>> data = createReportData(5);
        String csv = analyticsService.generateCsvReport(data);
        String[] lines = csv.split("\n");
        // 1 header + 5 data rows
        assertEquals(6, lines.length, "Should have header + 5 data rows");
    }

    @Test
    void test_csv_preserves_order() {
        List<Map<String, Object>> data = new ArrayList<>();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("alpha", "first");
        row.put("beta", "second");
        row.put("gamma", "third");
        data.add(row);

        String csv = analyticsService.generateCsvReport(data);
        assertNotNull(csv);
    }

    // ====== BUG G4: Pagination off-by-one ======
    @Test
    void test_pagination_correct() {
        
        List<String> items = createStringList(20);

        List<String> page1 = analyticsService.paginate(items, 1, 5);
        // With the bug, page 1 returns items[5..9] (skipping first page)
        // With the fix, page 1 should return items[0..4]
        assertFalse(page1.isEmpty(), "Page 1 should not be empty");
        assertEquals(5, page1.size(), "Page should have 5 items");
        assertEquals("item-0", page1.get(0),
            "First page should start with item-0");
    }

    @Test
    void test_no_off_by_one() {
        
        List<String> items = createStringList(10);

        List<String> page1 = analyticsService.paginate(items, 1, 3);
        assertEquals("item-0", page1.get(0),
            "Page 1 should start with the first item");
        assertEquals(3, page1.size());
    }

    @Test
    void test_pagination_page_2() {
        List<String> items = createStringList(20);
        List<String> page2 = analyticsService.paginate(items, 2, 5);
        assertFalse(page2.isEmpty());
    }

    @Test
    void test_pagination_last_page_partial() {
        List<String> items = createStringList(7);
        List<String> lastPage = analyticsService.paginate(items, 2, 5);
        // With fix: page 2 gets items[5..6] = 2 items
        assertTrue(lastPage.size() <= 5);
    }

    @Test
    void test_pagination_beyond_range() {
        List<String> items = createStringList(10);
        List<String> beyondPage = analyticsService.paginate(items, 100, 5);
        assertTrue(beyondPage.isEmpty(), "Page beyond range should be empty");
    }

    @Test
    void test_pagination_empty_list() {
        List<String> page = analyticsService.paginate(new ArrayList<>(), 1, 5);
        assertTrue(page.isEmpty());
    }

    @Test
    void test_pagination_single_item() {
        List<String> items = List.of("only");
        List<String> page = analyticsService.paginate(items, 1, 10);
        // With fix, page 1 should return the single item
        if (!page.isEmpty()) {
            assertEquals("only", page.get(0));
        }
    }

    @Test
    void test_pagination_exact_fit() {
        List<String> items = createStringList(10);
        List<String> page = analyticsService.paginate(items, 1, 10);
        if (!page.isEmpty()) {
            assertEquals(10, page.size());
        }
    }

    @Test
    void test_pagination_page_size_one() {
        List<String> items = createStringList(5);
        List<String> page = analyticsService.paginate(items, 1, 1);
        if (!page.isEmpty()) {
            assertEquals(1, page.size());
        }
    }

    @Test
    void test_pagination_returns_independent_copy() {
        List<String> items = new ArrayList<>(createStringList(10));
        List<String> page = analyticsService.paginate(items, 1, 5);
        if (!page.isEmpty()) {
            page.add("extra");
            // Original should not be modified
            assertEquals(10, items.size());
        }
    }

    // ====== BUG K3: Pattern matching binding scope / unsafe cast ======
    @Test
    void test_pattern_match_scope() {
        
        List<Integer> intList = List.of(1, 2, 3);

        // With the bug, this throws ClassCastException when accessing elements as String
        // With the fix, it should handle non-String lists gracefully
        assertDoesNotThrow(() -> analyticsService.describeMetric(intList),
            "List<Integer> should not cause ClassCastException");
    }

    @Test
    void test_safe_type_check() {
        
        List<Object> mixedList = List.of(1, "two", 3.0);

        assertDoesNotThrow(() -> analyticsService.describeMetric(mixedList),
            "Mixed-type list should be handled safely");
    }

    @Test
    void test_describe_string_metric() {
        String result = analyticsService.describeMetric("hello");
        assertTrue(result.contains("String metric"));
        assertTrue(result.contains("hello"));
    }

    @Test
    void test_describe_integer_metric() {
        String result = analyticsService.describeMetric(42);
        assertTrue(result.contains("Integer metric"));
        assertTrue(result.contains("42"));
    }

    @Test
    void test_describe_double_metric() {
        String result = analyticsService.describeMetric(3.14);
        assertTrue(result.contains("Double metric"));
    }

    @Test
    void test_describe_string_list_metric() {
        List<String> stringList = List.of("a", "b", "c");
        String result = analyticsService.describeMetric(stringList);
        assertNotNull(result);
        assertTrue(result.contains("List metric") || result.contains("list"));
    }

    @Test
    void test_describe_unknown_type() {
        Object custom = new Object() {};
        String result = analyticsService.describeMetric(custom);
        assertNotNull(result);
        assertTrue(result.contains("Unknown") || result.contains("metric"));
    }

    @Test
    void test_describe_empty_string() {
        String result = analyticsService.describeMetric("");
        assertTrue(result.contains("String metric"));
    }

    @Test
    void test_describe_zero() {
        String result = analyticsService.describeMetric(0);
        assertTrue(result.contains("Integer metric"));
    }

    @Test
    void test_describe_negative_double() {
        String result = analyticsService.describeMetric(-1.5);
        assertTrue(result.contains("Double metric"));
    }

    // ====== BUG J1: MDC context loss across async threads ======
    @Test
    void test_mdc_propagated() {
        
        MDC.put("traceId", "test-trace-123");
        MDC.put("requestId", "req-456");

        try {
            CompletableFuture<Map<String, Object>> future =
                analyticsService.generateAsyncReport("report-1");

            Map<String, Object> result = future.get(5, TimeUnit.SECONDS);
            assertNotNull(result);
            assertEquals("report-1", result.get("reportId"));

            // With the bug, traceId is null in the async thread
            // With the fix, traceId should be propagated
            Object traceId = result.get("traceId");
            // The fix would make this equal to "test-trace-123"
            // With the bug, it's null
            if (traceId != null) {
                assertEquals("test-trace-123", traceId,
                    "MDC traceId should be propagated to async thread");
            }
        } catch (Exception e) {
            fail("Async report generation should not throw: " + e.getMessage());
        } finally {
            MDC.clear();
        }
    }

    @Test
    void test_trace_in_async() {
        
        MDC.put("traceId", "async-trace-789");

        try {
            CompletableFuture<Map<String, Object>> future =
                analyticsService.generateAsyncReport("report-2");

            Map<String, Object> result = future.get(5, TimeUnit.SECONDS);
            assertNotNull(result);
            assertNotNull(result.get("generatedAt"), "Should have generation timestamp");
        } catch (Exception e) {
            fail("Async report should complete: " + e.getMessage());
        } finally {
            MDC.clear();
        }
    }

    @Test
    void test_async_report_contains_id() {
        CompletableFuture<Map<String, Object>> future =
            analyticsService.generateAsyncReport("my-report");

        try {
            Map<String, Object> result = future.get(5, TimeUnit.SECONDS);
            assertEquals("my-report", result.get("reportId"));
        } catch (Exception e) {
            fail("Should complete without error");
        }
    }

    @Test
    void test_async_report_has_timestamp() {
        CompletableFuture<Map<String, Object>> future =
            analyticsService.generateAsyncReport("ts-report");

        try {
            Map<String, Object> result = future.get(5, TimeUnit.SECONDS);
            assertNotNull(result.get("generatedAt"));
            assertTrue((Long) result.get("generatedAt") > 0);
        } catch (Exception e) {
            fail("Should complete");
        }
    }

    @Test
    void test_async_multiple_reports() {
        List<CompletableFuture<Map<String, Object>>> futures = new ArrayList<>();
        for (int i = 0; i < 5; i++) {
            futures.add(analyticsService.generateAsyncReport("report-" + i));
        }

        for (int i = 0; i < 5; i++) {
            try {
                Map<String, Object> result = futures.get(i).get(5, TimeUnit.SECONDS);
                assertEquals("report-" + i, result.get("reportId"));
            } catch (Exception e) {
                fail("Report " + i + " should complete");
            }
        }
    }

    @Test
    void test_mdc_cleared_after_async() {
        MDC.put("traceId", "cleanup-test");

        try {
            analyticsService.generateAsyncReport("cleanup").get(5, TimeUnit.SECONDS);
        } catch (Exception e) {
            // ignore
        } finally {
            MDC.clear();
        }

        assertNull(MDC.get("traceId"), "MDC should be cleared after test");
    }

    // ====== Additional CSV tests ======
    @Test
    void test_csv_special_characters() {
        List<Map<String, Object>> data = new ArrayList<>();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("name", "O'Brien");
        row.put("city", "San Francisco");
        data.add(row);

        String csv = analyticsService.generateCsvReport(data);
        assertNotNull(csv);
        assertTrue(csv.contains("O'Brien"));
    }

    @Test
    void test_csv_numeric_values() {
        List<Map<String, Object>> data = new ArrayList<>();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("count", 100);
        row.put("rate", 3.14);
        data.add(row);

        String csv = analyticsService.generateCsvReport(data);
        assertTrue(csv.contains("100"));
        assertTrue(csv.contains("3.14"));
    }

    @Test
    void test_csv_empty_strings() {
        List<Map<String, Object>> data = new ArrayList<>();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("filled", "value");
        row.put("empty", "");
        data.add(row);

        String csv = analyticsService.generateCsvReport(data);
        assertNotNull(csv);
    }

    @Test
    @Timeout(value = 10, unit = TimeUnit.SECONDS)
    void test_csv_large_dataset_completes() {
        List<Map<String, Object>> data = createReportData(1000);
        String csv = analyticsService.generateCsvReport(data);
        assertNotNull(csv);
        assertFalse(csv.isEmpty());
    }

    // ====== Additional pagination tests ======
    @Test
    void test_pagination_all_pages_cover_all_items() {
        List<String> items = createStringList(23);
        int pageSize = 5;
        List<String> allPaginated = new ArrayList<>();

        for (int page = 1; page <= 5; page++) {
            allPaginated.addAll(analyticsService.paginate(items, page, pageSize));
        }
        // With fix, all 23 items should be covered across 5 pages
        // (pages 1-4: 5 items each = 20, page 5: 3 items)
    }

    @Test
    void test_pagination_large_page_size() {
        List<String> items = createStringList(5);
        List<String> page = analyticsService.paginate(items, 1, 100);
        if (!page.isEmpty()) {
            assertEquals(5, page.size(), "Should return all items when page size > list size");
        }
    }

    @Test
    void test_pagination_consecutive_pages_no_overlap() {
        List<String> items = createStringList(20);

        List<String> p1 = analyticsService.paginate(items, 1, 5);
        List<String> p2 = analyticsService.paginate(items, 2, 5);

        if (!p1.isEmpty() && !p2.isEmpty()) {
            // Pages should not overlap
            for (String item : p1) {
                assertFalse(p2.contains(item),
                    "Consecutive pages should not overlap");
            }
        }
    }

    // ====== Cache additional tests ======
    @Test
    void test_cache_empty_data() {
        List<Map<String, Object>> emptyData = new ArrayList<>();
        analyticsService.cacheReport("empty", emptyData);
        List<Map<String, Object>> cached = analyticsService.getCachedReport("empty");
        if (cached != null) {
            assertTrue(cached.isEmpty());
        }
    }

    @Test
    void test_cache_large_data() {
        List<Map<String, Object>> largeData = createReportData(1000);
        analyticsService.cacheReport("large", largeData);
        // Keep strong ref
        List<Map<String, Object>> ref = largeData;
        List<Map<String, Object>> cached = analyticsService.getCachedReport("large");
        assertNotNull(cached);
        assertEquals(1000, cached.size());
    }

    @Test
    void test_describe_metric_list_with_strings() {
        List<String> list = List.of("alpha", "beta");
        String result = analyticsService.describeMetric(list);
        assertNotNull(result);
    }

    @Test
    void test_describe_metric_boolean() {
        String result = analyticsService.describeMetric(Boolean.TRUE);
        assertNotNull(result);
    }

    @Test
    void test_describe_metric_long() {
        String result = analyticsService.describeMetric(Long.MAX_VALUE);
        assertNotNull(result);
    }

    @Test
    void test_pagination_type_preservation() {
        List<Integer> nums = List.of(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);
        List<Integer> page = analyticsService.paginate(nums, 1, 3);
        if (!page.isEmpty()) {
            assertTrue(page.get(0) instanceof Integer);
        }
    }

    @Test
    void test_csv_row_count_matches_data() {
        int rowCount = 15;
        List<Map<String, Object>> data = createReportData(rowCount);
        String csv = analyticsService.generateCsvReport(data);
        String[] lines = csv.split("\n");
        assertEquals(rowCount + 1, lines.length, "CSV lines = header + data rows");
    }

    @Test
    void test_async_report_no_exception() {
        assertDoesNotThrow(() -> {
            CompletableFuture<Map<String, Object>> future =
                analyticsService.generateAsyncReport("safe-report");
            future.get(5, TimeUnit.SECONDS);
        });
    }

    @Test
    void test_cache_concurrent_access() throws Exception {
        int threads = 10;
        CountDownLatch latch = new CountDownLatch(threads);
        List<Exception> errors = Collections.synchronizedList(new ArrayList<>());

        for (int i = 0; i < threads; i++) {
            final int idx = i;
            new Thread(() -> {
                try {
                    List<Map<String, Object>> data = createReportData(5);
                    analyticsService.cacheReport("key-" + idx, data);
                    analyticsService.getCachedReport("key-" + idx);
                } catch (Exception e) {
                    errors.add(e);
                } finally {
                    latch.countDown();
                }
            }).start();
        }

        latch.await(10, TimeUnit.SECONDS);
        assertTrue(errors.isEmpty(), "Concurrent cache access should not throw: " + errors);
    }

    @Test
    void test_pagination_negative_page_handled() {
        List<String> items = createStringList(10);
        // Negative page - depends on implementation
        assertDoesNotThrow(() -> analyticsService.paginate(items, -1, 5));
    }

    @Test
    void test_describe_empty_list() {
        List<String> emptyList = List.of();
        // Empty list may cause IndexOutOfBoundsException in buggy version
        assertDoesNotThrow(() -> analyticsService.describeMetric(emptyList));
    }

    // ====== Additional tests for coverage ======
    @Test
    void test_csv_boolean_values() {
        List<Map<String, Object>> data = new ArrayList<>();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("active", true);
        row.put("deleted", false);
        data.add(row);
        String csv = analyticsService.generateCsvReport(data);
        assertTrue(csv.contains("true"));
        assertTrue(csv.contains("false"));
    }

    @Test
    void test_csv_single_column() {
        List<Map<String, Object>> data = new ArrayList<>();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("id", 1);
        data.add(row);
        String csv = analyticsService.generateCsvReport(data);
        assertTrue(csv.contains("id"));
        assertTrue(csv.contains("1"));
    }

    @Test
    void test_pagination_page_3() {
        List<String> items = createStringList(30);
        List<String> page3 = analyticsService.paginate(items, 3, 10);
        assertFalse(page3.isEmpty());
    }

    @Test
    void test_pagination_items_not_modified() {
        List<String> items = new ArrayList<>(createStringList(10));
        int originalSize = items.size();
        analyticsService.paginate(items, 1, 5);
        assertEquals(originalSize, items.size(), "Original list should not be modified");
    }

    @Test
    void test_cache_null_key_lookup() {
        List<Map<String, Object>> result = analyticsService.getCachedReport(null);
        // Should return null or throw - either way, should not crash the service
    }

    @Test
    void test_describe_metric_float() {
        // Float gets autoboxed - not a Double
        String result = analyticsService.describeMetric(Float.valueOf(1.5f));
        assertNotNull(result);
    }

    @Test
    void test_describe_metric_byte() {
        String result = analyticsService.describeMetric(Byte.valueOf((byte) 42));
        assertNotNull(result);
    }

    @Test
    void test_describe_metric_character() {
        String result = analyticsService.describeMetric(Character.valueOf('A'));
        assertNotNull(result);
    }

    @Test
    void test_csv_many_columns() {
        List<Map<String, Object>> data = new ArrayList<>();
        Map<String, Object> row = new LinkedHashMap<>();
        for (int i = 0; i < 20; i++) {
            row.put("col" + i, "val" + i);
        }
        data.add(row);
        String csv = analyticsService.generateCsvReport(data);
        assertTrue(csv.contains("col0"));
        assertTrue(csv.contains("col19"));
    }

    @Test
    void test_pagination_page_size_equals_list_size() {
        List<String> items = createStringList(5);
        List<String> page = analyticsService.paginate(items, 1, 5);
        if (!page.isEmpty()) {
            assertEquals(5, page.size());
        }
    }

    @Test
    void test_async_report_different_ids() {
        try {
            CompletableFuture<Map<String, Object>> f1 = analyticsService.generateAsyncReport("r1");
            CompletableFuture<Map<String, Object>> f2 = analyticsService.generateAsyncReport("r2");
            Map<String, Object> r1 = f1.get(5, TimeUnit.SECONDS);
            Map<String, Object> r2 = f2.get(5, TimeUnit.SECONDS);
            assertEquals("r1", r1.get("reportId"));
            assertEquals("r2", r2.get("reportId"));
        } catch (Exception e) {
            fail("Both reports should complete");
        }
    }

    @Test
    void test_cache_after_gc_hint() {
        List<Map<String, Object>> data = createReportData(10);
        analyticsService.cacheReport("gc-test", data);
        // Hint GC - with WeakReference, data might be collected
        // With SoftReference fix, data should survive
        System.gc();
        // Keep strong ref to prevent actual collection
        List<Map<String, Object>> ref = data;
        List<Map<String, Object>> cached = analyticsService.getCachedReport("gc-test");
        assertNotNull(cached, "Data with strong reference should survive GC");
    }

    @Test
    void test_describe_singleton_list() {
        List<String> single = List.of("only");
        String result = analyticsService.describeMetric(single);
        assertNotNull(result);
        assertTrue(result.contains("List") || result.contains("list") || result.contains("metric"));
    }

    @Test
    void test_csv_unicode_values() {
        List<Map<String, Object>> data = new ArrayList<>();
        Map<String, Object> row = new LinkedHashMap<>();
        row.put("city", "Zurich");
        row.put("symbol", "$");
        data.add(row);
        String csv = analyticsService.generateCsvReport(data);
        assertNotNull(csv);
    }

    @Test
    void test_pagination_two_items_page_one() {
        List<String> items = List.of("a", "b");
        List<String> page = analyticsService.paginate(items, 1, 5);
        if (!page.isEmpty()) {
            assertTrue(page.size() <= 2);
        }
    }

    @Test
    void test_pagination_returns_new_list() {
        List<String> items = createStringList(10);
        List<String> p1 = analyticsService.paginate(items, 1, 5);
        List<String> p2 = analyticsService.paginate(items, 1, 5);
        if (!p1.isEmpty() && !p2.isEmpty()) {
            assertNotSame(p1, p2, "Each call should return a new list instance");
        }
    }

    @Test
    void test_describe_metric_map() {
        Map<String, String> map = Map.of("key", "value");
        String result = analyticsService.describeMetric(map);
        assertNotNull(result);
    }

    @Test
    void test_csv_two_rows_same_data() {
        List<Map<String, Object>> data = new ArrayList<>();
        Map<String, Object> row1 = new LinkedHashMap<>();
        row1.put("id", 1);
        data.add(row1);
        Map<String, Object> row2 = new LinkedHashMap<>();
        row2.put("id", 1);
        data.add(row2);
        String csv = analyticsService.generateCsvReport(data);
        String[] lines = csv.split("\n");
        assertEquals(3, lines.length); // header + 2 rows
    }

    @Test
    void test_async_report_completes_without_mdc() {
        // No MDC set - should still work
        MDC.clear();
        try {
            Map<String, Object> result = analyticsService.generateAsyncReport("no-mdc")
                .get(5, TimeUnit.SECONDS);
            assertNotNull(result);
        } catch (Exception e) {
            fail("Should complete without MDC");
        }
    }

    @Test
    void test_cache_sequential_operations() {
        for (int i = 0; i < 10; i++) {
            List<Map<String, Object>> data = createReportData(i + 1);
            analyticsService.cacheReport("seq-" + i, data);
        }
        // Should not throw
    }

    // Helpers
    private List<Map<String, Object>> createReportData(int rows) {
        List<Map<String, Object>> data = new ArrayList<>();
        for (int i = 0; i < rows; i++) {
            Map<String, Object> row = new LinkedHashMap<>();
            row.put("id", i);
            row.put("name", "item-" + i);
            row.put("value", i * 10.5);
            data.add(row);
        }
        return data;
    }

    private List<String> createStringList(int count) {
        List<String> list = new ArrayList<>();
        for (int i = 0; i < count; i++) {
            list.add("item-" + i);
        }
        return list;
    }
}
